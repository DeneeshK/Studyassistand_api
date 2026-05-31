# Testing

## Current Test Status

No automated test suite is present in the repository at the time of this
documentation pass. There is no `tests/` directory, `pytest.ini`,
`pyproject.toml`, or project test command.

## Recommended Validation Commands

Use import/compile checks when making documentation, docstring, comment, or
logging-only changes:

```bash
python -m compileall app
```

If `pytest` is later added to the project, run:

```bash
pytest
```

## Manual Endpoint Checks

Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

Then check:

```bash
curl http://localhost:8100/health
```

For PDF and live-class checks, use small local sample files so failures are easy
to reproduce. For YouTube checks, choose a video with public captions or
automatic captions.

## External Dependencies During Tests

- PDF extraction requires `PyMuPDF`.
- YouTube transcript retrieval requires `yt-dlp`, `requests`, and network access.
- Live-class transcription requires `ffmpeg`, `faster-whisper`, and a compatible
  Whisper model download/cache.
- Groq-backed note generation requires `GROQ_API_KEY` and network access.

## What to Verify After Documentation-Only Changes

- Python files still compile.
- FastAPI app imports successfully.
- `/health` still returns the same response shape.
- Public route paths and response models are unchanged.
- Added logging does not include secrets, full prompts, raw documents, transcripts,
  or generated notes.
