from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator


LOW_TEXT_PAGE_THRESHOLD = 40
CHUNK_CHAR_LIMIT = 7000


def _load_fitz():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for PDF notes. Install the Study Assistant "
            "dependencies with: pip install -r app/requirements.txt"
        ) from exc
    return fitz


def clean_extracted_text(text: str) -> str:
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


# ── Generator: one page at a time ────────────────────────────────────────────

def iter_pdf_pages(pdf_path: str) -> Iterator[dict[str, Any]]:
    """
    Yield one result dict per page. Never loads the whole document text into memory.

    Each successful page yields:
        {"page_number": int, "text": str, "char_count": int, "status": "ok", "error": None}

    Each failed page yields:
        {"page_number": int, "text": "", "char_count": 0, "status": "failed", "error": str}
    """
    fitz = _load_fitz()
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    with fitz.open(path) as doc:
        for page_index in range(doc.page_count):
            page_number = page_index + 1
            try:
                page = doc.load_page(page_index)
                raw_text = page.get_text("text") or ""
                cleaned = clean_extracted_text(raw_text)
                yield {
                    "page_number": page_number,
                    "text": cleaned,
                    "char_count": len(cleaned),
                    "status": "ok",
                    "error": None,
                }
            except Exception as exc:
                yield {
                    "page_number": page_number,
                    "text": "",
                    "char_count": 0,
                    "status": "failed",
                    "error": str(exc),
                }


# ── Streaming extractor: consumes iter_pdf_pages ─────────────────────────────

def extract_pdf_text_streaming(
    pdf_path: str,
    min_chars_per_page: int = LOW_TEXT_PAGE_THRESHOLD,
) -> dict[str, Any]:
    """
    Consume iter_pdf_pages page-by-page (generator).
    Returns aggregated extraction metadata.
    """
    fitz = _load_fitz()
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Need total_pages before iterating — open briefly just for count
    with fitz.open(path) as doc:
        total_pages = doc.page_count

    text_parts: list[str] = []
    failed_pages: list[dict[str, Any]] = []
    low_text_pages: list[int] = []
    successful_pages = 0

    for page_result in iter_pdf_pages(pdf_path):
        if page_result["status"] == "failed":
            failed_pages.append({
                "page_number": page_result["page_number"],
                "error": page_result["error"],
            })
        else:
            successful_pages += 1
            if page_result["char_count"] < min_chars_per_page:
                low_text_pages.append(page_result["page_number"])
            if page_result["text"]:
                text_parts.append(page_result["text"])

    cleaned_text = clean_extracted_text("\n\n".join(text_parts))
    char_count = len(cleaned_text)
    is_probably_scanned = total_pages > 0 and (
        char_count < max(100, total_pages * min_chars_per_page)
        or len(low_text_pages) == total_pages
    )

    return {
        "text": cleaned_text,
        "total_pages": total_pages,
        "successful_pages": successful_pages,
        "failed_pages": failed_pages,
        "low_text_pages": low_text_pages,
        "is_probably_scanned": is_probably_scanned,
        "char_count": char_count,
    }


# ── Chunk generator: yields chunks for long PDFs ─────────────────────────────

def iter_pdf_text_chunks(
    pdf_path: str,
    max_chars: int = CHUNK_CHAR_LIMIT,
) -> Iterator[dict[str, Any]]:
    """
    Yield text chunks from a PDF, accumulating pages until max_chars is reached.

    Each chunk yields:
        {"chunk_id": "chunk_001", "start_page": int, "end_page": int,
         "text": str, "char_count": int}
    """
    chunk_parts: list[str] = []
    chunk_start_page = 1
    chunk_chars = 0
    chunk_index = 0

    for page_result in iter_pdf_pages(pdf_path):
        if page_result["status"] == "failed" or not page_result["text"]:
            continue

        page_text = page_result["text"]
        page_number = page_result["page_number"]

        if chunk_parts and chunk_chars + len(page_text) > max_chars:
            chunk_index += 1
            yield {
                "chunk_id": f"chunk_{chunk_index:03d}",
                "start_page": chunk_start_page,
                "end_page": page_number - 1,
                "text": clean_extracted_text("\n\n".join(chunk_parts)),
                "char_count": chunk_chars,
            }
            chunk_parts = []
            chunk_start_page = page_number
            chunk_chars = 0

        chunk_parts.append(page_text)
        chunk_chars += len(page_text)

    if chunk_parts:
        chunk_index += 1
        yield {
            "chunk_id": f"chunk_{chunk_index:03d}",
            "start_page": chunk_start_page,
            "end_page": chunk_start_page + len(chunk_parts) - 1,
            "text": clean_extracted_text("\n\n".join(chunk_parts)),
            "char_count": chunk_chars,
        }
