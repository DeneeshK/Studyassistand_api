# EduMind Study Assistant API

A standalone FastAPI service that processes external learning materials (PDFs, YouTube videos,
and live class audio) and returns structured, student-friendly learnable notes.

This service runs **separately** from the main EduMind course backend.

---

## Features

| Endpoint | What it does |
|---|---|
| `POST /pdf/short-note` | Upload a PDF → extract text page-by-page → generate learnable note |
| `POST /youtube/learnable-note` | Paste a YouTube URL → fetch transcript → generate learnable note |
| `POST /live-class/start` | Create a session for recording a live class |
| `POST /live-class/{id}/audio-chunk` | Upload audio chunks from the browser (5-second WebM segments) |
| `POST /live-class/{id}/finish` | Combine chunks → transcribe with Whisper → generate learnable note |

---

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) — required for audio conversion and chunk combining

### Install ffmpeg

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

Verify: `ffmpeg -version`

---

## Setup

```bash
# 1. Clone or copy the project
cd path/to/project

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Install Python dependencies
pip install -r app/requirements.txt

# 4. Copy and fill in the environment file
cp app/.env.example app/.env
# Edit app/.env and set GROQ_API_KEY
```

---

## Environment Variables

All variables live in `app/.env`. See `app/.env.example` for the full list.

The most important ones:

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | _(required)_ | Groq API key — get one at https://console.groq.com |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model to use for note generation |
| `WHISPER_MODEL` | `base.en` | Whisper model size (`tiny.en`, `base.en`, `small.en`, `medium.en`) |
| `STORAGE_DIR` | `storage` | Root folder for uploads, audio chunks, transcripts, and notes |
| `PORT` | `8100` | Port this service listens on |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |

---

## Running the API

Run from the **project root** (the folder containing the `app/` package):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Open Swagger UI: http://localhost:8100/docs

---

## Frontend environment variable

Add this to your frontend `.env` (Vite):

```env
VITE_STUDY_API_URL=http://localhost:8100
```

---

## Manual curl tests

**Health check:**
```bash
curl http://localhost:8100/health
```

**PDF note:**
```bash
curl -X POST "http://localhost:8100/pdf/short-note" \
  -F "file=@sample.pdf" \
  -F "title=Sample Chapter" \
  -F "subject=Physics" \
  -F "depth=medium"
```

**YouTube note:**
```bash
curl -X POST "http://localhost:8100/youtube/learnable-note" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID","title":"Sample Video","depth":"medium"}'
```

**Live class (3-step):**
```bash
# 1. Start session
SESSION=$(curl -s -X POST "http://localhost:8100/live-class/start" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Class","subject":"Physics"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

echo "Session: $SESSION"

# 2. Upload a small audio file as a chunk
curl -X POST "http://localhost:8100/live-class/$SESSION/audio-chunk" \
  -F "file=@test_audio.webm"

# 3. Finish and get notes
curl -X POST "http://localhost:8100/live-class/$SESSION/finish"
```

---

## Known limitations

- **No OCR**: PDFs that are fully scanned/image-based will return an `is_probably_scanned` flag and no note.
- **No diarization**: Live class transcripts are a single unattributed text stream.
- **No WebSocket**: Chunks are uploaded via simple HTTP POST every 5 seconds.
- **In-memory sessions**: Restarting the API clears all live-class sessions. If the server restarts mid-recording, the session is lost.
- **YouTube**: Only works when the video has auto-generated or manual subtitles. No audio download fallback.
- **ffmpeg required**: Without ffmpeg, multi-chunk live class sessions cannot be combined or converted.
