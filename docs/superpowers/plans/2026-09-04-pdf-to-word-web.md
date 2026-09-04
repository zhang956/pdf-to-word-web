# PDF 转 Word 网页程序 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个本地网页应用，将文字型、扫描型和混合型 PDF 转换为优先可编辑的 DOCX 文件。

**Architecture:** FastAPI 负责页面、上传、后台转换、状态查询和下载；转换器逐页通过 PyMuPDF 提取文本、表格和图片，在文本不足时使用 Tesseract OCR；任务存储负责隔离临时目录、进度状态与过期清理。原生 HTML/CSS/JavaScript 页面轮询任务状态并提供下载。

**Tech Stack:** Python 3.10+、FastAPI、Uvicorn、PyMuPDF、python-docx、Pillow、Tesseract OCR、pytest、HTTPX

## Global Constraints

- 单次只上传一个 PDF，默认最大文件大小为 50 MB。
- OCR 默认使用 `chi_sim+eng`，不调用云端服务。
- 输出优先保证文字可编辑和阅读顺序正确，不承诺复杂排版像素级还原。
- 不引入账号、数据库、批量转换、任务历史或前端构建工具。
- 临时文件使用随机任务目录，完成、失败、下载后或超时均可清理。

---

### Task 1: 项目骨架与文件校验

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: 浏览器上传的文件名、Content-Type、文件头和累计字节数。
- Produces: `validate_filename(filename: str) -> None`、`validate_pdf_header(header: bytes) -> None`、`ensure_size(size: int, maximum: int = MAX_FILE_SIZE) -> None`，失败时抛出 `UploadValidationError`。

- [ ] **Step 1: 编写失败的文件校验测试**

```python
import pytest
from app.validation import UploadValidationError, ensure_size, validate_filename, validate_pdf_header

def test_accepts_case_insensitive_pdf_name_and_signature():
    validate_filename("报告.PDF")
    validate_pdf_header(b"%PDF-1.7\n")

def test_rejects_non_pdf_name_bad_signature_and_oversize():
    with pytest.raises(UploadValidationError):
        validate_filename("报告.txt")
    with pytest.raises(UploadValidationError):
        validate_pdf_header(b"not a pdf")
    with pytest.raises(UploadValidationError):
        ensure_size(11, maximum=10)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_validation.py -v`

Expected: FAIL，提示 `app.validation` 不存在。

- [ ] **Step 3: 添加依赖、配置和最小校验实现**

```python
# app/config.py
from pathlib import Path

MAX_FILE_SIZE = 50 * 1024 * 1024
TASK_TTL_SECONDS = 60 * 60
WORK_ROOT = Path(".runtime/tasks")
OCR_LANGUAGES = "chi_sim+eng"
```

```python
# app/validation.py
from app.config import MAX_FILE_SIZE

class UploadValidationError(ValueError):
    pass

def validate_filename(filename: str) -> None:
    if not filename.lower().endswith(".pdf"):
        raise UploadValidationError("只支持 PDF 文件")

def validate_pdf_header(header: bytes) -> None:
    if not header.startswith(b"%PDF-"):
        raise UploadValidationError("文件内容不是有效的 PDF")

def ensure_size(size: int, maximum: int = MAX_FILE_SIZE) -> None:
    if size > maximum:
        raise UploadValidationError("PDF 文件不能超过 50 MB")
```

`requirements.txt` 固定 FastAPI、Uvicorn、python-multipart、PyMuPDF、python-docx、Pillow、pytest 和 HTTPX 的兼容版本范围。

- [ ] **Step 4: 运行校验测试**

Run: `pytest tests/test_validation.py -v`

Expected: 2 passed。

- [ ] **Step 5: 提交任务（仅在 Git 仓库中）**

```bash
git add requirements.txt app tests/test_validation.py
git commit -m "feat: add PDF upload validation"
```

### Task 2: 临时任务存储与生命周期

**Files:**
- Create: `app/tasks.py`
- Test: `tests/test_tasks.py`

**Interfaces:**
- Consumes: `WORK_ROOT`、原始文件名和任务进度更新。
- Produces: `TaskStatus` 数据类与 `TaskStore.create()`、`get()`、`update()`、`delete()`、`cleanup_expired()`；每个任务只允许访问自身目录中的 `input.pdf` 和 `output.docx`。

- [ ] **Step 1: 编写失败的任务生命周期测试**

```python
from datetime import timedelta
from app.tasks import TaskStore

def test_task_lifecycle_uses_isolated_paths(tmp_path):
    store = TaskStore(tmp_path, ttl=3600)
    task = store.create("报告.pdf")
    assert task.input_path.parent == tmp_path / task.id
    assert task.output_path.parent == task.input_path.parent
    store.update(task.id, state="running", current_page=1, total_pages=2)
    assert store.get(task.id).progress == 50
    store.delete(task.id)
    assert store.get(task.id) is None
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_tasks.py -v`

