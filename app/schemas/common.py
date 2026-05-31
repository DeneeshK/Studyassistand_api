"""Shared Pydantic schemas returned by note-generation endpoints."""

from pydantic import BaseModel
from typing import List, Optional

class Section(BaseModel):
    """A teachable section within a generated learnable note."""

    heading: str
    content: str
    key_terms: List[str]
    example: Optional[str] = None

class PracticeQuestion(BaseModel):
    """A free-response practice question and its answer."""

    question: str
    answer: str

class MCQOption(BaseModel):
    """A labeled answer option for a multiple-choice question."""

    label: str
    text: str

class MCQ(BaseModel):
    """A multiple-choice question with options, answer, and explanation."""

    question: str
    options: List[MCQOption]
    answer: str
    explanation: str

class Flashcard(BaseModel):
    """A front/back flashcard pair for quick revision."""

    front: str
    back: str

class LearnableNote(BaseModel):
    """Structured note content shared by PDF, YouTube, and live-class endpoints."""

    title: str
    overview: str
    prerequisites: List[str] = []
    sections: List[Section] = []
    key_takeaways: List[str] = []
    short_revision_note: str = ""
    common_doubts: List[str] = []
    practice_questions: List[PracticeQuestion] = []
    mcqs: List[MCQ] = []
    flashcards: List[Flashcard] = []
