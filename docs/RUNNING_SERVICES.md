# EduMind Services Run Guide

EduMind uses two separate backend services:

| Service | Port | Purpose |
|---|---|---|
| EduMind Core API | 8000 | Courses, curriculum agents, student state, evaluation |
| Study Assistant API | **8100** | PDF notes, YouTube notes, Live Class transcription |

---

## Environment variables

### Frontend `.env`
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_STUDY_API_URL=http://localhost:8100
```

### EduMind Core API `.env`
```env
DATABASE_URL=postgresql+asyncpg://edumind:edumind123@localhost:5432/edumind_db
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
EDUMIND_API_KEY=abc123
CORS_ORIGINS=http://localhost:5173
DEV_AUTH_ENABLED=true
CHROMADB_PATH=./chromadb_data
```

### Study Assistant API `app/.env`
```env
APP_NAME=EduMind Study Assistant API
PORT=8100
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
WHISPER_MODEL=base.en
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=auto
STORAGE_DIR=storage
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
FRONTEND_ORIGIN=http://localhost:5173
```

---

## Terminal 1: EduMind Core API
```bash
cd edumind_backend
source .venv/bin/activate
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

## Terminal 2: Study Assistant API

Run from the **project root** (the directory that contains the `app/` package):

```bash
source .venv/bin/activate
pip install -r app/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

Swagger UI: http://localhost:8100/docs

## Terminal 3: Frontend
```bash
cd edumind_frontend
npm install
npm run dev
```

Open: http://localhost:5173

---

## Manual test checklist

### Health
- [ ] `curl http://localhost:8100/health` returns `{"status":"ok",...}`

### PDF Notes
- [ ] Go to Study Assistant → PDF Notes
- [ ] Upload a text-based PDF with a title and subject
- [ ] Note generates with sections, questions, and flashcards
- [ ] Upload a scanned PDF → get clear "scanned PDF" message, no crash

### YouTube Notes
- [ ] Go to Study Assistant → YouTube Notes
- [ ] Paste a YouTube URL with subtitles → note generates
- [ ] Paste a video URL without subtitles → clear error message
- [ ] Paste an invalid URL → validation error

### Live Class
- [ ] Go to Study Assistant → Live Class Assistant
- [ ] Enter a class title
- [ ] Click "Start Live Assistant"
- [ ] Browser tab-sharing popup appears
- [ ] Select Google Meet tab with "Share tab audio" enabled
- [ ] Status changes to "Recording class audio…"
- [ ] Elapsed timer counts up
- [ ] Chunk count increments every 5 seconds
- [ ] Click "Stop and Generate Notes"
- [ ] Status changes to "Transcribing…"
- [ ] Transcript and learnable note appear
- [ ] If no audio tab selected → clear error message shown

### Existing course flow
- [ ] `/courses` lists courses
- [ ] Course creation, roadmap, evaluation, progress all work normally
