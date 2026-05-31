"""Local filesystem storage helpers for uploads and generated artifacts."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.config import settings


logger = logging.getLogger(__name__)

# ── Storage directory helpers ────────────────────────────────────────────────

def ensure_storage_dirs() -> None:
    """Create the runtime directories used by uploads, transcripts, and notes."""
    root = Path(settings.STORAGE_DIR)
    subdirs = [
        "uploads",
        "pdf",
        "youtube",
        "audio",
        "transcripts",
        "notes",
    ]
    for subdir in subdirs:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    logger.info("Ensured storage directories root=%s subdir_count=%s", root, len(subdirs))


def _storage_root() -> Path:
    """Return the storage root path, creating it if it does not exist."""
    root = Path(settings.STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(filename: str) -> str:
    """Return a filesystem-safe basename for an uploaded or generated file."""
    name = Path(filename or "upload.bin").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "upload.bin"


def _safe_subdir(subdir: str | None) -> Path:
    """Return a sanitized relative subdirectory path under the storage root."""
    if not subdir:
        return Path()
    clean_parts = [
        re.sub(r"[^A-Za-z0-9._-]+", "_", part).strip("._")
        for part in Path(subdir).parts
        if part not in {"", ".", ".."}
    ]
    return Path(*[part for part in clean_parts if part])


def save_uploaded_file(file_bytes: bytes, filename: str, subdir: str = "uploads") -> str:
    """Write uploaded bytes to local storage and return the stored path."""
    directory = _storage_root() / _safe_subdir(subdir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _safe_filename(filename)
    path.write_bytes(file_bytes)
    logger.info(
        "Saved uploaded file subdir=%s byte_count=%s",
        _safe_subdir(subdir),
        len(file_bytes),
    )
    return str(path)


def save_text_file(text: str, filename: str, subdir: str = "transcripts") -> str:
    """Write UTF-8 text content to local storage and return the stored path."""
    directory = _storage_root() / _safe_subdir(subdir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _safe_filename(filename)
    path.write_text(text or "", encoding="utf-8")
    logger.info(
        "Saved text file subdir=%s char_count=%s",
        _safe_subdir(subdir),
        len(text or ""),
    )
    return str(path)


def save_json_file(data: dict[str, Any], filename: str, subdir: str = "notes") -> str:
    """Serialize a dictionary as UTF-8 JSON and return the stored path."""
    directory = _storage_root() / _safe_subdir(subdir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _safe_filename(filename)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Saved JSON file subdir=%s key_count=%s",
        _safe_subdir(subdir),
        len(data),
    )
    return str(path)
