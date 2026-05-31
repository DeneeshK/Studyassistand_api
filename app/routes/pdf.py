"""Routes for generating study notes from uploaded PDF files."""

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging
import uuid

from app.schemas.common import LearnableNote
from app.extraction.pdf_extractor import extract_pdf_text_streaming, clean_extracted_text, iter_pdf_text_chunks
from app.services.note_generator import generate_learnable_note, generate_chunk_summary, generate_final_note_from_chunk_summaries
from app.storage.file_storage import save_uploaded_file

logger = logging.getLogger(__name__)

router = APIRouter()

class FailedPage(BaseModel):
    """Metadata for a PDF page that could not be extracted."""

    page_number: int
    error: str

class ExtractionMetadata(BaseModel):
    """Aggregated PDF extraction metadata returned with PDF note responses."""

    total_pages: int
    successful_pages: int
    failed_pages: List[FailedPage]
    low_text_pages: List[int]
    is_probably_scanned: bool
    char_count: int

class PDFNoteResponse(BaseModel):
    """Response returned after PDF extraction and note generation."""

    material_id: str
    source_type: str = "pdf"
    title: str
    extraction: ExtractionMetadata
    note: Optional[LearnableNote] = None
    error: Optional[str] = None

@router.post("/short-note", response_model=PDFNoteResponse)
async def create_pdf_short_note(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    depth: str = Form("medium")
):
    """Upload a PDF, extract text, and return a generated learnable note.

    Args:
        file: Uploaded PDF file.
        title: Optional note title override.
        subject: Optional subject hint for note generation.
        depth: Requested note depth.

    Returns:
        Extraction metadata plus a generated note, or a scanned-PDF error
        response when the document appears image-based.

    Raises:
        HTTPException: If the uploaded filename does not end with `.pdf`.
    """
    if not file.filename.endswith(".pdf"):
        logger.warning("Rejected PDF note request because filename is not a PDF")
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF")
    
    file_bytes = await file.read()
    material_id = str(uuid.uuid4())
    logger.info(
        "Received PDF note request material_id=%s byte_count=%s depth=%s subject_provided=%s",
        material_id,
        len(file_bytes),
        depth,
        subject is not None,
    )
    filename = f"{material_id}.pdf"
    saved_path = save_uploaded_file(file_bytes, filename)
    
    extraction_result = extract_pdf_text_streaming(saved_path)
    logger.info(
        "Completed PDF extraction material_id=%s total_pages=%s successful_pages=%s char_count=%s",
        material_id,
        extraction_result["total_pages"],
        extraction_result["successful_pages"],
        extraction_result["char_count"],
    )
    
    metadata = ExtractionMetadata(
        total_pages=extraction_result["total_pages"],
        successful_pages=extraction_result["successful_pages"],
        failed_pages=extraction_result["failed_pages"],
        low_text_pages=extraction_result["low_text_pages"],
        is_probably_scanned=extraction_result["is_probably_scanned"],
        char_count=extraction_result["char_count"]
    )
    
    if metadata.is_probably_scanned:
        logger.warning(
            "PDF appears scanned material_id=%s total_pages=%s char_count=%s",
            material_id,
            metadata.total_pages,
            metadata.char_count,
        )
        return PDFNoteResponse(
            material_id=material_id,
            title=title or file.filename,
            extraction=metadata,
            error="This PDF appears to be scanned or image-based. OCR is not implemented in this MVP."
        )
    
    cleaned_text = clean_extracted_text(extraction_result["text"])
    
    if metadata.char_count > 8000:
        # Long PDFs are summarized in chunks before the final note is generated.
        summaries = []
        for chunk in iter_pdf_text_chunks(saved_path):
            chunk_summary = generate_chunk_summary(chunk["text"], "pdf", title, subject)
            summaries.append(chunk_summary)
        logger.info("Generated PDF chunk summaries material_id=%s chunk_count=%s", material_id, len(summaries))
        
        note_dict = generate_final_note_from_chunk_summaries(summaries, title or file.filename, subject, depth)
    else:
        # Short PDFs can be sent to the normal note-generation pipeline directly.
        note_dict = generate_learnable_note(cleaned_text, "pdf", title or file.filename, subject, depth)
    
    # Keep response serialization stable even if the generated note is malformed.
    try:
        note = LearnableNote(**note_dict)
    except Exception as e:
        logger.warning(
            "Generated PDF note did not match response schema material_id=%s error_type=%s",
            material_id,
            e.__class__.__name__,
        )
        note = LearnableNote(
            title=note_dict.get("title", "Error Parsing Note"),
            overview=str(e),
            sections=[],
            practice_questions=[],
            mcqs=[],
            flashcards=[]
        )

    logger.info("Completed PDF note request material_id=%s", material_id)
    return PDFNoteResponse(
        material_id=material_id,
        title=title or file.filename,
        extraction=metadata,
        note=note
    )
