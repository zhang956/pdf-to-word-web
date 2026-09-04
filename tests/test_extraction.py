import pymupdf

from app.extraction import extract_page, needs_ocr, sort_blocks


def test_ocr_is_used_only_when_text_is_insufficient():
    assert needs_ocr("", 0.9)
    assert needs_ocr("少量字", 0.9)
    assert not needs_ocr("这是足够长的可提取文本内容" * 3, 0.1)


def test_blocks_are_sorted_in_reading_order():
    blocks = [(100, 20, "下"), (10, 50, "右"), (10, 10, "左")]
    assert [item[2] for item in sort_blocks(blocks)] == ["左", "右", "下"]


def test_extracts_text_blocks_from_text_page():
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "First editable paragraph")
    page.insert_text((72, 120), "Second editable paragraph")

    content = extract_page(page, "chi_sim+eng")

    assert content.paragraphs == [
        "First editable paragraph",
        "Second editable paragraph",
    ]
    assert not content.used_ocr
