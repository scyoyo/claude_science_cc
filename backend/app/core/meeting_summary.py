"""Generate and cache meeting summaries. Per-round summaries are auto-generated after each round."""

from sqlalchemy.orm import Session

from app.models import Meeting, MeetingMessage
from app.core.llm_client import resolve_llm_call, LLMQuotaError
from app.schemas.onboarding import ChatMessage


def generate_summary_for_round(
    meeting: Meeting,
    messages: list,
    db: Session,
) -> tuple[str | None, list[str]]:
    """Generate summary_text and key_points for a single round. Does not write to DB."""
    key_points = []
    seen = set()
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        agent_name = m.get("agent_name") if isinstance(m, dict) else getattr(m, "agent_name", None)
        if role != "assistant" or not content:
            continue
        first_line = content.strip().split("\n")[0].strip()
        first_sentence = content.split(".")[0].strip()
        if first_sentence.startswith("```") or first_sentence.startswith("#"):
            continue
        if first_line.startswith("```") or first_line.startswith("#"):
            continue
        if len(first_sentence) < 15 or len(first_sentence) > 300:
            continue
        if first_sentence in seen:
            continue
        seen.add(first_sentence)
        key_points.append(f"[{agent_name or 'Agent'}] {first_sentence}")

    summary_text: str | None = None
    try:
        llm_call = resolve_llm_call(db)
    except Exception:
        llm_call = None
    if llm_call and messages:
        def _agent(m):
            return (m.get("agent_name") if isinstance(m, dict) else getattr(m, "agent_name", None)) or "Agent"
        def _content(m):
            return m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        transcript = "\n\n".join(f"{_agent(m)}: {_content(m)}" for m in messages)
        if len(transcript) > 8000:
            transcript = transcript[:8000] + "\n\n[... truncated ...]"
        system = (
            "You are a meeting summarizer. Output exactly two sections: SUMMARY: (one short paragraph, 2-4 sentences), "
            "then KEY_POINTS: (3-5 bullet items, each on a new line starting with '- '). "
            "Use the same language as the meeting content when possible."
        )
        user_content = f"Round discussion:\n\n{transcript}\n\nProvide SUMMARY: and KEY_POINTS: as described."
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


def append_round_summary(
    meeting_id: str,
    round_number: int,
    summary_text: str | None,
    key_points: list[str],
    db: Session,
) -> None:
    """Append a round summary to meeting.round_summaries. Call after each round completes."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        return
    summaries = list(getattr(meeting, "round_summaries", None) or [])
    # Replace if this round already has a summary (e.g. re-run)
    summaries = [s for s in summaries if (s if isinstance(s, dict) else {}).get("round") != round_number]
    summaries.append({
        "round": round_number,
        "summary_text": summary_text or "",
        "key_points": key_points,
    })
    meeting.round_summaries = summaries
    db.commit()


def ensure_meeting_summary_cached(meeting_id: str, db: Session) -> None:
    """Legacy: ensure cached_summary_text exists. Now we use round_summaries instead.
    Kept for backward compatibility; no-op when round_summaries is used."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        return
    # No longer populate cached_summary_text; round_summaries is the source of truth
    db.commit()
