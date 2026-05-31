# EduMind Study Assistant API Reference

This app-local reference mirrors the implemented API. The canonical reference is
`docs/API_REFERENCE.md` at the repository root.

Base URL: `http://localhost:8100`

## GET /health

Returns service status, service name, and UTC timestamp.

## POST /pdf/short-note

Uploads a PDF and returns extraction metadata plus a `LearnableNote`.

Request content type: `multipart/form-data`

| Field | Required | Description |
| --- | --- | --- |
| `file` | Yes | PDF file. The filename must end with `.pdf`. |
| `title` | No | Optional title override. |
| `subject` | No | Optional subject hint. |
| `depth` | No | `short`, `medium`, or `deep`; defaults to `medium`. |

Likely scanned PDFs return `note: null` and an explanatory `error`; OCR is not
implemented.

## POST /youtube/learnable-note

Generates a note from available YouTube captions or subtitles.

Request content type: `application/json`

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "title": "Optional title",
  "subject": "Physics",
  "depth": "medium"
}
```

Invalid URLs, caption fetch failures, or videos without captions return the
normal response model with `note: null` and `error` populated.

## POST /live-class/start

Creates an in-memory live-class session.

```json
{
  "title": "Linear Algebra",
  "subject": "Mathematics",
  "depth": "medium"
}
```

Response:

```json
{
  "session_id": "uuid",
  "status": "started",
  "finish_url": "/live-class/{session_id}/finish"
}
```

## POST /live-class/{session_id}/finish

Accepts the full recording as a single multipart file upload, converts it to
16 kHz mono WAV, transcribes it with Faster Whisper, generates a note, and saves
transcript/note artifacts.

Request content type: `multipart/form-data`

| Field | Required | Description |
| --- | --- | --- |
| `file` | Yes | Full browser recording, typically WebM/Opus. |

The current backend does not implement `/live-class/{session_id}/audio-chunk`.

## Shared Note Shape

All note-producing endpoints return `LearnableNote`:

```json
{
  "title": "string",
  "overview": "string",
  "prerequisites": ["string"],
  "sections": [
    {
      "heading": "string",
      "content": "string",
      "key_terms": ["string"],
      "example": "string or null"
    }
  ],
  "key_takeaways": ["string"],
  "short_revision_note": "string",
  "common_doubts": ["string"],
  "practice_questions": [
    { "question": "string", "answer": "string" }
  ],
  "mcqs": [
    {
      "question": "string",
      "options": [
        { "label": "A", "text": "string" },
        { "label": "B", "text": "string" },
        { "label": "C", "text": "string" },
        { "label": "D", "text": "string" }
      ],
      "answer": "A",
      "explanation": "string"
    }
  ],
  "flashcards": [
    { "front": "string", "back": "string" }
  ]
}
```
