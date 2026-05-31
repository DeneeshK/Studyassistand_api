from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import uuid

from app.schemas.common import LearnableNote
from app.extraction.youtube_extractor import is_valid_youtube_url, fetch_youtube_transcript, clean_transcript
from app.services.note_generator import generate_learnable_note

router = APIRouter()

class YouTubeRequest(BaseModel):
    url: str
    title: Optional[str] = None
    subject: Optional[str] = None
    depth: str = "medium"  # "short" | "medium" | "deep"

class YouTubeNoteResponse(BaseModel):
    material_id: str
    source_type: str = "youtube"
    title: str
    video_url: str
    transcript_preview: Optional[str] = None
    note: Optional[LearnableNote] = None
    error: Optional[str] = None

@router.post("/learnable-note", response_model=YouTubeNoteResponse)
async def create_youtube_note(req: YouTubeRequest):
    if not is_valid_youtube_url(req.url):
        return YouTubeNoteResponse(
            material_id=str(uuid.uuid4()),
            title=req.title or "Invalid URL",
            video_url=req.url,
            error="Invalid YouTube URL format."
        )
    
    try:
        raw_transcript, fetched_title = fetch_youtube_transcript(req.url)
    except Exception as e:
        return YouTubeNoteResponse(
            material_id=str(uuid.uuid4()),
            title=req.title or "Unknown",
            video_url=req.url,
            error=str(e)
        )
    
    title = req.title or fetched_title or "YouTube Video"

    if not raw_transcript:
        return YouTubeNoteResponse(
            material_id=str(uuid.uuid4()),
            title=title,
            video_url=req.url,
            error="No transcript or subtitles found for this video. Audio transcription fallback is not implemented in this endpoint yet."
        )

    cleaned_text = clean_transcript(raw_transcript)
    
    note_dict = generate_learnable_note(cleaned_text, "youtube", title, req.subject, req.depth)
    
    try:
        note = LearnableNote(**note_dict)
    except Exception as e:
        note = LearnableNote(
            title=note_dict.get("title", title),
            overview=str(e),
            sections=[],
            practice_questions=[],
            mcqs=[],
            flashcards=[]
        )
        
    return YouTubeNoteResponse(
        material_id=str(uuid.uuid4()),
        title=title,
        video_url=req.url,
        transcript_preview=cleaned_text[:500] + "..." if len(cleaned_text) > 500 else cleaned_text,
        note=note
    )
