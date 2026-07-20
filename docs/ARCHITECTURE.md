# Architecture

## Purpose

The Study Assistant API is a focused FastAPI service that converts external
learning materials into structured notes. It is separate from the core EduMind
course backend and does not include course creation, roadmap generation,
student-progress tracking, authentication, or database persistence.

## Runtime Flow

The application starts in `app/main.py`. Startup creates required local storage
directories, configures CORS, and mounts four route groups:

| Area | Module | Responsibility |
| --- | --- | --- |
| Health | `app/routes/health.py` | Lightweight uptime/status response. |
| PDF | `app/routes/pdf.py` | PDF upload, extraction metadata, note generation response. |
| YouTube | `app/routes/youtube.py` | URL validation, caption extraction, transcript cleanup, note response. |
| Live class | `app/routes/live_class.py` | Session creation, recording upload, transcription, note response. |

## Major Components

### FastAPI Entry Point

`app/main.py` owns the FastAPI application object, CORS origins, startup storage
initialization, and router inclusion. It does not contain business workflow
logic beyond application wiring.

### Configuration

`app/config.py` defines `Settings`, a Pydantic settings object backed by
environment variables from `.env` and `app/.env`. Settings include service URLs,
storage location, Groq model configuration, Whisper model configuration, upload
limits, and CORS origins.

### Routes

Route modules translate HTTP requests into service calls and response models.
They perform endpoint-level checks such as PDF file extension validation, missing
live-class sessions, empty upload detection, and invalid YouTube URL handling.

### Schemas

`app/schemas/common.py` defines the shared `LearnableNote` shape returned by
PDF, YouTube, and live-class note generation. Route modules also define
endpoint-specific request and response models close to their handlers.

### Extraction

`app/extraction/pdf_extractor.py` uses PyMuPDF to read PDF text page by page,
track failed/low-text pages, detect likely scanned PDFs, and yield text chunks
for larger documents.

`app/extraction/youtube_extractor.py` validates supported YouTube URL forms,
uses `yt-dlp` metadata to locate captions, downloads the selected caption file,
parses JSON3 or VTT-like text, and normalizes transcript text.

### Note Generation

`app/services/note_generator.py` is the main note pipeline. It builds
depth-specific prompts, calls Groq when configured and available, normalizes
model JSON into the shared note shape, and falls back to deterministic
Python-based note generation when the LLM path is unavailable or fails.

`app/services/llm_service.py` and `app/services/question_generator.py` are
compatibility placeholders. The current implementation keeps LLM and question
generation behavior inside `note_generator.py`.

### Transcription

`app/transcription/audio_utils.py` converts uploaded recordings to 16 kHz mono
WAV with `ffmpeg`. It also contains an older chunk-combination helper that reads
session chunk paths if they exist.

`app/transcription/whisper_service.py` resolves Whisper device/compute settings,
loads `faster-whisper` lazily, and transcribes converted audio.

### Storage

`app/storage/file_storage.py` writes uploads, transcripts, and generated notes
under `STORAGE_DIR`. Filenames and subdirectories are sanitized before writing.

`app/storage/session_store.py` keeps live-class session metadata in a SQLite
file under `STORAGE_DIR`. Session state survives process restarts and is shared
by every worker process pointed at the same `STORAGE_DIR`.

## Data Flow

### PDF Notes

1. `POST /pdf/short-note` receives a multipart PDF upload.
2. The file is saved to local storage.
3. Text extraction runs page by page and returns metadata.
4. Scanned/image-like PDFs return an explanatory error response.
5. Short PDFs go directly to note generation.
6. Longer PDFs are summarized in chunks and merged into a final note.
7. The response includes extraction metadata and a parsed `LearnableNote`.

### YouTube Notes

1. `POST /youtube/learnable-note` receives a URL and optional note hints.
2. The URL is checked against supported YouTube hosts and path patterns.
3. `yt-dlp` fetches metadata and available captions.
4. Captions are selected, downloaded, parsed, and cleaned.
5. Clean transcript text is sent to note generation.
6. The response includes a transcript preview and parsed `LearnableNote`.

### Live-Class Notes

1. `POST /live-class/start` creates a durable session record.
2. `POST /live-class/{session_id}/finish` receives one full recording file,
   saves it under `storage/audio/{session_id}`, and returns `202 Accepted`
   immediately with a `status_url`.
3. In a background task: `ffmpeg` converts the recording to 16 kHz mono WAV,
   `faster-whisper` transcribes it, and a note is generated.
4. Transcript and generated note JSON are saved to local storage, and the
   session status is updated to `completed` (or `failed` with an error).
5. The frontend polls `GET /live-class/{session_id}/status` until the session
   is `completed` or `failed`.

## Failure Handling

The service returns explicit API errors for invalid uploads, missing sessions,
and empty live-class recordings. For note generation, the Groq path is best
effort: if the API key, dependency, response parsing, or provider call fails,
the deterministic fallback note generator is used.

## Persistence Model

There is no database or repository layer in the current backend. Runtime files
are written to local disk, and session state is stored in memory. Any production
deployment that needs durable sessions or generated artifacts should replace
these storage primitives with persistent infrastructure.
