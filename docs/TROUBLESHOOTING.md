# Troubleshooting

## Server Does Not Start

Check that dependencies are installed:

```bash
pip install -r app/requirements.txt
```

Confirm the command is run from the repository root:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

## PDF Upload Returns "Uploaded file must be a PDF"

The endpoint checks the uploaded filename and requires it to end with `.pdf`.
Rename the file or confirm the client is sending the original PDF filename.

## PDF Returns Scanned/Image-Based Error

The extractor found too little text relative to the number of pages. OCR is not
implemented, so scanned documents need to be converted to text before upload.

## YouTube Note Returns No Transcript

The video may not have manual or automatic captions available. The current
endpoint does not download audio and transcribe YouTube videos.

## YouTube Fetch Fails

Confirm:

- the URL is a supported YouTube URL form
- network access is available
- `yt-dlp` is installed
- the video is public and accessible from the server environment

## Live-Class Finish Returns Session Not Found

Live-class sessions are stored in memory. Restarting the API clears all sessions.
Start a new session and use the returned `session_id`.

## Live-Class Finish Says No Recording File Was Received

Send a multipart form field named `file` to:

```text
POST /live-class/{session_id}/finish
```

The current backend expects the full recording at finish time.

## ffmpeg Errors

Install `ffmpeg` and confirm it is visible on `PATH`:

```bash
ffmpeg -version
```

If the command works but conversion still fails, verify that the uploaded file is
a valid audio/video recording format supported by your `ffmpeg` build.

## No Speech Was Transcribed

The uploaded recording may be silent, too short, or missing the intended audio
track. For browser tab capture, ensure the user selected the source tab and
enabled tab audio sharing.

## Notes Look Less Detailed Than Expected

Check whether `GROQ_API_KEY` is configured. Without a provider key, the service
uses its deterministic fallback generator, which is intentionally simpler than
LLM-generated notes.

## Storage Files Appear in Unexpected Locations

`STORAGE_DIR` is relative to the process working directory unless set to an
absolute path. Start the API from the repository root or set an absolute
`STORAGE_DIR`.
