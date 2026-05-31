"""
app/routes/mcq.py

MCQ Generator endpoints — uses the fine-tuned DeepSeek R1 Distill LLaMA 8B
model and the Class 11 Physics knowledge graph.

Endpoints:
  GET  /mcq/chapters         — list valid chapter names
  POST /mcq/by-chapter       — generate MCQs from a chapter name / topic
  POST /mcq/by-pdf           — upload a PDF, match to a chapter, generate MCQs
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

# ── Ensure project root is on sys.path ───────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.mcq.graph_utils import (
    COVERAGE_NOTE,
    build_mcq_messages,
    format_mcq_response,
    get_chapter_edges,
    get_valid_chapters,
    parse_model_output,
    GRAPH_JSON,
)
from app.mcq.model_loader import generate_mcq_response, is_model_available

router = APIRouter()

MAX_QUESTIONS = 5
CONCEPT_CHROMA_PATH = str(_ROOT / "vector_stores" / "concept_chroma")
CONCEPT_COLLECTION  = "physics_concepts"


# ── Request / response schemas ────────────────────────────────────────────────

class ByChapterRequest(BaseModel):
    chapter: str
    topic: Optional[str] = None
    num_questions: int = 2
    difficulty: Optional[str] = "medium"


class MCQOption(BaseModel):
    label: str
    text: str


class MCQDistractor(BaseModel):
    value: str
    reason: str


class GeneratedMCQ(BaseModel):
    question: str
    options: list[MCQOption]
    correct_answer: str
    correct_label: str
    explanation: str
    formula_used: str
    unknown_solved: str
    distractors: list[MCQDistractor] = []
    edge_id: str = ""


class MCQResponse(BaseModel):
    chapter: str
    topic: str
    coverage_note: str
    mcqs: list[GeneratedMCQ]
    error: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp_questions(n: int) -> int:
    return max(1, min(n, MAX_QUESTIONS))


def _validate_chapter(chapter: str) -> tuple[bool, list[str]]:
    """Returns (is_valid, valid_chapters_list)."""
    valid = get_valid_chapters()
    return chapter in valid, valid


def _generate_n_mcqs(
    chapter: str,
    edges: list[dict],
    num_questions: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Generate num_questions MCQs for the given chapter edges.
    Returns (mcq_list, error_list).
    Each failed question is skipped with a warning logged.
    """
    mcqs:   list[dict[str, Any]] = []
    errors: list[str]            = []

    for i in range(num_questions):
        messages, chosen_edge, unknown, known_vals, equations = \
            build_mcq_messages(chapter, edges)

        response_text, gen_error = generate_mcq_response(
            messages, max_new_tokens=1200, temperature=0.2
        )

        if gen_error:
            errors.append(f"Q{i+1}: {gen_error}")
            continue

        parsed = parse_model_output(response_text or "")
        if not parsed:
            errors.append(f"Q{i+1}: Model output could not be parsed as JSON.")
            continue

        mcq = format_mcq_response(parsed, chosen_edge, unknown, equations)
        mcqs.append(mcq)

    return mcqs, errors


def _pdf_to_text(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF, page by page."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PyMuPDF is required for PDF matching. pip install pymupdf",
        )
    import io
    doc  = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return "\n".join(pages)


def _match_chapter_from_text(text: str) -> tuple[str | None, float]:
    """
    Query the concept ChromaDB with text, return (chapter_name, relevance).
    Returns (None, 0.0) if no match above threshold or ChromaDB unavailable.
    """
    try:
        import chromadb
    except ImportError:
        return None, 0.0

    chroma_path = Path(CONCEPT_CHROMA_PATH)
    if not chroma_path.exists():
        return None, 0.0

    try:
        client  = chromadb.PersistentClient(path=CONCEPT_CHROMA_PATH)
        col     = client.get_collection(CONCEPT_COLLECTION)
        results = col.query(
            query_texts=[text[:2000]],
            n_results=1,
            include=["metadatas", "distances"],
        )
    except Exception:
        return None, 0.0

    ids       = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    if not ids:
        return None, 0.0

    concept_id = ids[0]
    relevance  = round(1.0 - distances[0], 3)

    # Find the chapter this concept belongs to (from graph edges)
    try:
        import json as _json
        if not GRAPH_JSON.exists():
            return None, relevance
        with open(GRAPH_JSON, encoding="utf-8") as f:
            data = _json.load(f)
        for edge in data["edges"]:
            if edge.get("node_a") == concept_id or edge.get("node_b") == concept_id:
                chapter = edge.get("chapter", "").strip()
                if chapter:
                    return chapter, relevance
    except Exception:
        pass

    return None, relevance


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/chapters")
def list_chapters() -> dict:
    """List all valid chapter names available in the knowledge graph."""
    try:
        chapters = get_valid_chapters()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "chapters":      chapters,
        "coverage_note": COVERAGE_NOTE,
    }


