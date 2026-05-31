from pydantic import BaseModel
from typing import List, Optional

class Section(BaseModel):
    heading: str
    content: str
    key_terms: List[str]
    example: Optional[str] = None

class PracticeQuestion(BaseModel):
    question: str
    answer: str

class MCQOption(BaseModel):
    label: str
    text: str

class MCQ(BaseModel):
    question: str
    options: List[MCQOption]
    answer: str
    explanation: str

class Flashcard(BaseModel):
    front: str
    back: str

class LearnableNote(BaseModel):
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
