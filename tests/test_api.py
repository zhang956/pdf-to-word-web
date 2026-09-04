import asyncio

import pymupdf
import httpx
import pytest

import app.main as main_module
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        login = await test_client.post(
            "/login",
            data={"password": "local-dev-password"},
            headers={"origin": "http://test"},
        )
        assert login.status_code == 303
        yield test_client


def _text_pdf() -> bytes:
    source = pymupdf.open()
    page = source.new_page()
    page.insert_text((72, 72), "API editable text")
    content = source.tobytes()
    source.close()
    return content


@pytest.mark.anyio
async def test_rejects_non_pdf_upload(client):
    response = await client.post(
        "/api/convert",
        files={"file": ("x.txt", b"hello", "text/plain")},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "只支持 PDF 文件"


@pytest.mark.anyio
async def test_rejects_fake_pdf_content(client):
    response = await client.post(
        "/api/convert",
        files={"file": ("x.pdf", b"hello", "application/pdf")},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "文件内容不是有效的 PDF"


@pytest.mark.anyio
async def test_unknown_task_is_404(client):
    assert (await client.get("/api/tasks/missing")).status_code == 404
    assert (await client.get("/api/tasks/missing/download")).status_code == 404


@pytest.mark.anyio
async def test_rejects_upload_when_conversion_capacity_is_full(client, monkeypatch):
    class NoCapacity:
        def acquire(self, blocking=False):
            return False

    monkeypatch.setattr(main_module, "conversion_slots", NoCapacity())
    response = await client.post(
        "/api/convert",
        files={"file": ("busy.pdf", _text_pdf(), "application/pdf")},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "转换任务较多，请稍后重试"


@pytest.mark.anyio
async def test_rejects_oversized_request_before_multipart_parsing(client):
    response = await client.post(
        "/api/convert",
        content=b"not-a-multipart-body",
        headers={
            "origin": "http://test",
            "content-type": "multipart/form-data; boundary=x",
            "content-length": str(32 * 1024 * 1024),
        },
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "请求体过大"


@pytest.mark.anyio
async def test_upload_converts_and_downloads_docx(client):
    response = await client.post(
        "/api/convert",
        files={"file": ("sample.pdf", _text_pdf(), "application/pdf")},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 202
    task_id = response.json()["task_id"]

    for _ in range(100):
        status = await client.get(f"/api/tasks/{task_id}")
        if status.json()["state"] in {"completed", "failed"}:
            break
        await asyncio.sleep(0.02)
    assert status.status_code == 200
    assert status.json()["state"] == "completed"
    assert status.json()["progress"] == 100

    download = await client.get(f"/api/tasks/{task_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert download.content.startswith(b"PK")
    assert (await client.get(f"/api/tasks/{task_id}")).status_code == 404
