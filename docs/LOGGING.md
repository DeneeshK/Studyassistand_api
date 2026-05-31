# Logging

## Logging Policy

Logging should help operators understand service workflow progress and failures
without exposing private content or secrets.

Safe log metadata includes:

- route or workflow name
- generated material/session identifiers
- source type
- depth value
- provider/model name
- page, chunk, section, or item counts
- status changes
- exception type and short error text

Do not log:

- API keys, tokens, passwords, or authorization headers
- full prompts or full LLM responses
- raw uploaded files or extracted document text
- YouTube transcript contents
- live-class transcripts
- generated lesson/note bodies
- database URLs or full environment dumps

## Logger Naming

Backend modules should use module-level loggers:

```python
import logging

logger = logging.getLogger(__name__)
```

## Level Guidance

| Level | Use |
| --- | --- |
| `debug` | Low-level diagnostics such as selected compute mode or sanitized file paths. |
| `info` | Normal workflow milestones such as request accepted, extraction complete, note generated, or session completed. |
| `warning` | Recoverable issues such as fallback note generation, missing captions, parse failures, scanned PDFs, or missing optional dependencies. |
| `error` | Failed operations where a stack trace is not useful. |
| `exception` | Exception handlers where a stack trace is useful for debugging. |

## Current Observability Points

The service should log major milestones for:

- startup storage initialization
- PDF upload, extraction, scanned-PDF detection, chunk summarization, and response generation
- YouTube URL rejection, caption lookup failure, transcript fetch/parsing issues, and note generation
- live-class session creation, recording upload, audio conversion, transcription, artifact save, and failure status
- Groq note generation attempts and fallback usage
- storage writes and session status updates

## Runtime Configuration

The application does not currently configure logging handlers or formatting.
Logging output is controlled by the ASGI server or deployment environment. For
local development, Uvicorn will display application logs when configured with an
appropriate log level.
