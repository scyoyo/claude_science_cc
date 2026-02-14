"""
Smart context extraction for meeting chains (RAG-lite).

Replaces the naive "last assistant message" approach with keyword-based
paragraph extraction from previous meeting messages.
"""

import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Meeting, MeetingMessage


# Common English stop words to exclude from keyword extraction
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "about", "up", "what",
    "which", "who", "whom", "this", "that", "these", "those", "am", "i",
    "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
    "her", "it", "its", "they", "them", "their", "also", "use", "using",
})


def extract_keywords_from_agenda(
    agenda: str,
    questions: Optional[List[str]] = None,
) -> List[str]:
    """Extract domain-specific keywords from agenda text and questions.

    Splits on non-alphanumeric chars, lowercases, removes stop words,
    and returns unique keywords with length > 2.
    """
    text = agenda
    if questions:
        text += " " + " ".join(questions)

    tokens = re.findall(r"[a-zA-Z0-9_-]+", text.lower())
    keywords = []
    seen = set()
    for t in tokens:
        if len(t) > 2 and t not in _STOP_WORDS and t not in seen:
            keywords.append(t)
            seen.add(t)
    return keywords


def _split_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs (double-newline separated or markdown sections)."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _paragraph_matches(paragraph: str, keywords: List[str]) -> bool:
    """Check if a paragraph contains at least one keyword."""
    lower = paragraph.lower()
    return any(kw in lower for kw in keywords)


def extract_relevant_context(
    db: Session,
    meeting_ids: List[str],
    keywords: Optional[List[str]] = None,
    max_chars: int = 3000,
) -> List[dict]:
    """Extract relevant paragraphs from context meetings based on keywords.

    For each meeting in meeting_ids, find assistant messages whose paragraphs
    match the keywords. Falls back to last assistant message if no keyword match.

    Returns:
        List of {"title": str, "summary": str} dicts.
    """
    results = []
    chars_used = 0

    for mid in meeting_ids:
        if chars_used >= max_chars:
            break

        meeting = db.query(Meeting).filter(Meeting.id == mid).first()
        if not meeting:
            continue

        messages = db.query(MeetingMessage).filter(
            MeetingMessage.meeting_id == mid,
            MeetingMessage.role == "assistant",
        ).order_by(MeetingMessage.created_at).all()

        if not messages:
            continue

        if keywords:
            # Keyword-based extraction: collect matching paragraphs
            matched_parts = []
            for msg in messages:
                for para in _split_paragraphs(msg.content):
                    if _paragraph_matches(para, keywords):
                        matched_parts.append(para)

            if matched_parts:
                summary = "\n\n".join(matched_parts)
            else:
                # Fallback: last assistant message
                summary = messages[-1].content
        else:
            # No keywords: use last assistant message (legacy behavior)
            summary = messages[-1].content

        # Truncate to respect max_chars budget
        remaining = max_chars - chars_used
        if len(summary) > remaining:
            summary = summary[:remaining] + "..."

        results.append({
            "title": meeting.title,
            "summary": summary,
        })
        chars_used += len(summary)

    return results
