# EduMind Services Run Guide

EduMind commonly runs as separate services:

| Service | Default port | Purpose |
| --- | --- | --- |
| EduMind Core API | `8000` | Course and learning-platform backend. |
| Study Assistant API | `8100` | PDF notes, YouTube notes, and live-class transcription. |
| Frontend | `5173` | Browser application. |

## Study Assistant Environment

Copy `.env.example` to `.env` in this repository:

```env
APP_NAME=EduMind Study Assistant API
APP_ENV=development
HOST=0.0.0.0
PORT=8100
FRONTEND_ORIGIN=http://localhost:5173
CORE_API_URL=http://localhost:8000
STUDY_API_URL=http://localhost:8100
STORAGE_DIR=storage
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
WHISPER_MODEL=base.en
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=auto
MAX_UPLOAD_MB=200
AUDIO_CHUNK_SECONDS=5
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## Run Study Assistant API

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

Swagger UI: `http://localhost:8100/docs`

## Frontend Environment

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_STUDY_API_URL=http://localhost:8100
```

## Manual Checklist

Health:

```bash
curl http://localhost:8100/health
```

PDF notes:

- Upload a text-based PDF and confirm a note is returned.
- Upload a scanned/image-only PDF and confirm the response reports OCR is not
  implemented.

YouTube notes:

- Submit a public YouTube URL with captions and confirm a note is returned.
- Submit a video without captions and confirm a clear error response.

Live class:

- Start a session with `POST /live-class/start`.
- Submit a full recording file to `POST /live-class/{session_id}/finish`.
- Confirm the response includes `status: "completed"`, transcript text, and a
  note.

The current Study Assistant API does not expose an audio-chunk upload endpoint.