Expected: FAIL，提示 `app.tasks` 不存在。

- [ ] **Step 3: 实现线程安全的内存任务表和目录清理**

实现 `TaskStatus(id, original_name, state, current_page, total_pages, error, created_at, input_path, output_path)`；`progress` 在总页数未知时为 0，完成时为 100，其余按页数计算。`TaskStore` 使用 `threading.Lock` 保护字典，通过 `uuid.uuid4().hex` 创建任务目录，并用 `shutil.rmtree(task.input_path.parent)` 删除精确任务目录。

- [ ] **Step 4: 运行任务测试**

Run: `pytest tests/test_tasks.py -v`

Expected: PASS。

- [ ] **Step 5: 提交任务（仅在 Git 仓库中）**

```bash
git add app/tasks.py tests/test_tasks.py
git commit -m "feat: add conversion task lifecycle"
```

### Task 3: PDF 页面分析与 OCR 判定

**Files:**
- Create: `app/extraction.py`
- Test: `tests/test_extraction.py`

**Interfaces:**
- Consumes: PyMuPDF `Page`。
- Produces: `needs_ocr(text: str, image_coverage: float) -> bool`、`extract_page(page, ocr_languages: str) -> PageContent`；`PageContent` 包含按 `(y0, x0)` 排序的 `paragraphs: list[str]`、`tables: list[list[list[str]]]` 和 `images: list[bytes]`。

- [ ] **Step 1: 编写 OCR 判定和排序失败测试**

```python
from app.extraction import needs_ocr, sort_blocks

def test_ocr_is_used_only_when_text_is_insufficient():
    assert needs_ocr("", 0.9)
    assert needs_ocr("少量字", 0.9)
    assert not needs_ocr("这是足够长的可提取文本内容" * 3, 0.1)

def test_blocks_are_sorted_in_reading_order():
    blocks = [(100, 20, "下"), (10, 50, "右"), (10, 10, "左")]
    assert [item[2] for item in sort_blocks(blocks)] == ["左", "右", "下"]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_extraction.py -v`

Expected: FAIL，提示导入目标不存在。

- [ ] **Step 3: 实现普通提取和 OCR 回退**

使用 `page.get_text("blocks", sort=True)` 提取文字块；当清理后的文本少于 30 个字符且页面主要由图像构成时，调用 `page.get_textpage_ocr(language=ocr_languages, dpi=300, full=True)`，然后把该 TextPage 传回 `page.get_text("blocks", textpage=...)`。通过 `page.find_tables()` 提取单元格文本，并提取面积和尺寸足够的嵌入图片。捕获 OCR 环境缺失并抛出带安装提示的 `ConversionError`。

- [ ] **Step 4: 运行提取测试**

Run: `pytest tests/test_extraction.py -v`

Expected: PASS。

- [ ] **Step 5: 提交任务（仅在 Git 仓库中）**

```bash
git add app/extraction.py tests/test_extraction.py
git commit -m "feat: extract PDF content with OCR fallback"
```

### Task 4: DOCX 生成与转换服务

**Files:**
- Create: `app/converter.py`
- Test: `tests/test_converter.py`

**Interfaces:**
- Consumes: `convert_pdf(input_path: Path, output_path: Path, progress: Callable[[int, int], None]) -> None`。
- Produces: 能被 python-docx 重新打开的 DOCX，正文为可编辑段落和 Word 表格，页面之间添加分页符。

- [ ] **Step 1: 编写失败的 DOCX 集成测试**

```python
import pymupdf
from docx import Document
from app.converter import convert_pdf

def test_text_pdf_becomes_editable_docx(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Editable PDF text")
    doc.save(pdf_path)
    output = tmp_path / "output.docx"
    calls = []
    convert_pdf(pdf_path, output, lambda current, total: calls.append((current, total)))
    word = Document(output)
    assert "Editable PDF text" in "\n".join(p.text for p in word.paragraphs)
    assert calls[-1] == (1, 1)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_converter.py -v`

Expected: FAIL，提示 `app.converter` 不存在。

- [ ] **Step 3: 实现 DOCX 写入和逐页转换**

设置 A4 页面和普通页边距；逐页调用 `extract_page`；非空段落写入 `Document.add_paragraph()`，表格写入 `Document.add_table()`，有效图片用内存流插入且宽度不超过正文区域；非末页添加分页符。打开加密或无页 PDF 时抛出中文 `ConversionError`，仅在全部页面成功后保存到最终输出路径。

- [ ] **Step 4: 运行转换测试**

Run: `pytest tests/test_converter.py -v`

Expected: PASS，生成的 DOCX 可重新打开且文字可选择。

- [ ] **Step 5: 提交任务（仅在 Git 仓库中）**

```bash
git add app/converter.py tests/test_converter.py
git commit -m "feat: generate editable Word documents"
```

### Task 5: FastAPI 上传、状态和下载接口

