# EduMind Study Assistant API

This directory contains the FastAPI application package for the Study Assistant
API. The service processes PDFs, YouTube captions, and live-class recordings into
the shared `LearnableNote` response shape.

Canonical project documentation is maintained at the repository root:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/API_REFERENCE.md`
- `docs/ENVIRONMENT.md`
- `docs/SETUP.md`
- `docs/TESTING.md`
- `docs/LOGGING.md`
- `docs/DEVELOPER_HANDOVER.md`
- `docs/TROUBLESHOOTING.md`

## Run Locally

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Swagger UI: `http://localhost:8100/docs`

## Current Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service status and timestamp. |
| `POST /pdf/short-note` | Upload a PDF and generate a study note. |
| `POST /youtube/learnable-note` | Generate a note from available YouTube captions. |
| `POST /live-class/start` | Start a durable live-class session. |
| `POST /live-class/{session_id}/finish` | Upload one full recording; returns immediately and processes it in the background. |
| `GET /live-class/{session_id}/status` | Poll for transcription/note-generation progress and result. |

The implemented live-class API accepts the full recording on the finish
endpoint. It does not currently expose an audio-chunk upload route.