@router.post("/by-chapter", response_model=MCQResponse)
def generate_by_chapter(req: ByChapterRequest) -> MCQResponse:
    """
    Generate MCQs from a chapter name.
    The topic (optional) refines which edge is selected.
    """
    # 1. Validate chapter
    is_valid, valid_chapters = _validate_chapter(req.chapter)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{req.chapter}' is not a recognised chapter. "
                f"Valid chapters: {valid_chapters}"
            ),
        )

    # 2. Check model
    ok, model_err = is_model_available()
    if not ok:
        return MCQResponse(
            chapter=req.chapter,
            topic=req.topic or req.chapter,
            coverage_note=COVERAGE_NOTE,
            mcqs=[],
            error=model_err,
        )

    # 3. Get edges
    try:
        edges = get_chapter_edges(req.chapter)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not edges:
        return MCQResponse(
            chapter=req.chapter,
            topic=req.topic or req.chapter,
            coverage_note=COVERAGE_NOTE,
            mcqs=[],
            error=f"No equations found for chapter '{req.chapter}' in the knowledge graph.",
        )

    # 4. Generate
    num_q = _clamp_questions(req.num_questions)
    topic = (req.topic or req.chapter).strip()
    mcqs, errors = _generate_n_mcqs(req.chapter, edges, num_q)

    error_summary = "; ".join(errors) if errors and not mcqs else None

    return MCQResponse(
        chapter=req.chapter,
        topic=topic,
        coverage_note=COVERAGE_NOTE,
        mcqs=[GeneratedMCQ(**m) for m in mcqs],
        error=error_summary,
    )


@router.post("/by-pdf")
async def generate_by_pdf(
    file: UploadFile = File(...),
    num_questions: int = Form(default=2),
) -> dict:
    """
    Upload a PDF. The text is matched against the concept knowledge graph
    to identify the most relevant chapter, then MCQs are generated.
    """
    # 1. Read file
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 2. Extract text
    try:
        text = _pdf_to_text(file_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {exc}")

    if not text.strip():
        return {
            "chapter":       None,
            "topic":         None,
            "coverage_note": COVERAGE_NOTE,
            "mcqs":          [],
            "error":         "No readable text found in the uploaded PDF.",
        }

    # 3. Match to chapter via concept ChromaDB
    SIMILARITY_THRESHOLD = 0.4
    chapter, relevance = _match_chapter_from_text(text)

    if not chapter or relevance < SIMILARITY_THRESHOLD:
        return {
            "chapter":       None,
            "topic":         None,
            "coverage_note": COVERAGE_NOTE,
            "mcqs":          [],
            "error": (
                "No matching physics concepts found in the uploaded PDF. "
                "This feature currently covers Class 11 Physics Part 1 only. "
                f"Best match relevance: {relevance:.2f} (threshold: {SIMILARITY_THRESHOLD})."
            ),
        }

    # 4. Check model
    ok, model_err = is_model_available()
    if not ok:
        return {
            "chapter":       chapter,
            "topic":         chapter,
            "coverage_note": COVERAGE_NOTE,
            "mcqs":          [],
            "error":         model_err,
        }

    # 5. Get edges and generate
    try:
        edges = get_chapter_edges(chapter)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not edges:
        return {
            "chapter":       chapter,
            "topic":         chapter,
            "coverage_note": COVERAGE_NOTE,
            "mcqs":          [],
            "error":         f"No equations found for matched chapter '{chapter}'.",
        }

    num_q = _clamp_questions(num_questions)
    mcqs, errors = _generate_n_mcqs(chapter, edges, num_q)

    error_summary = "; ".join(errors) if errors and not mcqs else None

    return {
        "chapter":       chapter,
        "topic":         chapter,
        "coverage_note": COVERAGE_NOTE,
        "matched_concept_relevance": relevance,
        "mcqs": [
            {
                "question":       m["question"],
                "options":        m["options"],
                "correct_answer": m["correct_answer"],
                "correct_label":  m["correct_label"],
                "explanation":    m["explanation"],
                "formula_used":   m["formula_used"],
                "unknown_solved": m["unknown_solved"],
                "distractors":    m["distractors"],
                "edge_id":        m["edge_id"],
            }
            for m in mcqs
        ],
        "error": error_summary,
    }
