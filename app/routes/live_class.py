"""Routes for live-class recording transcription and note generation."""

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, HTTPException

from pydantic import BaseModel
from typing import Optional
import logging
import uuid

from app.schemas.common import LearnableNote
from app.storage.session_store import create_session, get_session, update_session
from app.storage.file_storage import (
    save_uploaded_file,
    save_text_file,
    save_json_file,
    load_text_file,
    load_json_file,
)
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


class FinishAcceptedResponse(BaseModel):
    """Response returned immediately after a recording is accepted for processing.

    Conversion, transcription, and note generation continue in the background;
    poll `GET /live-class/{session_id}/status` for the result.
    """

    session_id: str
    status: str
    status_url: str


class LiveClassStatusResponse(BaseModel):
    """Response returned when polling a live-class session's processing status."""

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


def _process_recording(
    session_id: str,
    saved_path: str,
    title: str,
    subject: Optional[str],
    depth: str,
) -> None:
    """Convert, transcribe, and generate a note for an uploaded recording.

    Runs as a background task after `/finish` has already returned its
    acknowledgement, so failures are only observable through the session's
    persisted status rather than an HTTP response.
    """
    try:
        wav_path = convert_to_wav_16k(saved_path)
        logger.info("Converted live-class recording session_id=%s", session_id)

        transcript = transcribe_audio(wav_path)
        transcript_path = save_text_file(transcript, f"{session_id}.txt", subdir="transcripts")
        logger.info("Transcribed live-class recording session_id=%s transcript_chars=%s", session_id, len(transcript))

        note_dict = generate_learnable_note(transcript, "live_class", title, subject, depth)
        try:
            note = LearnableNote(**note_dict)
        except Exception as parse_err:
            logger.warning(
                "Generated live-class note did not match response schema session_id=%s error_type=%s",
                session_id,
                parse_err.__class__.__name__,
            )
            note = LearnableNote(
                title=note_dict.get("title", title),
                overview=f"Note parsed with errors: {parse_err}",
                sections=[],
                practice_questions=[],
                mcqs=[],
                flashcards=[],
            )

        note_path = save_json_file(note.model_dump(), f"{session_id}.json", subdir="notes")
        logger.info("Generated live-class note session_id=%s", session_id)

        update_session(session_id, status="completed", transcript_path=transcript_path, note_path=note_path)
    except Exception as exc:
        logger.exception(
            "Live-class processing failed session_id=%s error_type=%s",
            session_id,
            exc.__class__.__name__,
        )
        update_session(session_id, status="failed", error=str(exc))


@router.post("/{session_id}/finish", response_model=FinishAcceptedResponse, status_code=202)
async def finish_live_class(
    session_id: str,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(default=None),
):
    """Accept a full live-class recording and process it in the background.

    The frontend records the full session and sends it as a single multipart
    upload when the user stops recording. This endpoint saves the recording
    and returns immediately; conversion, transcription, and note generation
    happen after the response is sent, since they can take longer than a
    typical proxy or gateway timeout allows for one request.

    Args:
        session_id: Existing live-class session identifier.
        background_tasks: Injected by FastAPI to schedule post-response work.
        file: Full recording file uploaded under the multipart `file` field.

    Returns:
        An acknowledgement with a `status_url` to poll for the transcript and
        note once processing finishes.

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

    file_bytes = await file.read()
    if not file_bytes:
        logger.warning("Live-class finish request contained empty recording session_id=%s", session_id)
        raise HTTPException(status_code=400, detail="Uploaded recording is empty.")

    # Persist the full recording before conversion so failures can be inspected.
    filename = f"recording_{session_id}.webm"
    saved_path = save_uploaded_file(file_bytes, filename, subdir=f"audio/{session_id}")
    logger.info("Saved live-class recording session_id=%s byte_count=%s", session_id, len(file_bytes))

    update_session(session_id, status="processing")
    background_tasks.add_task(
        _process_recording,
        session_id,
        saved_path,
        session["title"],
        session.get("subject"),
        session.get("depth", "medium"),
    )

    return FinishAcceptedResponse(
        session_id=session_id,
        status="processing",
        status_url=f"/live-class/{session_id}/status",
    )


@router.get("/{session_id}/status", response_model=LiveClassStatusResponse)
async def get_live_class_status(session_id: str):
    """Return the current processing status of a live-class session.

    Args:
        session_id: Existing live-class session identifier.

    Returns:
        The session's status, plus transcript and note once `status` is
        `completed`, or an error message once `status` is `failed`.

    Raises:
        HTTPException: If the session does not exist.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    status = session["status"]
    transcript = None
    note = None

    if status == "completed":
        if session.get("transcript_path"):
            transcript = load_text_file(session["transcript_path"])
        if session.get("note_path"):
            note = LearnableNote(**load_json_file(session["note_path"]))

    return LiveClassStatusResponse(
        session_id=session_id,
        status=status,
        transcript=transcript,
        note=note,
        error=session.get("error") if status == "failed" else None,
    )
