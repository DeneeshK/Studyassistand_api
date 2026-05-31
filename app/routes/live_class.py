"""Routes for live-class recording transcription and note generation."""

from fastapi import APIRouter, File, UploadFile, HTTPException, Form

from pydantic import BaseModel
from typing import Optional
import logging
import uuid

from app.schemas.common import LearnableNote
from app.storage.memory_store import create_session, get_session, add_chunk_to_session, update_session
from app.storage.file_storage import save_uploaded_file, save_text_file, save_json_file
from app.transcription.audio_utils import convert_to_wav_16k
from app.transcription.whisper_service import transcribe_audio
from app.services.note_generator import generate_learnable_note

logger = logging.getLogger(__name__)

router = APIRouter()


class StartSessionRequest(BaseModel):
    """Request body for starting a live-class recording session."""

    title: str
    subject: Optional[str] = None
    depth: str = "medium"  # "short" | "medium" | "deep"


class StartSessionResponse(BaseModel):
    """Response returned when a live-class session is created."""

    session_id: str
    status: str
    finish_url: str


class FinishSessionResponse(BaseModel):
    """Response returned after processing a live-class recording."""

    session_id: str
    status: str
    transcript: Optional[str] = None
    note: Optional[LearnableNote] = None
    error: Optional[str] = None


@router.post("/start", response_model=StartSessionResponse)
async def start_live_class(req: StartSessionRequest):
    """Create a live-class session and return the finish endpoint URL.

    Args:
        req: Session title, optional subject, and requested note depth.

    Returns:
        Session identifier, current status, and finish URL.
    """
    depth = req.depth if req.depth in {"short", "medium", "deep"} else "medium"
    session_id = str(uuid.uuid4())
    create_session(session_id, req.title, req.subject, depth)
    logger.info(
        "Started live-class session session_id=%s depth=%s subject_provided=%s",
        session_id,
        depth,
        req.subject is not None,
    )

    return StartSessionResponse(
        session_id=session_id,
        status="started",
        finish_url=f"/live-class/{session_id}/finish",
    )


@router.post("/{session_id}/finish", response_model=FinishSessionResponse)
async def finish_live_class(
    session_id: str,
    file: Optional[UploadFile] = File(default=None),
):
    """Process a full live-class recording and return transcript plus note.

    The frontend records the full session and sends it as a single multipart
    upload when the user stops recording.

    Args:
        session_id: Existing live-class session identifier.
        file: Full recording file uploaded under the multipart `file` field.

    Returns:
        Completed response with transcript and note, or a failed response with a
        user-facing error message when processing fails.

    Raises:
        HTTPException: If the session is missing, no file is provided, or the
        uploaded file is empty.
    """
    logger.info("Received live-class finish request session_id=%s file_present=%s", session_id, file is not None)
    session = get_session(session_id)
    if not session:
        logger.warning("Live-class finish requested for missing session session_id=%s", session_id)
        raise HTTPException(status_code=404, detail="Session not found.")

    if not file:
        logger.warning("Live-class finish request missing recording file session_id=%s", session_id)
        raise HTTPException(
            status_code=400,
            detail="No recording file received. The frontend must send the full recording as 'file'.",
        )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            logger.warning("Live-class finish request contained empty recording session_id=%s", session_id)
            raise HTTPException(status_code=400, detail="Uploaded recording is empty.")

        # Persist the full recording before conversion so failures can be inspected.
        filename = f"recording_{session_id}.webm"
        saved_path = save_uploaded_file(
            file_bytes,
            filename,
            subdir=f"audio/{session_id}",
        )
        logger.info("Saved live-class recording session_id=%s byte_count=%s", session_id, len(file_bytes))

        # Whisper expects a 16 kHz mono WAV input.
        wav_path = convert_to_wav_16k(saved_path)
        logger.info("Converted live-class recording session_id=%s", session_id)

        transcript = transcribe_audio(wav_path)
        transcript_path = save_text_file(transcript, f"{session_id}.txt", subdir="transcripts")
        logger.info("Transcribed live-class recording session_id=%s transcript_chars=%s", session_id, len(transcript))

        note_dict = generate_learnable_note(
            transcript,
            "live_class",
            session["title"],
            session.get("subject"),
            session.get("depth", "medium"),
        )
        note_path = save_json_file(note_dict, f"{session_id}.json", subdir="notes")
        logger.info("Generated live-class note session_id=%s", session_id)

        update_session(session_id, status="completed", transcript_path=transcript_path, note_path=note_path)

        try:
            note = LearnableNote(**note_dict)
        except Exception as parse_err:
            logger.warning(
                "Generated live-class note did not match response schema session_id=%s error_type=%s",
                session_id,
                parse_err.__class__.__name__,
            )
            note = LearnableNote(
                title=note_dict.get("title", session["title"]),
                overview=f"Note parsed with errors: {parse_err}",
                sections=[],
                practice_questions=[],
                mcqs=[],
                flashcards=[],
            )

        return FinishSessionResponse(
            session_id=session_id,
            status="completed",
            transcript=transcript,
            note=note,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Live-class processing failed session_id=%s error_type=%s",
            session_id,
            exc.__class__.__name__,
        )
        update_session(session_id, status="failed")
        return FinishSessionResponse(
            session_id=session_id,
            status="failed",
            error=str(exc),
        )
