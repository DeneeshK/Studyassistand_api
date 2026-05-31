from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from app.config import settings


MAX_LLM_CHARS = 14000

STOPWORDS = {
    "about", "after", "again", "against", "also", "because", "before", "being",
    "between", "could", "during", "every", "first", "from", "have", "into",
    "just", "like", "more", "most", "other", "over", "same", "should", "some",
    "such", "than", "that", "their", "then", "there", "these", "they", "this",
    "through", "under", "using", "very", "what", "when", "where", "which",
    "while", "with", "would", "your",
}

# ── Per-depth system prompts ──────────────────────────────────────────────────

_SYSTEM_FAST = (
    "You are EduMind's Study Assistant.\n"
    "The student selected FAST mode. They want a quick, scannable overview.\n"
    "Rules:\n"
    "- overview: 2-3 sentences max.\n"
    "- sections: 2 sections, content is BULLET POINTS ONLY (no paragraphs).\n"
    "- key_takeaways: 4-5 tight bullet points.\n"
    "- short_revision_note: 2 sentences.\n"
    "- common_doubts: 2-3 short questions a learner would ask.\n"
    "- practice_questions: exactly 2.\n"
    "- mcqs: exactly 5. Each must be crisp and unambiguous.\n"
    "- flashcards: 5 front/back pairs.\n"
    "Return ONLY valid JSON. No markdown, no explanation, no backticks."
)

_SYSTEM_MEDIUM = (
    "You are EduMind's Study Assistant.\n"
    "The student selected MEDIUM depth. Build proper understanding.\n"
    "Rules:\n"
    "- overview: 3-4 sentences explaining the topic clearly.\n"
    "- sections: 3-4 sections. Each section has a clear heading, a concise prose\n"
    "  explanation (2-4 sentences), 3-5 key_terms, and one worked example where relevant.\n"
    "- key_takeaways: 5-6 important points.\n"
    "- short_revision_note: 3-4 sentences capturing the essence.\n"
    "- common_doubts: 3-4 questions students typically ask, with context.\n"
    "- practice_questions: 4-5 questions with detailed answers.\n"
    "- mcqs: exactly 5. Include explanation for the correct answer.\n"
    "- flashcards: 6-8 concept/definition pairs.\n"
    "Do not copy sentences verbatim from the source. Teach, do not transcribe.\n"
    "Return ONLY valid JSON. No markdown, no explanation, no backticks."
)

_SYSTEM_DEEP = (
    "You are EduMind's Study Assistant.\n"
    "The student selected DEEP mode. Build genuine mastery.\n"
    "Rules:\n"
    "- overview: 4-5 sentences that situate the topic in a broader context.\n"
    "- prerequisites: list of concepts the student should already know.\n"
    "- sections: 5-6 sections. Each needs:\n"
    "    • heading: descriptive, not just a keyword.\n"
    "    • content: 4-6 sentences of clear explanation with cause-effect reasoning.\n"
    "    • key_terms: 4-6 terms with brief inline definitions.\n"
    "    • example: a worked or real-world example that cements understanding.\n"
    "- key_takeaways: 6-8 points that a student must remember.\n"
    "- short_revision_note: a mini-paragraph (5-6 sentences) that could serve as\n"
    "  a standalone 60-second review.\n"
    "- common_doubts: 5-6 nuanced questions students commonly have, framed as doubts\n"
    "  (not just 'what is X'). If the source is a meeting/lecture, surface the actual\n"
    "  doubts raised by participants.\n"
    "- practice_questions: 6-8 questions that require understanding, not recall.\n"
    "  Answers must be thorough.\n"
    "- mcqs: exactly 5. Each option must be plausible (no throwaway wrong answers).\n"
    "  Explanation must justify why correct is correct AND why others are wrong.\n"
    "- flashcards: 10 pairs — mix of concept/definition, cause/effect, and\n"
    "  'what happens when' style.\n"
    "Do not transcribe. Analyze, synthesize, and teach.\n"
    "Return ONLY valid JSON. No markdown, no explanation, no backticks."
)

NOTE_SHAPE = """{
  "title": "string",
  "overview": "string",
  "prerequisites": ["string"],
  "sections": [{"heading": "string", "content": "string", "key_terms": ["string"], "example": "string or null"}],
  "key_takeaways": ["string"],
  "short_revision_note": "string",
  "common_doubts": ["string"],
  "practice_questions": [{"question": "string", "answer": "string"}],
  "mcqs": [{"question": "string", "options": [{"label": "A", "text": "string"}, {"label": "B", "text": "string"}, {"label": "C", "text": "string"}, {"label": "D", "text": "string"}], "answer": "A", "explanation": "string"}],
  "flashcards": [{"front": "string", "back": "string"}]
}"""

