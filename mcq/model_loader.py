"""
app/mcq/model_loader.py

Safe wrapper around model_manager.get_model() and model_manager.generate().

Responsibilities:
  - Locate model_manager.py in the project root (outside app/)
  - Insert the project root into sys.path so imports resolve
  - Provide is_model_available() — fast check before attempting generation
  - Provide generate_mcq_response() — wraps generate() with error handling
  - Track whether the model loaded successfully

The model is loaded lazily: the first call to generate_mcq_response()
will trigger loading. A startup background thread in app/main.py calls
warm_model() to pre-load before the first real request arrives.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

# ── Add project root to path so model_manager and knowledge_base resolve ─────
_HERE     = Path(__file__).resolve().parent   # app/mcq/
_APP_DIR  = _HERE.parent                       # app/
_ROOT     = _APP_DIR.parent                    # project_root/

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── State ─────────────────────────────────────────────────────────────────────
_load_error:  str | None = None
_load_lock = threading.Lock()
_model_ready = False


def _check_prerequisites() -> str | None:
    """Return an error string if the model cannot be loaded, else None."""
    model_path = _ROOT / "outputs" / "final_model"
    if not model_path.exists():
        return (
            f"Fine-tuned model not found at: {model_path}\n"
            "Copy your trained LoRA adapters to outputs/final_model/ "
            "in the project root."
        )
    try:
        import unsloth  # noqa: F401
    except ImportError:
        return (
            "unsloth is not installed. "
            "Install it with: pip install unsloth"
        )
    try:
        import torch
        if not torch.cuda.is_available():
            return (
                "No CUDA GPU detected. "
                "The fine-tuned MCQ model requires a CUDA GPU."
            )
    except ImportError:
        return "torch is not installed."
    return None


def is_model_available() -> tuple[bool, str]:
    """
    Returns (ok, error_message).
    ok=True means the model is ready to use.
    """
    global _load_error, _model_ready

    if _model_ready:
        return True, ""

    if _load_error:
        return False, _load_error

    prereq_error = _check_prerequisites()
    if prereq_error:
        _load_error = prereq_error
        return False, prereq_error

    return False, "Model is still loading. Please try again in a moment."


def warm_model() -> None:
    """
    Called from app startup in a background thread.
    Loads the model into GPU memory so the first MCQ request is fast.
    """
    global _load_error, _model_ready

    prereq_error = _check_prerequisites()
    if prereq_error:
        with _load_lock:
            _load_error = prereq_error
        print(f"[MCQ] Skipping model load: {prereq_error}")
        return

    try:
        print("[MCQ] Loading fine-tuned model into VRAM...")
        from model_manager import get_model
        get_model()
        with _load_lock:
            _model_ready = True
        print("[MCQ] Fine-tuned model ready.")
    except Exception as exc:
        with _load_lock:
            _load_error = str(exc)
        print(f"[MCQ] Model load failed: {exc}")


def generate_mcq_response(
    messages: list[dict],
    max_new_tokens: int = 1200,
    temperature: float = 0.2,
) -> tuple[str | None, str | None]:
    """
    Run inference. Returns (response_text, error_message).
    One of the two will always be None.
    """
    global _model_ready

    ok, err = is_model_available()
    if not ok:
        # If it looks like the model just hasn't loaded yet, try loading now
        if "still loading" in err:
            try:
                from model_manager import get_model
                get_model()
                with _load_lock:
                    _model_ready = True
            except Exception as exc:
                return None, str(exc)
        else:
            return None, err

    try:
        from model_manager import generate
        response = generate(
            messages,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
        )
        return response, None
    except Exception as exc:
        return None, f"Generation failed: {exc}"
