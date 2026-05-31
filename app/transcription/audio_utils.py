from __future__ import annotations

import shutil
import subprocess
import tempfile
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
    """
    Combines all WebM chunks into a single 16kHz mono WAV in one FFmpeg pass.
    Returns the path to the WAV file directly.

    Using -c copy with WebM chunks fails because browser MediaRecorder resets
    timestamps to zero in every chunk. Re-encoding in a single pass fixes this.
    """
    session = get_session(session_id)
    if not session:
        raise RuntimeError(f"Session not found: {session_id}")

    chunks = [Path(p) for p in session.get("audio_chunks", [])]
    if not chunks:
        raise RuntimeError("No audio chunks were uploaded for this session.")

    missing = [str(p) for p in chunks if not p.exists()]
    if missing:
        raise RuntimeError(f"Uploaded audio chunk is missing: {missing[0]}")

    ffmpeg = _ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to combine audio chunks.")

    audio_dir = _audio_dir(session_id)
    concat_file = audio_dir / "chunks.txt"
    concat_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in chunks),
        encoding="utf-8",
    )

    # Output directly as 16kHz mono WAV — skips the broken intermediate WebM
    output_wav = audio_dir / "combined.16k.wav"

    command = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        # Re-encode to PCM 16kHz mono WAV in one pass
        # This fixes browser MediaRecorder timestamp resets per chunk
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_wav),
    ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed to combine chunks:\n{result.stderr.strip()}"
        )

    return str(output_wav)


def convert_to_wav_16k(audio_path: str) -> str:
    """
    If combine_audio_chunks already produced a .16k.wav, return it as-is.
    Otherwise convert whatever file we have to 16kHz mono WAV.
    This function is kept for compatibility but combine_audio_chunks now
    produces the final WAV directly, so this is usually a no-op.
    """
    path = Path(audio_path)
    if not path.exists():
        raise RuntimeError(f"Audio file not found: {audio_path}")

    # Already a 16kHz WAV from combine_audio_chunks — nothing to do
    if path.suffix.lower() == ".wav":
        return str(path)

    output_path = path.with_suffix(".16k.wav")
    ffmpeg = _ffmpeg()

    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to convert audio to 16kHz WAV.")

    command = [
        ffmpeg,
        "-y",
        "-i", str(path),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{result.stderr.strip()}"
        )
    return str(output_path)