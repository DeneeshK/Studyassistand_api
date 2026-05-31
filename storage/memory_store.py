from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


_sessions: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(session_id: str, title: str, subject: str | None = None) -> dict[str, Any]:
    session = {
        "session_id": session_id,
        "title": title,
        "subject": subject,
        "status": "started",
        "audio_chunks": [],
        "created_at": _now(),
        "updated_at": _now(),
        "transcript_path": None,
        "note_path": None,
    }
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> dict[str, Any] | None:
    return _sessions.get(session_id)


def add_chunk_to_session(session_id: str, file_path: str) -> int:
    session = get_session(session_id)
    if not session:
        raise KeyError(f"Session not found: {session_id}")
    session.setdefault("audio_chunks", []).append(file_path)
    session["updated_at"] = _now()
    return len(session["audio_chunks"])


def update_session(session_id: str, **fields: Any) -> dict[str, Any] | None:
    session = get_session(session_id)
    if not session:
        return None
    session.update(fields)
    session["updated_at"] = _now()
    return session
