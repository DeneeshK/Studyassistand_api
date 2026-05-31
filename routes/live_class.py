from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from app.schemas.common import LearnableNote
from app.storage.memory_store import create_session, get_session, add_chunk_to_session, update_session
from app.storage.file_storage import save_uploaded_file, save_text_file, save_json_file
from app.transcription.audio_utils import combine_audio_chunks, convert_to_wav_16k
from app.transcription.whisper_service import transcribe_audio
from app.services.note_generator import generate_learnable_note

router = APIRouter()


class StartSessionRequest(BaseModel):
    title: str
    subject: Optional[str] = None


class StartSessionResponse(BaseModel):
    session_id: str
    status: str
    audio_upload_url: str
    finish_url: str


class ChunkUploadResponse(BaseModel):
    session_id: str
    chunk_received: bool
    chunk_count: int


class FinishSessionResponse(BaseModel):
    session_id: str
    status: str
    transcript: Optional[str] = None
    note: Optional[LearnableNote] = None
    error: Optional[str] = None


@router.post("/start", response_model=StartSessionResponse)
async def start_live_class(req: StartSessionRequest):
    session_id = str(uuid.uuid4())
    create_session(session_id, req.title, req.subject)

    return StartSessionResponse(
        session_id=session_id,
        status="started",
        audio_upload_url=f"/live-class/{session_id}/audio-chunk",
        finish_url=f"/live-class/{session_id}/finish",
    )


@router.post("/{session_id}/audio-chunk", response_model=ChunkUploadResponse)
async def upload_audio_chunk(session_id: str, file: UploadFile = File(...)):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Call /live-class/start first.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded chunk is empty.")

    # Determine chunk index from current count for stable ordering
    current_count = len(session.get("audio_chunks", []))
    chunk_filename = f"chunk_{current_count:04d}.webm"

    saved_path = save_uploaded_file(
        file_bytes,
        chunk_filename,
        subdir=f"audio/{session_id}",
    )

    chunk_count = add_chunk_to_session(session_id, saved_path)

    return ChunkUploadResponse(
        session_id=session_id,
        chunk_received=True,
        chunk_count=chunk_count,
    )


@router.post("/{session_id}/finish", response_model=FinishSessionResponse)
async def finish_live_class(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    chunks = session.get("audio_chunks", [])
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No audio chunks were uploaded for this session. Record some audio before finishing.",
        )

    try:
        combined_audio = combine_audio_chunks(session_id)
        wav_audio = convert_to_wav_16k(combined_audio)

        transcript = transcribe_audio(wav_audio)
        transcript_path = save_text_file(transcript, f"{session_id}.txt", subdir="transcripts")

        note_dict = generate_learnable_note(
            transcript,
            "live_class",
            session["title"],
            session.get("subject"),
            "deep",
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

    except Exception as exc:
        update_session(session_id, status="failed")
        return FinishSessionResponse(
            session_id=session_id,
            status="failed",
            error=str(exc),
        )
