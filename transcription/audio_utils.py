from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.config import settings
from app.storage.memory_store import get_session


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _audio_dir(session_id: str) -> Path:
    path = Path(settings.audio_dir) / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def combine_audio_chunks(session_id: str) -> str:
    session = get_session(session_id)
    if not session:
        raise RuntimeError(f"Session not found: {session_id}")

    chunks = [Path(path) for path in session.get("audio_chunks", [])]
    if not chunks:
        raise RuntimeError("No audio chunks were uploaded for this session.")

    missing = [str(path) for path in chunks if not path.exists()]
    if missing:
        raise RuntimeError(f"Uploaded audio chunk is missing: {missing[0]}")

    if len(chunks) == 1:
        return str(chunks[0])

    ffmpeg = _ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to combine multiple audio chunks.")

    output_path = _audio_dir(session_id) / "combined.webm"
    concat_file = _audio_dir(session_id) / "chunks.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.resolve()}'" for path in chunks),
        encoding="utf-8",
    )

    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg could not combine audio chunks.")
    return str(output_path)


def convert_to_wav_16k(audio_path: str) -> str:
    path = Path(audio_path)
    if not path.exists():
        raise RuntimeError(f"Audio file not found: {audio_path}")

    output_path = path.with_suffix(".16k.wav")
    ffmpeg = _ffmpeg()

    if not ffmpeg:
        if path.suffix.lower() == ".wav":
            return str(path)
        raise RuntimeError("ffmpeg is required to convert uploaded audio to 16 kHz WAV.")

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(path),
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg could not convert audio.")
    return str(output_path)
