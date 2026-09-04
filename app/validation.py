from app.config import MAX_FILE_SIZE


class UploadValidationError(ValueError):
    """Raised when an uploaded file does not meet the input contract."""


def validate_filename(filename: str) -> None:
    if not filename.lower().endswith(".pdf"):
        raise UploadValidationError("只支持 PDF 文件")


def validate_pdf_header(header: bytes) -> None:
    if not header.startswith(b"%PDF-"):
        raise UploadValidationError("文件内容不是有效的 PDF")


def ensure_size(size: int, maximum: int = MAX_FILE_SIZE) -> None:
    if size > maximum:
        raise UploadValidationError("PDF 文件不能超过 50 MB")
