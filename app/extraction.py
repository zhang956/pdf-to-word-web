from dataclasses import dataclass, field
import re
from typing import Any

import pymupdf

from app.errors import ConversionError


@dataclass
class ContentItem:
    kind: str
    y: float
    x: float
    value: Any


@dataclass
class PageContent:
    items: list[ContentItem] = field(default_factory=list)
    used_ocr: bool = False

    @property
    def paragraphs(self) -> list[str]:
        return [item.value for item in self.items if item.kind == "paragraph"]

    @property
    def tables(self) -> list[list[list[str]]]:
        return [item.value for item in self.items if item.kind == "table"]

    @property
    def images(self) -> list[bytes]:
        return [item.value for item in self.items if item.kind == "image"]


def needs_ocr(text: str, image_coverage: float) -> bool:
    compact_text = "".join(text.split())
    return len(compact_text) < 30 and image_coverage >= 0.35


def sort_blocks(blocks: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    return sorted(blocks, key=lambda item: (round(item[0], 1), item[1]))


def _image_coverage(page: pymupdf.Page) -> float:
    page_area = max(page.rect.width * page.rect.height, 1)
    covered_area = 0.0
    for image in page.get_images(full=True):
        xref = image[0]
        for rect in page.get_image_rects(xref):
            covered_area += max(rect.width, 0) * max(rect.height, 0)
    return min(covered_area / page_area, 1.0)


def _paragraph_items(
    blocks: list[tuple],
    table_rects: list[pymupdf.Rect],
) -> list[ContentItem]:
    items = []
    for block in blocks:
        if len(block) < 7 or block[6] != 0:
            continue
        text = str(block[4]).strip()
        rect = pymupdf.Rect(block[:4])
        center = (rect.x0 + rect.width / 2, rect.y0 + rect.height / 2)
        if text and not any(center in table_rect for table_rect in table_rects):
            items.append(ContentItem("paragraph", rect.y0, rect.x0, text))
    return items


def _extract_tables(page: pymupdf.Page) -> tuple[list[ContentItem], list[pymupdf.Rect]]:
    items: list[ContentItem] = []
    rects: list[pymupdf.Rect] = []
    try:
        finder = page.find_tables()
    except (AttributeError, RuntimeError, ValueError):
        return items, rects
    for table in finder.tables:
        rows = table.extract()
        cleaned_rows = [
            [(cell or "").strip() for cell in row]
            for row in rows
            if any((cell or "").strip() for cell in row)
        ]
        if cleaned_rows:
            rect = pymupdf.Rect(table.bbox)
            items.append(ContentItem("table", rect.y0, rect.x0, cleaned_rows))
            rects.append(rect)
    return items, rects


def _extract_images(page: pymupdf.Page) -> list[ContentItem]:
    images: list[ContentItem] = []
    page_area = max(page.rect.width * page.rect.height, 1)
    seen_xrefs: set[int] = set()
    for item in page.get_images(full=True):
        xref, width, height = item[0], item[2], item[3]
        if xref in seen_xrefs or width < 32 or height < 32:
            continue
        rects = page.get_image_rects(xref)
        rect_area = sum(rect.width * rect.height for rect in rects)
        if rect_area / page_area < 0.01:
            continue
        try:
            image = page.parent.extract_image(xref)["image"]
            rect = rects[0]
            images.append(ContentItem("image", rect.y0, rect.x0, image))
            seen_xrefs.add(xref)
        except (RuntimeError, KeyError):
            continue
    return images


def _ocr_blocks(page: pymupdf.Page, ocr_languages: str) -> list[tuple]:
    candidates: list[tuple[str, list[tuple], int]] = []
    languages = [language for language in ocr_languages.split("+") if language]
    requested_languages = [ocr_languages] if len(languages) > 1 else []
    requested_languages.extend(languages or [ocr_languages])
    for language in requested_languages:
        text_page = page.get_textpage_ocr(language=language, dpi=300, full=True)
        blocks = page.get_text("blocks", sort=True, textpage=text_page)
        text = "\n".join(str(block[4]) for block in blocks if len(block) >= 7 and block[6] == 0)
        chinese_count = len(re.findall(r"[\u3400-\u9fff]", text))
        candidates.append((language, blocks, chinese_count))

    combined = candidates[0]
    combined_text = "\n".join(str(block[4]) for block in combined[1])
    if combined[2] >= 2 and re.search(r"[A-Za-z]{3}", combined_text):
        return combined[1]
    chinese_candidates = [candidate for candidate in candidates if candidate[2] >= 2]
    if chinese_candidates:
        return max(chinese_candidates, key=lambda candidate: candidate[2])[1]
    for language, blocks, _ in candidates:
        if language == "eng":
            return blocks
    return candidates[0][1]


def extract_page(page: pymupdf.Page, ocr_languages: str) -> PageContent:
    blocks = page.get_text("blocks", sort=True)
    plain_text = "\n".join(str(block[4]) for block in blocks if len(block) >= 7 and block[6] == 0)
    used_ocr = needs_ocr(plain_text, _image_coverage(page))

    if used_ocr:
        try:
            blocks = _ocr_blocks(page, ocr_languages)
        except Exception as exc:
            raise ConversionError(
                "OCR 识别失败，请确认已安装 Tesseract 及 chi_sim、eng 语言包"
            ) from exc

    table_items, table_rects = _extract_tables(page)
    items = _paragraph_items(blocks, table_rects) + table_items
    if not used_ocr:
        items.extend(_extract_images(page))
    items.sort(key=lambda item: (round(item.y, 1), item.x))
    return PageContent(items=items, used_ocr=used_ocr)
