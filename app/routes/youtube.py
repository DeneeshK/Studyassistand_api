"""Routes for generating study notes from YouTube captions."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import logging
import uuid

from app.schemas.common import LearnableNote
from app.extraction.youtube_extractor import is_valid_youtube_url, fetch_youtube_transcript, clean_transcript
from app.services.note_generator import generate_learnable_note

logger = logging.getLogger(__name__)

router = APIRouter()

class YouTubeRequest(BaseModel):
    """Request body for generating a note from a YouTube video transcript."""

    url: str
    title: Optional[str] = None
    subject: Optional[str] = None
    depth: str = "medium"  # "short" | "medium" | "deep"

class YouTubeNoteResponse(BaseModel):
    """Response returned after YouTube transcript lookup and note generation."""

    material_id: str
    source_type: str = "youtube"
    title: str
    video_url: str
    transcript_preview: Optional[str] = None
    note: Optional[LearnableNote] = None
    error: Optional[str] = None

@router.post("/learnable-note", response_model=YouTubeNoteResponse)
async def create_youtube_note(req: YouTubeRequest):
    """Generate a learnable note from a YouTube video's available captions.

    Args:
        req: YouTube URL and optional note-generation hints.

    Returns:
        A response containing the transcript preview, generated note, or a
        user-facing error message when captions cannot be used.
    """
    logger.info(
        "Received YouTube note request depth=%s title_provided=%s subject_provided=%s",
        req.depth,
        req.title is not None,
        req.subject is not None,
    )
    if not is_valid_youtube_url(req.url):
        logger.warning("Rejected YouTube note request because URL format is invalid")
        return YouTubeNoteResponse(
            material_id=str(uuid.uuid4()),
            title=req.title or "Invalid URL",
            video_url=req.url,
            error="Invalid YouTube URL format."
        )
    
    try:
        raw_transcript, fetched_title = fetch_youtube_transcript(req.url)
    except Exception as e:
        logger.warning(
            "Failed to fetch YouTube transcript error_type=%s",
            e.__class__.__name__,
        )
        return YouTubeNoteResponse(
            material_id=str(uuid.uuid4()),
            title=req.title or "Unknown",
            video_url=req.url,
            error=str(e)
        )
    
    title = req.title or fetched_title or "YouTube Video"

    if not raw_transcript:
        logger.warning("YouTube transcript was unavailable title_available=%s", fetched_title is not None)
        return YouTubeNoteResponse(
            material_id=str(uuid.uuid4()),
            title=title,
            video_url=req.url,
            error="No transcript or subtitles found for this video. Audio transcription fallback is not implemented in this endpoint yet."
        )

    cleaned_text = clean_transcript(raw_transcript)
    logger.info("Generating YouTube note transcript_chars=%s", len(cleaned_text))
    
    note_dict = generate_learnable_note(cleaned_text, "youtube", title, req.subject, req.depth)
    
    try:
        note = LearnableNote(**note_dict)
    except Exception as e:
        logger.warning(
            "Generated YouTube note did not match response schema error_type=%s",
            e.__class__.__name__,
        )
        note = LearnableNote(
            title=note_dict.get("title", title),
            overview=str(e),
            sections=[],
            practice_questions=[],
            mcqs=[],
            flashcards=[]
        )
        
    logger.info("Completed YouTube note request note_available=%s", note is not None)
    return YouTubeNoteResponse(
        material_id=str(uuid.uuid4()),
        title=title,
        video_url=req.url,
        transcript_preview=cleaned_text[:500] + "..." if len(cleaned_text) > 500 else cleaned_text,
        note=note
    )
