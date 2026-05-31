"""Faster Whisper integration for live-class transcription."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.config import settings


logger = logging.getLogger(__name__)

def _resolve_device_and_compute() -> tuple[str, str]:
    """Resolve Whisper device and compute type from configured settings.

    The `auto` device path selects CUDA when available and otherwise uses CPU.
    The `auto` compute path uses float16 on CUDA and int8 on CPU.

    Returns:
        Tuple of device name and Faster Whisper compute type.
    """
    device = settings.WHISPER_DEVICE
    compute = settings.WHISPER_COMPUTE_TYPE

    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"

    logger.debug("Resolved Whisper runtime device=%s compute_type=%s", device, compute)
    return device, compute


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the configured Faster Whisper model."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is required for Google Meet/live-class transcription. "
            "Install the Study Assistant dependencies with: pip install -r app/requirements.txt"
        ) from exc

    device, compute = _resolve_device_and_compute()
    logger.info("Loading Faster Whisper model model=%s device=%s compute_type=%s", settings.WHISPER_MODEL, device, compute)
    return WhisperModel(settings.WHISPER_MODEL, device=device, compute_type=compute)


def transcribe_audio(audio_path: str) -> str:
    """Transcribe an audio file with Faster Whisper.

    Args:
        audio_path: Local path to a WAV file or other supported audio file.

    Returns:
        Transcribed speech as a single string.

    Raises:
        RuntimeError: If the model produces no transcript text.
    """
    model = _load_model()
    logger.info("Starting Whisper transcription")
    segments, _info = model.transcribe(audio_path, beam_size=5)
    transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
    if not transcript:
        logger.warning("Whisper transcription completed with no speech text")
        raise RuntimeError("No speech was transcribed from the uploaded audio.")
    logger.info("Completed Whisper transcription transcript_chars=%s", len(transcript))
    return transcript
