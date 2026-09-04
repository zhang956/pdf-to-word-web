import pytest

from app.validation import (
    UploadValidationError,
    ensure_size,
    validate_filename,
    validate_pdf_header,
)


def test_accepts_case_insensitive_pdf_name_and_signature():
    validate_filename("报告.PDF")
    validate_pdf_header(b"%PDF-1.7\n")


def test_rejects_non_pdf_name():
    with pytest.raises(UploadValidationError, match="只支持 PDF 文件"):
        validate_filename("报告.txt")


def test_rejects_bad_pdf_signature():
    with pytest.raises(UploadValidationError, match="文件内容不是有效的 PDF"):
        validate_pdf_header(b"not a pdf")


def test_rejects_oversized_file():
    with pytest.raises(UploadValidationError, match="PDF 文件不能超过 50 MB"):
        ensure_size(11, maximum=10)
