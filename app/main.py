"""FastAPI application setup for the EduMind Study Assistant API."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import health, pdf, youtube, live_class
from app.storage.file_storage import ensure_storage_dirs

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EduMind Study Assistant API",
    description=(
        "Service for PDF notes, YouTube notes, and live class transcription."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

if settings.FRONTEND_ORIGIN and settings.FRONTEND_ORIGIN not in _raw_origins:
    _raw_origins.append(settings.FRONTEND_ORIGIN)

_dev_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
for _o in _dev_origins:
    if _o not in _raw_origins:
        _raw_origins.append(_o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_raw_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Create local runtime storage directories before serving requests."""
    logger.info("Initializing Study Assistant storage directories")
    ensure_storage_dirs()


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router,     tags=["Health"])
app.include_router(pdf.router,        prefix="/pdf",        tags=["PDF"])
app.include_router(youtube.router,    prefix="/youtube",    tags=["YouTube"])
app.include_router(live_class.router, prefix="/live-class", tags=["Live Class"])