_SOURCE_HINTS: dict[str, str] = {
    "youtube": (
        "The source is a YouTube video transcript. "
        "Treat it as a lecture or tutorial. "
        "common_doubts should reflect questions a viewer watching this video might have."
    ),
    "pdf": (
        "The source is a PDF document. "
        "Treat it as study material or a textbook excerpt. "
        "Preserve technical accuracy."
    ),
    "live_class": (
        "The source is a live class or Google Meet recording transcript. "
        "The text may be informal, include filler words, or have speaker overlaps. "
        "Focus on the concepts taught, not the conversation style. "
        "common_doubts should surface actual questions raised by participants, or\n"
        "questions a student who attended this class would likely have."
    ),
}


def _system_prompt(depth: str) -> str:
    if depth == "short":
        return _SYSTEM_FAST
    if depth == "deep":
        return _SYSTEM_DEEP
    return _SYSTEM_MEDIUM


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?:\n+)", normalized)
    sentences = [part.strip(" -") for part in parts if len(part.strip()) > 20]
    if not sentences and normalized:
        return [normalized[:500]]
    return sentences


def _keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text or "")
    counter = Counter(
        word.lower()
        for word in words
        if word.lower() not in STOPWORDS and not word.isdigit()
    )
    return [word for word, _ in counter.most_common(limit)]


