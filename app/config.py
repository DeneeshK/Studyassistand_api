"""Environment-backed configuration for the Study Assistant API."""

from pathlib import Path
from pydantic_settings import BaseSettings

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env files."""

    # ── Core ──────────────────────────────────────────────────────────────────
    APP_NAME:   str = "EduMind Study Assistant API"
    APP_ENV:    str = "development"
    HOST:       str = "0.0.0.0"
    PORT:       int = 8100

    FRONTEND_ORIGIN: str = "http://localhost:5173"
    CORE_API_URL:    str = "http://localhost:8000"
    STUDY_API_URL:   str = "http://localhost:8100"

    STORAGE_DIR: str = "storage"

    # ── LLM (Groq — for PDF/YouTube/Live Class notes) ─────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL:   str = "llama-3.1-8b-instant"

    # ── Whisper (local — for Live Class transcription) ────────────────────────
    WHISPER_MODEL:        str = "base.en"
    WHISPER_DEVICE:       str = "auto"
    WHISPER_COMPUTE_TYPE: str = "auto"

    # ── Upload limits ─────────────────────────────────────────────────────────
    MAX_UPLOAD_MB:       int = 200
    AUDIO_CHUNK_SECONDS: int = 5

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def audio_dir(self) -> str:
        """Return the configured directory for live-class audio artifacts."""
        return f"{self.STORAGE_DIR}/audio"

    class Config:
        """Pydantic settings source configuration."""

        env_file = (".env", str(APP_DIR / ".env"))
        env_file_encoding = "utf-8"
        # Silently ignore env vars from the core backend (.env in project root)
        # that don't belong to this service (TAVILY_API_KEY, DATABASE_URL, etc.)
        extra = "ignore"


settings = Settings()
