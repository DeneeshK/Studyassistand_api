# API Reference

Base URL for local development: `http://localhost:8100`

Interactive OpenAPI documentation is available at `http://localhost:8100/docs`
when the server is running.

## GET /health

Returns service status and a UTC timestamp.

### Response

```json
{
  "status": "ok",
  "service": "EduMind Study Assistant API",
  "timestamp": "2026-05-31T10:00:00+00:00"
}
```

## POST /pdf/short-note

Uploads a text-based PDF and returns extraction metadata plus a generated
learnable note.

### Request

Content type: `multipart/form-data`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `file` | file | Yes | PDF file to process. The filename must end with `.pdf`. |
| `title` | string | No | Optional note title override. |
| `subject` | string | No | Optional subject hint passed to note generation. |
| `depth` | string | No | `short`, `medium`, or `deep`. Defaults to `medium`. |

### Success Response

```json
{
  "material_id": "uuid",
  "source_type": "pdf",
  "title": "Chapter 5",
  "extraction": {
    "total_pages": 12,
    "successful_pages": 12,
    "failed_pages": [],
    "low_text_pages": [],
    "is_probably_scanned": false,
    "char_count": 14200
  },
  "note": {
    "title": "Chapter 5",
    "overview": "string",
    "prerequisites": [],
    "sections": [],
    "key_takeaways": [],
    "short_revision_note": "string",
    "common_doubts": [],
    "practice_questions": [],
    "mcqs": [],
    "flashcards": []
  },
  "error": null
}
```

### Error Cases

- Non-PDF filenames raise `400` with `Uploaded file must be a PDF`.
- Likely scanned/image-only PDFs return `200` with `note: null`,
  `is_probably_scanned: true`, and an explanatory `error`.
- Note parsing failures return a fallback `LearnableNote` with the parsing error
  in `overview`; the HTTP response remains successful.

## POST /youtube/learnable-note

Fetches available YouTube captions/subtitles and returns a learnable note.

### Request

Content type: `application/json`

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "title": "Optional title",
  "subject": "Physics",
  "depth": "medium"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `url` | string | Yes | YouTube watch, shorts, embed, live, or `youtu.be` URL. |
| `title` | string | No | Optional note title override. |
| `subject` | string | No | Optional subject hint passed to note generation. |
| `depth` | string | No | `short`, `medium`, or `deep`. Defaults to `medium`. |

### Success Response

```json
{
  "material_id": "uuid",
  "source_type": "youtube",
  "title": "Video title",
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "transcript_preview": "First part of the cleaned transcript...",
  "note": {
    "title": "Video title",
    "overview": "string",
    "prerequisites": [],
    "sections": [],
    "key_takeaways": [],
    "short_revision_note": "string",
    "common_doubts": [],
    "practice_questions": [],
    "mcqs": [],
    "flashcards": []
  },
  "error": null
}
```

### Error Response Shape

The endpoint returns the same response model with `note: null` and `error`
populated for invalid URLs, transcript fetch failures, or videos with no
captions/subtitles.

## POST /live-class/start

Creates a durable live-class session, persisted to `STORAGE_DIR/sessions.db`.

### Request

Content type: `application/json`

```json
{
  "title": "Linear Algebra",
  "subject": "Mathematics",
  "depth": "medium"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `title` | string | Yes | Session title and fallback note title. |
| `subject` | string | No | Optional subject hint passed to note generation. |
| `depth` | string | No | `short`, `medium`, or `deep`; unsupported values are stored as `medium`. |

### Response

```json
{
  "session_id": "uuid",
  "status": "started",
  "finish_url": "/live-class/{session_id}/finish"
}
```

## POST /live-class/{session_id}/finish

Accepts the full live-class recording as one multipart upload and saves it,
then returns immediately with `202 Accepted`. Conversion, transcription, and
note generation continue in a background task after the response is sent —
poll `GET /live-class/{session_id}/status` for the result. This endpoint does
not block for the duration of transcription, since that can take minutes for
a longer recording and would otherwise risk being killed by a proxy or
gateway timeout on one long-held request.

### Request

Content type: `multipart/form-data`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `file` | file | Yes | Full browser recording, typically WebM/Opus. |

### Response — `202 Accepted`

```json
{
  "session_id": "uuid",
  "status": "processing",
  "status_url": "/live-class/{session_id}/status"
}
```

### Error Cases

- Unknown sessions raise `404` with `Session not found.`
- Missing `file` raises `400` with a message explaining that the recording file
  must be sent as `file`.
- Empty uploads raise `400` with `Uploaded recording is empty.`

## GET /live-class/{session_id}/status

Returns the current processing status of a live-class session. Poll this
after `/finish` returns `202` until `status` is `completed` or `failed`.

### Response

```json
{
  "session_id": "uuid",
  "status": "processing",
  "transcript": null,
  "note": null,
  "error": null
}
```

`status` is one of `started`, `processing`, `completed`, or `failed`.
`transcript` and `note` are populated once `status` is `completed`; `error` is
populated once `status` is `failed`. Unknown sessions raise `404` with
`Session not found.`

## Shared LearnableNote Shape

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
    {
      "question": "string",
      "answer": "string"
    }
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
    {
      "front": "string",
      "back": "string"
    }
  ]
}
```
