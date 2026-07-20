"""Audio conversion helpers for live-class transcription."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)

def _ffmpeg() -> str | None:
    """Return the path to the ffmpeg executable when it is available."""
    return shutil.which("ffmpeg")


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
