from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.config import settings


# ── Storage directory helpers ────────────────────────────────────────────────

def ensure_storage_dirs() -> None:
    """Create all required storage directories on startup."""
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


def _storage_root() -> Path:
    root = Path(settings.STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(filename: str) -> str:
    name = Path(filename or "upload.bin").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "upload.bin"


def _safe_subdir(subdir: str | None) -> Path:
    if not subdir:
        return Path()
    clean_parts = [
        re.sub(r"[^A-Za-z0-9._-]+", "_", part).strip("._")
        for part in Path(subdir).parts
        if part not in {"", ".", ".."}
    ]
    return Path(*[part for part in clean_parts if part])


def save_uploaded_file(file_bytes: bytes, filename: str, subdir: str = "uploads") -> str:
    directory = _storage_root() / _safe_subdir(subdir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _safe_filename(filename)
    path.write_bytes(file_bytes)
    return str(path)


def save_text_file(text: str, filename: str, subdir: str = "transcripts") -> str:
    directory = _storage_root() / _safe_subdir(subdir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _safe_filename(filename)
    path.write_text(text or "", encoding="utf-8")
    return str(path)


def save_json_file(data: dict[str, Any], filename: str, subdir: str = "notes") -> str:
    directory = _storage_root() / _safe_subdir(subdir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _safe_filename(filename)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
