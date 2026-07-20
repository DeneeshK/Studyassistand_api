# Environment

The service reads settings with `pydantic-settings` from process environment
variables, `.env`, and `app/.env`. Values in the real environment can override
file-based values.

Use `.env.example` as the template:

```bash
cp .env.example .env
```

## Variables

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `EduMind Study Assistant API` | Human-readable service name. |
| `APP_ENV` | `development` | Environment label used for deployment context. |
| `HOST` | `0.0.0.0` | Host value for local run commands or deployment wrappers. |
| `PORT` | `8100` | Default service port. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Primary frontend origin appended to CORS origins. |
| `CORE_API_URL` | `http://localhost:8000` | URL of the separate core EduMind backend. |
| `STUDY_API_URL` | `http://localhost:8100` | Public URL for this service. |
| `STORAGE_DIR` | `storage` | Root directory for uploads, audio, transcripts, and notes. |
| `GROQ_API_KEY` | empty | Enables Groq-backed note generation when set. |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq chat model used by `note_generator.py`. |
| `YOUTUBE_PROXY_URL` | empty | Optional HTTP(S) proxy for YouTube caption requests. Fixes `IpBlocked`/`RequestBlocked` errors when YouTube blocks this server's IP as a bot; used by both the `youtube-transcript-api` and `yt-dlp` extraction paths. |
| `WHISPER_MODEL` | `base.en` | `faster-whisper` model name for live-class transcription. |
| `WHISPER_DEVICE` | `auto` | `auto`, `cpu`, or `cuda`. |
| `WHISPER_COMPUTE_TYPE` | `auto` | `auto`, `int8`, `float16`, or another supported Faster Whisper value. |
| `MAX_UPLOAD_MB` | `200` | Configured upload limit value. The current route code does not enforce it directly. |
| `AUDIO_CHUNK_SECONDS` | `5` | Configured chunk length value. The current finish endpoint accepts one full recording. |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated origins passed to FastAPI CORS middleware. |

## Sensitive Values

Do not commit real API keys or secrets. Logging and documentation should refer
to the presence of a key, provider name, or model name without exposing key
contents.

## Storage Path Notes

`STORAGE_DIR` is resolved relative to the current working directory when the
server starts. Run the API from the repository root unless your deployment
intentionally sets an absolute storage path.

## LLM Fallback Behavior

If `GROQ_API_KEY` is empty, the `groq` package is missing, the provider call
fails, or the model response cannot be parsed as JSON, the service falls back to
local deterministic note generation. This fallback keeps the endpoint usable but
produces less polished study material than the LLM path.
