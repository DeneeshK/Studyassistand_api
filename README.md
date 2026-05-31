# EduMind Study Assistant API

EduMind Study Assistant API is a standalone FastAPI backend for turning learning
materials into structured study notes. It accepts text-based PDFs, YouTube videos
with captions, and live-class recordings, then returns a shared `LearnableNote`
response shape with sections, takeaways, questions, MCQs, and flashcards.

This service runs separately from the main EduMind course backend. The current
backend stores uploaded files and generated artifacts on local disk and keeps
live-class session state in memory.

## Features

| Feature | Endpoint | Summary |
| --- | --- | --- |
| Health check | `GET /health` | Returns service status and UTC timestamp. |
| PDF notes | `POST /pdf/short-note` | Uploads a PDF, extracts text page by page, and generates a note. |
| YouTube notes | `POST /youtube/learnable-note` | Fetches available captions/subtitles for a YouTube URL and generates a note. |
| Live class start | `POST /live-class/start` | Creates an in-memory live-class session. |
| Live class finish | `POST /live-class/{session_id}/finish` | Accepts one full recording upload, converts/transcribes it, and generates a note. |

## Repository Layout

```text
app/
  main.py                  FastAPI application setup, CORS, startup, routers
  config.py                Environment-backed settings
  routes/                  HTTP route handlers and route-local response models
  schemas/                 Shared Pydantic response models
  services/                Note generation and LLM/fallback orchestration
  extraction/              PDF and YouTube transcript extraction
  transcription/           Audio conversion and Whisper transcription
  storage/                 Local file storage and in-memory session storage
  docs/                    Legacy app-local documentation
docs/                      Project documentation for reviewers and developers
storage/                   Runtime-generated local files
```

## Quick Start

Install Python dependencies and start the API from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Swagger UI is available at `http://localhost:8100/docs`.

## Required System Dependency

`ffmpeg` must be installed and available on `PATH` for live-class audio
conversion.

```bash
ffmpeg -version
```

## Environment

Copy `.env.example` to `.env` and set values for your environment. The service
can run without `GROQ_API_KEY`, but note generation will use the local fallback
path instead of Groq.

See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for the full variable reference.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API_REFERENCE.md)
- [Environment](docs/ENVIRONMENT.md)
- [Setup](docs/SETUP.md)
- [Testing](docs/TESTING.md)
- [Logging](docs/LOGGING.md)
- [Developer Handover](docs/DEVELOPER_HANDOVER.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Known Limitations

- OCR is not implemented for scanned/image-only PDFs.
- YouTube note generation depends on available manual or automatic captions.
- Live-class transcription accepts one full recording on the finish endpoint.
- Live-class sessions are in memory and are lost when the process restarts.
- Local runtime files under `storage/` are not a durable production data store.
