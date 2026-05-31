from fastapi import APIRouter, File, UploadFile, HTTPException, Form

from pydantic import BaseModel
from typing import Optional
import uuid

from app.schemas.common import LearnableNote
from app.storage.memory_store import create_session, get_session, add_chunk_to_session, update_session
from app.storage.file_storage import save_uploaded_file, save_text_file, save_json_file
from app.transcription.audio_utils import convert_to_wav_16k
from app.transcription.whisper_service import transcribe_audio
from app.services.note_generator import generate_learnable_note

router = APIRouter()


class StartSessionRequest(BaseModel):
    title: str
    subject: Optional[str] = None
    depth: str = "medium"  # "short" | "medium" | "deep"


class StartSessionResponse(BaseModel):
    session_id: str
    status: str
    finish_url: str


class FinishSessionResponse(BaseModel):
    session_id: str
    status: str
    transcript: Optional[str] = None
    note: Optional[LearnableNote] = None
    error: Optional[str] = None


@router.post("/start", response_model=StartSessionResponse)
async def start_live_class(req: StartSessionRequest):
    depth = req.depth if req.depth in {"short", "medium", "deep"} else "medium"
    session_id = str(uuid.uuid4())
    create_session(session_id, req.title, req.subject, depth)

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
    """
    Accepts the full recording as a single multipart file upload.
    The frontend records the entire session in memory and sends it here
    in one POST when the user clicks Stop.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not file:
        raise HTTPException(
            status_code=400,
            detail="No recording file received. The frontend must send the full recording as 'file'.",
        )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded recording is empty.")

        # Save the full recording blob
        filename = f"recording_{session_id}.webm"
        saved_path = save_uploaded_file(
            file_bytes,
            filename,
            subdir=f"audio/{session_id}",
        )

        # Convert directly to 16kHz mono WAV for Whisper
        wav_path = convert_to_wav_16k(saved_path)

        # Transcribe
        transcript = transcribe_audio(wav_path)
        transcript_path = save_text_file(transcript, f"{session_id}.txt", subdir="transcripts")

        # Generate notes
        note_dict = generate_learnable_note(
            transcript,
            "live_class",
            session["title"],
            session.get("subject"),
            session.get("depth", "medium"),
        )
        note_path = save_json_file(note_dict, f"{session_id}.json", subdir="notes")

        update_session(session_id, status="completed", transcript_path=transcript_path, note_path=note_path)

        try:
            note = LearnableNote(**note_dict)
        except Exception as parse_err:
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
        update_session(session_id, status="failed")
        return FinishSessionResponse(
            session_id=session_id,
            status="failed",
            error=str(exc),
        )