**Files:**
- Create: `app/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: multipart 字段 `file`、任务 ID。
- Produces: `POST /api/convert` 返回 HTTP 202 与 `{"task_id": "..."}`；状态接口返回 `state/progress/current_page/total_pages/error`；下载接口返回 DOCX。

- [ ] **Step 1: 编写失败的接口测试**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_rejects_non_pdf_upload():
    response = client.post("/api/convert", files={"file": ("x.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert response.json()["detail"] == "只支持 PDF 文件"

def test_unknown_task_is_404():
    assert client.get("/api/tasks/missing").status_code == 404
    assert client.get("/api/tasks/missing/download").status_code == 404
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_api.py -v`

Expected: FAIL，提示 `app.main` 不存在。

- [ ] **Step 3: 实现流式上传、后台转换和安全下载**

上传时每次读取 1 MB，将首块传给签名校验并持续调用大小校验；成功落盘后通过 `BackgroundTasks` 调用转换器。状态更新只能通过 `TaskStore`；转换异常写入 `failed/error`，成功写入 `completed`。下载只使用任务对象保存的 `output_path`，并设置经过清洗的 `.docx` 文件名。

- [ ] **Step 4: 运行接口测试**

Run: `pytest tests/test_api.py -v`

Expected: PASS。

- [ ] **Step 5: 提交任务（仅在 Git 仓库中）**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: expose PDF conversion API"
```

### Task 6: 上传与下载网页

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/styles.css`
- Create: `app/static/app.js`
- Modify: `app/main.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: Task 5 的三个 API。
- Produces: `GET /` 返回中文单页应用；拖拽和文件选择共用一个文件状态；每 700 ms 轮询；完成后展示下载按钮。

- [ ] **Step 1: 编写失败的首页测试**

```python
from fastapi.testclient import TestClient
from app.main import app

def test_home_page_contains_converter_controls():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "PDF 转 Word" in response.text
    assert 'id="drop-zone"' in response.text
    assert 'id="convert-button"' in response.text
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_web.py -v`

Expected: FAIL，首页尚未提供转换页面。

- [ ] **Step 3: 实现响应式单页界面**

HTML 使用语义化表单、可键盘触发的拖拽区、`aria-live` 状态区域、进度条和下载链接。JavaScript 在浏览器端验证 `.pdf` 与 50 MB 限制，上传后轮询状态，在 `completed` 时设置下载 URL，在 `failed` 时显示服务端错误；CSS 支持桌面和手机宽度，确保焦点样式和足够颜色对比度。

- [ ] **Step 4: 运行页面和全量测试**

Run: `pytest -v`

Expected: 全部 PASS。

- [ ] **Step 5: 提交任务（仅在 Git 仓库中）**

```bash
git add app/static app/main.py tests/test_web.py
git commit -m "feat: add PDF conversion web interface"
```

### Task 7: 启动说明与端到端验收

**Files:**
- Create: `README.md`
- Create: `run.sh`
- Create: `.gitignore`
- Test: `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: Python 环境、Tesseract 的 `chi_sim` 和 `eng` 数据。
- Produces: `./run.sh` 在 `127.0.0.1:8000` 启动网页；README 给出 Linux 安装、启动、测试、限制和排错命令。

- [ ] **Step 1: 添加真实文件端到端测试**

测试动态生成包含文字页和整页图片的混合 PDF，执行 `convert_pdf` 后用 python-docx 打开，断言普通页文字存在、页数回调完成；当本机存在 `chi_sim` 时再断言扫描页中文 OCR，否则将 OCR 环境检查作为明确跳过原因。

- [ ] **Step 2: 运行端到端测试并记录基线**

Run: `pytest tests/test_end_to_end.py -v`

Expected: 普通转换 PASS；OCR 测试 PASS，或仅因明确缺少 `chi_sim` 数据而 SKIP。

- [ ] **Step 3: 添加启动脚本和 README**

`run.sh` 使用 `exec python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"`；README 提供虚拟环境安装、`tesseract-ocr`、`tesseract-ocr-chi-sim`、Python 依赖安装、启动、测试、HTTP 地址、50 MB 限制和 OCR 排错说明；`.gitignore` 忽略虚拟环境、缓存、测试缓存及 `.runtime/`。

- [ ] **Step 4: 完整验证**

Run: `pytest -v`

Expected: 全部可运行测试 PASS，OCR 测试仅允许因语言包缺失而 SKIP。

Run: `bash -n run.sh`

Expected: exit 0。

Run: `./run.sh`

Expected: Uvicorn 监听 `127.0.0.1:8000`；`curl -I http://127.0.0.1:8000/` 返回 HTTP 200；上传样例后状态最终为 `completed` 且下载响应为 DOCX MIME 类型。

- [ ] **Step 5: 提交任务（仅在 Git 仓库中）**

```bash
git add README.md run.sh .gitignore tests/test_end_to_end.py
git commit -m "docs: add setup and end-to-end verification"
```