def _chunk_list(items: list[str], chunks: int) -> list[list[str]]:
    if not items:
        return []
    chunks = max(1, min(chunks, len(items)))
    size = max(1, (len(items) + chunks - 1) // chunks)
    return [items[index:index + size] for index in range(0, len(items), size)]


def _title_from_terms(text: str, fallback: str) -> str:
    terms = _keywords(text, 3)
    if not terms:
        return fallback
    return " ".join(term.capitalize() for term in terms)


def _section_heading(section_text: str, index: int) -> str:
    terms = _keywords(section_text, 3)
    if terms:
        return " ".join(term.capitalize() for term in terms)
    return f"Core Idea {index}"


def _depth_section_count(depth: str) -> int:
    if depth == "short":
        return 2
    if depth == "deep":
        return 5
    return 3


def _fallback_note(
    text: str,
    source_type: str,
    title: str | None,
    subject: str | None,
    depth: str = "medium",
) -> dict[str, Any]:
    """Pure-Python fallback when LLM is unavailable."""
    clean = _clean_text(text)
    source_label = source_type.replace("_", " ")
    note_title = title or _title_from_terms(clean, "Learnable Note")
    sentences = _sentences(clean)
    terms = _keywords(clean, 10)
    overview_sentences = sentences[:2] or [f"These notes summarize the provided {source_label} material."]
    section_groups = _chunk_list(sentences[:18], _depth_section_count(depth))

    sections = []
    for index, group in enumerate(section_groups, start=1):
        section_text = " ".join(group)
        content = section_text[:1200]
        if depth == "short":
            # Convert to bullet points for fast mode
            bullet_sentences = [s.strip() for s in group if len(s.strip()) > 10]
            content = "\n".join(f"• {s}" for s in bullet_sentences) or content
        sections.append({
            "heading": _section_heading(section_text, index),
            "content": content,
            "key_terms": _keywords(section_text, 5),
            "example": None,
        })

    if not sections:
        sections = [{
            "heading": subject or "Main Idea",
            "content": clean[:1200] or "No readable source text was available.",
            "key_terms": terms[:5],
            "example": None,
        }]

    takeaways = sentences[2:7] if len(sentences) > 2 else sentences[:4]
    if not takeaways and clean:
        takeaways = [clean[:220]]

    practice_questions = []
    for term in terms[:3]:
        practice_questions.append({
            "question": f"What role does {term} play in this material?",
            "answer": (
                f"{term.capitalize()} is one of the recurring ideas in the source. "
                "Review the sections above and connect it to the main explanation."
            ),
        })

    if not practice_questions:
        practice_questions = [{
            "question": "What is the central idea of this material?",
            "answer": "Use the overview and key takeaways to state the main idea in your own words.",
        }]

    answer_term = terms[0] if terms else "the main concept"
    distractors = terms[1:4] if len(terms) >= 4 else ["background detail", "unrelated topic", "minor example"]

    return {
        "title": note_title,
        "overview": " ".join(overview_sentences),
        "prerequisites": [subject] if subject else [],
        "sections": sections,
        "key_takeaways": takeaways[:6],
        "short_revision_note": " ".join(takeaways[:3])[:900],
        "common_doubts": [
            "Which ideas are definitions, and which are examples?",
            "How do the key terms connect to the overall topic?",
        ],
        "practice_questions": practice_questions,
        "mcqs": [{
            "question": "Which term best represents a central idea in these notes?",
            "options": [
                {"label": "A", "text": answer_term},
                {"label": "B", "text": distractors[0]},
                {"label": "C", "text": distractors[1]},
                {"label": "D", "text": distractors[2]},
            ],
            "answer": "A",
            "explanation": f"{answer_term} appears as a recurring key term in the provided material.",
        }],
        "flashcards": [
            {
                "front": f"What should you remember about {term}?",
                "back": f"{term.capitalize()} is a key term from the source material."
            }
            for term in terms[:5]
        ],
    }


def _extract_json_object(value: str) -> dict[str, Any]:
    value = re.sub(r"```(?:json)?", "", value).strip("`").strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_note(note: dict[str, Any], fallback_title: str) -> dict[str, Any]:
    normalized = {
        "title": note.get("title") or fallback_title,
        "overview": note.get("overview") or "",
        "prerequisites": note.get("prerequisites") or [],
        "sections": note.get("sections") or [],
        "key_takeaways": note.get("key_takeaways") or [],
        "short_revision_note": note.get("short_revision_note") or "",
        "common_doubts": note.get("common_doubts") or [],
        "practice_questions": note.get("practice_questions") or [],
        "mcqs": note.get("mcqs") or [],
        "flashcards": note.get("flashcards") or [],
    }

    normalized["sections"] = [
        {
            "heading": section.get("heading") or "Section",
            "content": section.get("content") or "",
            "key_terms": section.get("key_terms") or [],
            "example": section.get("example"),
        }
        for section in normalized["sections"]
        if isinstance(section, dict)
    ]

    normalized["practice_questions"] = [
        {
            "question": item.get("question") or "",
            "answer": item.get("answer") or "",
        }
        for item in normalized["practice_questions"]
        if isinstance(item, dict)
    ]

    normalized["mcqs"] = [
        {
            "question": item.get("question") or "",
            "options": item.get("options") or [],
            "answer": item.get("answer") or "",
            "explanation": item.get("explanation") or "",
        }
        for item in normalized["mcqs"]
        if isinstance(item, dict)
    ]

    normalized["flashcards"] = [
        {
            "front": item.get("front") or "",
            "back": item.get("back") or "",
        }
        for item in normalized["flashcards"]
        if isinstance(item, dict)
    ]

    return normalized


def _groq_note(
    text: str,
    source_type: str,
    title: str | None,
    subject: str | None,
    depth: str,
) -> dict[str, Any] | None:
    if not settings.GROQ_API_KEY:
        return None

    try:
        from groq import Groq
    except ImportError:
        return None

    fallback_title = title or "Learnable Note"
    source = _clean_text(text)[:MAX_LLM_CHARS]

    source_hint = _SOURCE_HINTS.get(source_type, "")

    user_prompt = f"""Create learnable study notes from the source text below.

Return only valid JSON with this exact shape:
{NOTE_SHAPE}

Source type: {source_type}
{source_hint}
Title: {fallback_title}
Subject: {subject or "Not specified"}
Depth: {depth}

Source text:
{source}
""".strip()

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _system_prompt(depth)},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        content = completion.choices[0].message.content or ""
        return _normalize_note(_extract_json_object(content), fallback_title)
    except Exception:
        return None


def generate_learnable_note(
    text: str,
    source_type: str,
    title: str | None = None,
    subject: str | None = None,
    depth: str = "medium",
) -> dict[str, Any]:
    depth = depth if depth in {"short", "medium", "deep"} else "medium"
    note = _groq_note(text, source_type, title, subject, depth)
    if note:
        return note
    return _fallback_note(text, source_type, title, subject, depth)


def generate_chunk_summary(
    text: str,
    source_type: str,
    title: str | None = None,
    subject: str | None = None,
) -> str:
    note = _groq_note(text, source_type, title, subject, "short")
    if note:
        parts = [note.get("overview", "")]
        parts.extend(note.get("key_takeaways", [])[:5])
        return " ".join(part for part in parts if part)

    sentences = _sentences(text)
    return " ".join(sentences[:6]) or _clean_text(text)[:1200]


def generate_final_note_from_chunk_summaries(
    summaries: list[str],
    title: str | None = None,
    subject: str | None = None,
    depth: str = "medium",
) -> dict[str, Any]:
    combined = "\n\n".join(summary for summary in summaries if summary)
    return generate_learnable_note(combined, "pdf", title, subject, depth)
