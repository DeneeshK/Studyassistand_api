# EduMind Study Assistant API — Reference

Base URL: `http://localhost:8100`

All endpoints return JSON. Swagger UI: `http://localhost:8100/docs`

---

## GET /health

Health check.

**Response:**
```json
{
  "status": "ok",
  "service": "EduMind Study Assistant API",
  "timestamp": "2026-05-24T10:00:00+00:00"
}
```

---

## POST /pdf/short-note

Upload a PDF and receive a structured learnable note.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | ✅ | PDF file to process |
| `title` | string | ❌ | Override the note title |
| `subject` | string | ❌ | Subject hint (e.g. "Physics") |
| `depth` | string | ❌ | `short` / `medium` / `deep` (default: `medium`) |

**Response:**
```json
{
  "material_id": "uuid",
  "source_type": "pdf",
  "title": "Chapter 5 — Newton's Laws",
  "extraction": {
    "total_pages": 12,
    "successful_pages": 11,
    "failed_pages": [],
    "low_text_pages": [3],
    "is_probably_scanned": false,
    "char_count": 14200
  },
  "note": { ... },
  "error": null
}
```

If the PDF is scanned/image-based, `note` is null and `error` explains why.

---

## POST /youtube/learnable-note

Paste a YouTube URL and get a learnable note from its transcript/subtitles.

**Request:** `application/json`
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "title": "Optional override title",
  "subject": "Physics",
  "depth": "medium"
}
```

**Response:**
```json
{
  "material_id": "uuid",
  "source_type": "youtube",
  "title": "Video title",
  "video_url": "https://...",
  "transcript_preview": "First 500 chars of transcript...",
  "note": { ... },
  "error": null
}
```

If no transcript is available, `note` is null and `error` explains why.

---

## POST /live-class/start

Create a new live class recording session.

**Request:** `application/json`
```json
{
  "title": "Linear Algebra — Eigenvalues",
  "subject": "Mathematics"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "started",
  "audio_upload_url": "/live-class/{session_id}/audio-chunk",
  "finish_url": "/live-class/{session_id}/finish"
}
```

---

## POST /live-class/{session_id}/audio-chunk

Upload one audio chunk (WebM/Opus) captured from the browser.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | ✅ | WebM audio blob from MediaRecorder |

**Response:**
```json
{
  "session_id": "uuid",
  "chunk_received": true,
  "chunk_count": 5
}
```

---

## POST /live-class/{session_id}/finish

Stop the session, combine all chunks, transcribe, and generate a note.

**Request:** No body needed.

**Response:**
```json
{
  "session_id": "uuid",
  "status": "completed",
  "transcript": "Full transcribed text...",
  "note": { ... },
  "error": null
}
```

If processing fails, `status` is `"failed"` and `error` contains the reason.

---

## Learnable Note shape

All three features return a note in this shape:

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
        {"label": "A", "text": "string"},
        {"label": "B", "text": "string"},
        {"label": "C", "text": "string"},
        {"label": "D", "text": "string"}
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
