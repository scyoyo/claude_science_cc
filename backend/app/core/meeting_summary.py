"""Generate and cache meeting summaries. Used when meeting completes and on first GET /summary."""

from sqlalchemy.orm import Session

from app.models import Meeting, MeetingMessage
from app.core.llm_client import resolve_llm_call, LLMQuotaError
from app.schemas.onboarding import ChatMessage


def _parse_summary_llm_response(text: str) -> tuple[str | None, list[str]]:
    """Parse LLM response with SUMMARY: and KEY_POINTS: sections."""
    summary_text: str | None = None
    key_points: list[str] = []
    if not text or not text.strip():
        return summary_text, key_points
    upper = text.upper()
    summary_start = upper.find("SUMMARY:")
    kp_start = upper.find("KEY_POINTS:")
    if summary_start >= 0:
        end = kp_start if kp_start >= 0 else len(text)
        summary_text = text[summary_start + 8 : end].strip()
        if summary_text:
            summary_text = summary_text.strip()
    if kp_start >= 0:
        block = text[kp_start + 11 :].strip()
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                line = line[1:].strip()
            if line:
                key_points.append(line)
    return summary_text or None, key_points


def generate_summary_for_meeting(meeting: Meeting, messages: list, db: Session) -> tuple[str | None, list]:
    """Generate summary_text and key_points for a meeting (LLM or fallback). Does not write to DB."""
    key_points = []
    seen = set()
    for m in messages:
        if m.role != "assistant" or not m.content:
            continue
        first_line = m.content.strip().split("\n")[0].strip()
        first_sentence = m.content.split(".")[0].strip()
        if first_sentence.startswith("```") or first_sentence.startswith("#"):
            continue
        if first_line.startswith("```") or first_line.startswith("#"):
            continue
        if len(first_sentence) < 15 or len(first_sentence) > 300:
            continue
        if first_sentence in seen:
            continue
        seen.add(first_sentence)
        key_points.append(f"[{m.agent_name or 'Agent'}] {first_sentence}")

    summary_text: str | None = None
    try:
        llm_call = resolve_llm_call(db)
    except Exception:
        llm_call = None
    if llm_call and messages:
        transcript = "\n\n".join(
            f"[Round {m.round_number}] {m.agent_name or m.role}: {m.content}" for m in messages
        )
        if len(transcript) > 12000:
            transcript = transcript[:12000] + "\n\n[... truncated for summary ...]"
        system = (
            "You are a meeting summarizer. Output exactly two sections: SUMMARY: (one short paragraph, 2-4 sentences), "
            "then KEY_POINTS: (3-7 bullet items, each on a new line starting with '- '). "
            "Use the same language as the meeting content when possible."
        )
        user_content = f"Meeting title: {meeting.title}\n\nTranscript:\n{transcript}\n\nProvide SUMMARY: and KEY_POINTS: as described."
        try:
            response = llm_call(system, [ChatMessage(role="user", content=user_content)])
            parsed_summary, parsed_points = _parse_summary_llm_response(response)
            if parsed_summary:
                summary_text = parsed_summary
            if parsed_points:
                key_points = parsed_points
        except (LLMQuotaError, Exception):
            pass
    return summary_text, key_points


def ensure_meeting_summary_cached(meeting_id: str, db: Session) -> None:
    """If the meeting has no cached summary, generate and save it. Call when meeting completes."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        return
    if getattr(meeting, "cached_summary_text", None) is not None:
        return
    if getattr(meeting, "cached_key_points", None) and len(meeting.cached_key_points) > 0:
        return
    messages = (
        db.query(MeetingMessage)
        .filter(MeetingMessage.meeting_id == meeting_id)
        .order_by(MeetingMessage.created_at)
        .all()
    )
    summary_text, key_points = generate_summary_for_meeting(meeting, messages, db)
    meeting.cached_summary_text = summary_text
    meeting.cached_key_points = key_points
    db.commit()
