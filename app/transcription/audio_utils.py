"""Audio conversion helpers for live-class transcription."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import settings
from app.storage.memory_store import get_session


logger = logging.getLogger(__name__)

def _ffmpeg() -> str | None:
    """Return the path to the ffmpeg executable when it is available."""
    return shutil.which("ffmpeg")


def _audio_dir(session_id: str) -> Path:
    """Return the local audio directory for a session, creating it if needed."""
    path = Path(settings.audio_dir) / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def combine_audio_chunks(session_id: str) -> str:
    """Combine stored WebM chunks into one 16 kHz mono WAV file.

    Using -c copy with WebM chunks fails because browser MediaRecorder resets
    timestamps to zero in every chunk. Re-encoding in a single pass fixes this.

    Args:
        session_id: Live-class session containing stored audio chunk paths.

    Returns:
        Path to the combined WAV file.

    Raises:
        RuntimeError: If the session, chunks, ffmpeg, or conversion fails.
    """
    session = get_session(session_id)
    if not session:
        logger.warning("Cannot combine audio chunks because session is missing session_id=%s", session_id)
        raise RuntimeError(f"Session not found: {session_id}")

    chunks = [Path(p) for p in session.get("audio_chunks", [])]
    if not chunks:
        logger.warning("Cannot combine audio chunks because no chunks were uploaded session_id=%s", session_id)
        raise RuntimeError("No audio chunks were uploaded for this session.")

    missing = [str(p) for p in chunks if not p.exists()]
    if missing:
        logger.warning("Cannot combine audio chunks because a stored chunk is missing session_id=%s", session_id)
        raise RuntimeError(f"Uploaded audio chunk is missing: {missing[0]}")

    ffmpeg = _ffmpeg()
    if not ffmpeg:
        logger.error("ffmpeg executable was not found for audio chunk combination")
        raise RuntimeError("ffmpeg is required to combine audio chunks.")

    audio_dir = _audio_dir(session_id)
    concat_file = audio_dir / "chunks.txt"
    concat_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in chunks),
        encoding="utf-8",
    )

    # Output directly as 16 kHz mono WAV to avoid a broken intermediate WebM.
    output_wav = audio_dir / "combined.16k.wav"

    command = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        # Re-encoding fixes browser MediaRecorder timestamp resets per chunk.
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_wav),
    ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("ffmpeg failed to combine audio chunks session_id=%s returncode=%s", session_id, result.returncode)
        raise RuntimeError(
            f"ffmpeg failed to combine chunks:\n{result.stderr.strip()}"
        )

    logger.info("Combined audio chunks session_id=%s chunk_count=%s", session_id, len(chunks))
    return str(output_wav)


def convert_to_wav_16k(audio_path: str) -> str:
    """Convert an audio file to 16 kHz mono WAV for Whisper.

    If the input is already a WAV file, its path is returned unchanged.

    Args:
        audio_path: Local path to the uploaded or combined audio file.

    Returns:
        Path to a WAV file suitable for transcription.

    Raises:
        RuntimeError: If the input file is missing, ffmpeg is unavailable, or
        conversion fails.
    """
    path = Path(audio_path)
    if not path.exists():
        logger.error("Audio file path does not exist for conversion")
        raise RuntimeError(f"Audio file not found: {audio_path}")

    # Existing WAV inputs are treated as already compatible by this helper.
    if path.suffix.lower() == ".wav":
        logger.info("Audio conversion skipped because input is already WAV")
        return str(path)

    output_path = path.with_suffix(".16k.wav")
    ffmpeg = _ffmpeg()

    if not ffmpeg:
        logger.error("ffmpeg executable was not found for audio conversion")
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
        logger.error("ffmpeg failed to convert audio returncode=%s", result.returncode)
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{result.stderr.strip()}"
        )
    logger.info("Converted audio to 16 kHz WAV")
    return str(output_path)
