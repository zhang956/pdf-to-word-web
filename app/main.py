import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from starlette.middleware.sessions import SessionMiddleware

from app.auth import is_authenticated, password_matches, require_api_auth, validate_same_origin
from app.body_limit import RequestBodyLimitMiddleware
from app.config import MAX_CONVERSION_JOBS, MAX_FILE_SIZE, TASK_TTL_SECONDS, WORK_ROOT, settings
from app.converter import convert_pdf
from app.errors import ConversionError
from app.rate_limit import SlidingWindowLimiter, client_ip
from app.tasks import TaskStatus, TaskStore
from app.validation import (
    UploadValidationError,
    ensure_size,
    validate_filename,
    validate_pdf_header,
)


task_store = TaskStore(WORK_ROOT, TASK_TTL_SECONDS)
conversion_pool = ThreadPoolExecutor(
    max_workers=settings.conversion_workers,
    thread_name_prefix="pdf-convert",
)
conversion_slots = BoundedSemaphore(MAX_CONVERSION_JOBS)
login_limiter = SlidingWindowLimiter(limit=10, window_seconds=600)
conversion_limiter = SlidingWindowLimiter(limit=5, window_seconds=600)
STATIC_ROOT = Path(__file__).parent / "static"


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(60)
        task_store.cleanup_expired()


@asynccontextmanager
async def lifespan(_: FastAPI):
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        conversion_pool.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="PDF 转 Word", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.production,
    same_site="lax",
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_size=settings.max_file_size + 1024 * 1024,
    path="/api/convert",
)


def _run_conversion(task_id: str) -> None:
    task = task_store.get(task_id)
    if task is None:
        return
    task_store.update(task_id, state="running", error=None)

    def report_progress(current: int, total: int) -> None:
        task_store.update(
            task_id,
            current_page=current,
            total_pages=total,
        )

    try:
        convert_pdf(task.input_path, task.output_path, report_progress)
        task_store.update(task_id, state="completed")
        task.input_path.unlink(missing_ok=True)
    except ConversionError as exc:
        task_store.update(task_id, state="failed", error=str(exc))
        task.input_path.unlink(missing_ok=True)
    except Exception:
        task_store.update(task_id, state="failed", error="转换过程中发生未知错误")
        task.input_path.unlink(missing_ok=True)
    finally:
        conversion_slots.release()


async def _queue_conversion(task_id: str) -> None:
    try:
        conversion_pool.submit(_run_conversion, task_id)
    except RuntimeError:
        conversion_slots.release()
        task_store.update(task_id, state="failed", error="转换服务正在关闭")


async def _delete_task_async(task_id: str) -> None:
    task_store.delete(task_id)


async def _stream_file(path: Path):
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            yield chunk


def _task_payload(task: TaskStatus) -> dict:
    return {
        "task_id": task.id,
        "state": task.state,
        "progress": task.progress,
        "current_page": task.current_page,
        "total_pages": task.total_pages,
        "error": task.error,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _login_page(error: str = "") -> HTMLResponse:
    content = (STATIC_ROOT / "login.html").read_text(encoding="utf-8")
    return HTMLResponse(content.replace("{{ERROR}}", error))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    if is_authenticated(request):
        return RedirectResponse("/", status_code=303)
    return _login_page()


@app.post("/login")
async def login(request: Request, password: str = Form(...)) -> Response:
    validate_same_origin(request)
    if not login_limiter.check(client_ip(request, settings.trust_render_proxy)):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后重试")
    if not password_matches(password):
        return HTMLResponse(
            _login_page("密码错误，请重试").body,
            status_code=401,
        )
    request.session.clear()
    request.session["authenticated"] = True
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    validate_same_origin(request)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> Response:
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse((STATIC_ROOT / "index.html").read_text(encoding="utf-8"))


@app.get("/static/styles.css")
async def styles() -> Response:
    return Response(
        (STATIC_ROOT / "styles.css").read_text(encoding="utf-8"),
        media_type="text/css",
    )


@app.get("/static/app.js")
async def javascript() -> Response:
    return Response(
        (STATIC_ROOT / "app.js").read_text(encoding="utf-8"),
        media_type="text/javascript",
    )


@app.post("/api/convert", status_code=202)
async def create_conversion(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict[str, str]:
    require_api_auth(request)
    validate_same_origin(request)
    if not conversion_limiter.check(client_ip(request, settings.trust_render_proxy)):
        await file.close()
        raise HTTPException(status_code=429, detail="转换提交过于频繁，请稍后重试")
    filename = file.filename or ""
    try:
        validate_filename(filename)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        task = task_store.create(filename)
    except OSError as exc:
        await file.close()
        raise HTTPException(status_code=500, detail="创建转换任务失败") from exc
    total_size = 0
    first_chunk = True
    try:
        with task.input_path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                if first_chunk:
                    validate_pdf_header(chunk)
                    first_chunk = False
                total_size += len(chunk)
                ensure_size(total_size, MAX_FILE_SIZE)
                target.write(chunk)
        if first_chunk:
            validate_pdf_header(b"")
    except UploadValidationError as exc:
        task_store.delete(task.id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        task_store.delete(task.id)
        raise HTTPException(status_code=500, detail="保存上传文件失败") from exc
    except Exception as exc:
        task_store.delete(task.id)
        raise HTTPException(status_code=500, detail="读取上传文件失败") from exc
    finally:
        await file.close()

    if not conversion_slots.acquire(blocking=False):
        task_store.delete(task.id)
        raise HTTPException(status_code=503, detail="转换任务较多，请稍后重试")

    background_tasks.add_task(_queue_conversion, task.id)
    return {"task_id": task.id}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, request: Request) -> dict:
    require_api_auth(request)
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="转换任务不存在或已过期")
    return _task_payload(task)


@app.get("/api/tasks/{task_id}/download")
async def download_task(task_id: str, request: Request) -> StreamingResponse:
    require_api_auth(request)
    task = task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="转换任务不存在或已过期")
    if task.state != "completed" or not task.output_path.is_file():
        raise HTTPException(status_code=409, detail="转换尚未完成")

    output_name = f"{Path(task.original_name).stem}.docx"
    encoded_name = quote(output_name)
    return StreamingResponse(
        _stream_file(task.output_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "Content-Length": str(task.output_path.stat().st_size),
        },
        background=BackgroundTask(_delete_task_async, task.id),
    )
