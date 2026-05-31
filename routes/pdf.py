from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid

from app.schemas.common import LearnableNote
from app.extraction.pdf_extractor import extract_pdf_text_streaming, clean_extracted_text, iter_pdf_text_chunks
from app.services.note_generator import generate_learnable_note, generate_chunk_summary, generate_final_note_from_chunk_summaries
from app.storage.file_storage import save_uploaded_file

router = APIRouter()

class FailedPage(BaseModel):
    page_number: int
    error: str

class ExtractionMetadata(BaseModel):
    total_pages: int
    successful_pages: int
    failed_pages: List[FailedPage]
    low_text_pages: List[int]
    is_probably_scanned: bool
    char_count: int

class PDFNoteResponse(BaseModel):
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
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF")
    
    file_bytes = await file.read()
    material_id = str(uuid.uuid4())
    filename = f"{material_id}.pdf"
    saved_path = save_uploaded_file(file_bytes, filename)
    
    extraction_result = extract_pdf_text_streaming(saved_path)
    
    metadata = ExtractionMetadata(
        total_pages=extraction_result["total_pages"],
        successful_pages=extraction_result["successful_pages"],
        failed_pages=extraction_result["failed_pages"],
        low_text_pages=extraction_result["low_text_pages"],
        is_probably_scanned=extraction_result["is_probably_scanned"],
        char_count=extraction_result["char_count"]
    )
    
    if metadata.is_probably_scanned:
        return PDFNoteResponse(
            material_id=material_id,
            title=title or file.filename,
            extraction=metadata,
            error="This PDF appears to be scanned or image-based. OCR is not implemented in this MVP."
        )
    
    cleaned_text = clean_extracted_text(extraction_result["text"])
    
    if metadata.char_count > 8000:
        # Long PDF
        summaries = []
        for chunk in iter_pdf_text_chunks(saved_path):
            chunk_summary = generate_chunk_summary(chunk["text"], "pdf", title, subject)
            summaries.append(chunk_summary)
        
        note_dict = generate_final_note_from_chunk_summaries(summaries, title or file.filename, subject, depth)
    else:
        # Short PDF
        note_dict = generate_learnable_note(cleaned_text, "pdf", title or file.filename, subject, depth)
    
    # Parse dict into LearnableNote
    try:
        note = LearnableNote(**note_dict)
    except Exception as e:
        note = LearnableNote(
            title=note_dict.get("title", "Error Parsing Note"),
            overview=str(e),
            sections=[],
            practice_questions=[],
            mcqs=[],
            flashcards=[]
        )

    return PDFNoteResponse(
        material_id=material_id,
        title=title or file.filename,
        extraction=metadata,
        note=note
    )
