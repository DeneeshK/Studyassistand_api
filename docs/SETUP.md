# Setup

## Prerequisites

- Python 3.10 or newer
- `ffmpeg` on `PATH` for live-class recording conversion
- Internet access for YouTube caption retrieval and Groq-backed note generation
- Optional Groq API key for LLM-generated notes

## Install ffmpeg

Ubuntu or Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

macOS with Homebrew:

```bash
brew install ffmpeg
```

Verify installation:

```bash
ffmpeg -version
```

## Python Environment

Run commands from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
```

## Configure Environment

```bash
cp .env.example .env
```

Set `GROQ_API_KEY` if LLM-backed notes are required. Without it, the service uses
the local fallback generator.

## Start the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Open:

- Swagger UI: `http://localhost:8100/docs`
- ReDoc: `http://localhost:8100/redoc`
- Health: `http://localhost:8100/health`

## Manual Smoke Checks

Health:

```bash
curl http://localhost:8100/health
```

PDF:

```bash
curl -X POST "http://localhost:8100/pdf/short-note" \
  -F "file=@sample.pdf" \
  -F "title=Sample Chapter" \
  -F "subject=Physics" \
  -F "depth=medium"
```

YouTube:

```bash
curl -X POST "http://localhost:8100/youtube/learnable-note" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID","title":"Sample Video","depth":"medium"}'
```

Live class:

```bash
SESSION_ID=$(curl -s -X POST "http://localhost:8100/live-class/start" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Class","subject":"Physics","depth":"medium"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['session_id'])")

curl -X POST "http://localhost:8100/live-class/${SESSION_ID}/finish" \
  -F "file=@recording.webm"
```

## Frontend Configuration

For a Vite frontend, set:

```env
VITE_STUDY_API_URL=http://localhost:8100
```
