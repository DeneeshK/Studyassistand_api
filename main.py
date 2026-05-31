from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading

from app.config import settings
from app.routes import health, pdf, youtube, live_class
from app.routes import mcq
from app.storage.file_storage import ensure_storage_dirs

app = FastAPI(
    title="EduMind Study Assistant API",
    description=(
        "Separate service for PDF notes, YouTube notes, "
        "live class transcription, and MCQ generation."
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
    ensure_storage_dirs()

    # Pre-load the fine-tuned MCQ model in a background thread so the API
    # starts immediately and the model is warm before the first MCQ request.
    def _warm():
        try:
            from app.mcq.model_loader import warm_model
            warm_model()
        except Exception as exc:
            print(f"[startup] MCQ model warm-up skipped: {exc}")

    threading.Thread(target=_warm, daemon=True).start()


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(pdf.router,       prefix="/pdf",        tags=["PDF"])
app.include_router(youtube.router,   prefix="/youtube",    tags=["YouTube"])
app.include_router(live_class.router, prefix="/live-class", tags=["Live Class"])
app.include_router(mcq.router,       prefix="/mcq",        tags=["MCQ"])
