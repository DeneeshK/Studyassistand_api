from __future__ import annotations

from functools import lru_cache

from app.config import settings


def _resolve_device_and_compute() -> tuple[str, str]:
    """
    Resolve WHISPER_DEVICE and WHISPER_COMPUTE_TYPE from settings.
    "auto" selects cpu/int8 safely on machines without CUDA.
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

    return device, compute


@lru_cache(maxsize=1)
def _load_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is required for Google Meet/live-class transcription. "
            "Install the Study Assistant dependencies with: pip install -r app/requirements.txt"
        ) from exc

    device, compute = _resolve_device_and_compute()
    return WhisperModel(settings.WHISPER_MODEL, device=device, compute_type=compute)


def transcribe_audio(audio_path: str) -> str:
    model = _load_model()
    segments, _info = model.transcribe(audio_path, beam_size=5)
    transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
    if not transcript:
        raise RuntimeError("No speech was transcribed from the uploaded audio.")
    return transcript
