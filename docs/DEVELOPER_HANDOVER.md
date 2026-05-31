# Developer Handover

## Service Scope

This backend is the Study Assistant API. It handles external study material
processing only:

- PDF to note
- YouTube captions to note
- Live-class recording to transcript and note

It does not implement the core EduMind course backend features such as course
creation, roadmaps, evaluations, progress tracking, authentication, or database
models.

## Important Files

| File | Why it matters |
| --- | --- |
| `app/main.py` | App setup, CORS, startup, router registration. |
| `app/config.py` | Environment-backed settings. |
| `app/routes/pdf.py` | PDF upload endpoint and response metadata mapping. |
| `app/routes/youtube.py` | YouTube note endpoint and URL/transcript failure responses. |
| `app/routes/live_class.py` | Live-class session start and full-recording finish endpoint. |
| `app/services/note_generator.py` | Groq prompt path, response normalization, and fallback note generator. |
| `app/extraction/pdf_extractor.py` | Page-by-page PDF extraction and scanned-PDF heuristic. |
| `app/extraction/youtube_extractor.py` | YouTube caption selection and parsing. |
| `app/transcription/audio_utils.py` | `ffmpeg` audio conversion helpers. |
| `app/transcription/whisper_service.py` | Faster Whisper model loading and transcription. |
| `app/storage/file_storage.py` | Local runtime file persistence. |
| `app/storage/memory_store.py` | Process-local live-session state. |

## Operational Notes

- Run the API from the repository root so relative `STORAGE_DIR` paths resolve
  consistently.
- Ensure `ffmpeg` is installed before testing live-class transcription.
- Set `GROQ_API_KEY` for provider-backed note generation.
- Expect first Whisper transcription to take longer because the model may need
  to load or download.
- Do not rely on in-memory sessions across restarts.

## Current Live-Class Contract

The implemented live-class flow is:

1. Start a session with `POST /live-class/start`.
2. Upload one complete recording file to `POST /live-class/{session_id}/finish`.

There is no implemented `/live-class/{session_id}/audio-chunk` route in the
current code. Some older documentation referenced chunk uploads; that is not the
current public API.

## Note Generation Contract

All source types share the `LearnableNote` model. The LLM path must return JSON
that can be normalized into that shape. When the LLM path is unavailable or
fails, the fallback generator returns a simpler note with the same keys.

## Safe Change Guidance

When modifying this backend:

- Preserve route paths, request models, response models, and exception behavior
  unless the API contract is intentionally changing.
- Keep logging free of raw documents, transcripts, prompts, LLM responses, and
  secrets.
- Prefer narrow changes in the module that owns the behavior.
- Update `docs/API_REFERENCE.md` whenever endpoint behavior changes.
- Add automated tests before changing extraction, transcription, or note
  generation behavior.

## Known Gaps

- No OCR for scanned PDFs.
- No durable session store.
- No automated test suite in the repository.
- No app-level logging configuration.
- `MAX_UPLOAD_MB` and `AUDIO_CHUNK_SECONDS` are settings values but are not
  enforced directly by the current route code.
