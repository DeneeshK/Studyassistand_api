"""PDF text extraction helpers for note generation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterator


logger = logging.getLogger(__name__)

LOW_TEXT_PAGE_THRESHOLD = 40
CHUNK_CHAR_LIMIT = 7000


def _load_fitz():
    """Import and return PyMuPDF, raising an install hint when unavailable."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for PDF notes. Install the Study Assistant "
            "dependencies with: pip install -r app/requirements.txt"
        ) from exc
    return fitz


def clean_extracted_text(text: str) -> str:
    """Normalize extracted PDF text while preserving paragraph boundaries."""
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


# ── Generator: one page at a time ────────────────────────────────────────────

def iter_pdf_pages(pdf_path: str) -> Iterator[dict[str, Any]]:
    """Yield extraction results one page at a time.

    The generator avoids loading the whole document text into memory and returns
    a structured result for both successful and failed pages.

    Each successful page yields:
        {"page_number": int, "text": str, "char_count": int, "status": "ok", "error": None}

    Each failed page yields:
        {"page_number": int, "text": "", "char_count": 0, "status": "failed", "error": str}
    """
    fitz = _load_fitz()
    path = Path(pdf_path)
    if not path.exists():
        logger.error("PDF file path does not exist")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    with fitz.open(path) as doc:
        logger.info("Starting PDF page extraction total_pages=%s", doc.page_count)
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
                logger.warning(
                    "Failed to extract PDF page page_number=%s error_type=%s",
                    page_number,
                    exc.__class__.__name__,
                )
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
    """Extract PDF text and aggregate page-level extraction metadata.

    Args:
        pdf_path: Local path to the PDF file.
        min_chars_per_page: Threshold used to flag low-text pages and likely
            scanned documents.

    Returns:
        Dictionary containing cleaned text, page counts, failed-page metadata,
        low-text page numbers, scanned-PDF heuristic result, and character count.

    Raises:
        FileNotFoundError: If the provided PDF path does not exist.
    """
    fitz = _load_fitz()
    path = Path(pdf_path)
    if not path.exists():
        logger.error("PDF file path does not exist")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # The aggregate response needs total_pages before page text is streamed.
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
    logger.info(
        "Aggregated PDF extraction total_pages=%s successful_pages=%s failed_pages=%s low_text_pages=%s char_count=%s scanned=%s",
        total_pages,
        successful_pages,
        len(failed_pages),
        len(low_text_pages),
        char_count,
        is_probably_scanned,
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
    """Yield cleaned PDF text chunks for long-document summarization.

    Pages are accumulated until the configured character limit would be exceeded,
    then emitted as a chunk with page-range metadata.

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
            logger.debug(
                "Yielding PDF text chunk chunk_id=%s start_page=%s end_page=%s char_count=%s",
                f"chunk_{chunk_index:03d}",
                chunk_start_page,
                page_number - 1,
                chunk_chars,
            )
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
        logger.debug(
            "Yielding final PDF text chunk chunk_id=%s start_page=%s char_count=%s",
            f"chunk_{chunk_index:03d}",
            chunk_start_page,
            chunk_chars,
        )
        yield {
            "chunk_id": f"chunk_{chunk_index:03d}",
            "start_page": chunk_start_page,
            "end_page": chunk_start_page + len(chunk_parts) - 1,
            "text": clean_extracted_text("\n\n".join(chunk_parts)),
            "char_count": chunk_chars,
        }
