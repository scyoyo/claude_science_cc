"""
Background meeting runner: executes meetings in a background thread so the
frontend can disconnect without losing progress.

Each round is committed individually so the frontend can poll for progress.
"""

import threading
import logging
from typing import Optional, Callable

from sqlalchemy.orm import Session, sessionmaker

from app.models import Meeting, MeetingMessage, MeetingStatus, Agent, CodeArtifact
from app.schemas.onboarding import ChatMessage
from app.core.meeting_engine import MeetingEngine
from app.core.llm_client import resolve_llm_call
from app.core.code_extractor import extract_from_meeting_messages

logger = logging.getLogger(__name__)

# Track running meetings: meeting_id -> thread
_running: dict[str, threading.Thread] = {}
_lock = threading.Lock()


def is_running(meeting_id: str) -> bool:
    with _lock:
        thread = _running.get(meeting_id)
        return thread is not None and thread.is_alive()


def start_background_run(
    meeting_id: str,
    session_factory: sessionmaker,
    rounds: int = 1,
    topic: Optional[str] = None,
    llm_call_override: Optional[Callable] = None,
) -> bool:
    """Start a background meeting run. Returns True if started, False if already running."""
    with _lock:
        thread = _running.get(meeting_id)
        if thread is not None and thread.is_alive():
            return False

        t = threading.Thread(
            target=_run_meeting_thread,
            args=(meeting_id, session_factory, rounds, topic, llm_call_override),
            daemon=True,
        )
        _running[meeting_id] = t
        t.start()
        return True


def _run_meeting_thread(
    meeting_id: str,
    session_factory: sessionmaker,
    rounds: int,
    topic: Optional[str],
    llm_call_override: Optional[Callable],
) -> None:
    """Background thread that runs meeting rounds one at a time, committing after each."""
    db: Session = session_factory()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            logger.error("Background run: meeting %s not found", meeting_id)
            return

        # Get agents
        agents = (
            db.query(Agent)
            .filter(Agent.team_id == meeting.team_id, Agent.is_mirror == False)
            .all()
        )
        if not agents:
            meeting.status = MeetingStatus.failed.value
            db.commit()
            return

        agent_dicts = [
            {"id": str(a.id), "name": a.name, "system_prompt": a.system_prompt, "model": a.model}
            for a in agents
        ]

        # Build LLM callable
        if llm_call_override:
            llm_call = llm_call_override
        else:
            llm_call = resolve_llm_call(db)

        engine = MeetingEngine(llm_call=llm_call)

        # Cap rounds
        remaining = meeting.max_rounds - meeting.current_round
        rounds_to_run = min(rounds, remaining)
        if rounds_to_run <= 0:
            return

        meeting.status = MeetingStatus.running.value
        db.commit()

        # Build conversation history
        existing_messages = (
            db.query(MeetingMessage)
            .filter(MeetingMessage.meeting_id == meeting_id)
            .order_by(MeetingMessage.created_at)
            .all()
        )
        conversation_history: list[ChatMessage] = []
        for msg in existing_messages:
            if msg.role == "user":
                conversation_history.append(ChatMessage(role="user", content=msg.content))
            else:
                label = msg.agent_name or "Assistant"
                conversation_history.append(
                    ChatMessage(role="user", content=f"[{label}]: {msg.content}")
                )

        use_structured = bool(meeting.agenda)
        from app.core.lang_detect import meeting_preferred_lang
        preferred_lang = meeting_preferred_lang(
            existing_messages, topic, None
        )

        # Run round by round, committing after each
        for round_idx in range(rounds_to_run):
            current_round_num = meeting.current_round + 1
            total_rounds = meeting.max_rounds

            if use_structured:
                round_messages = engine.run_structured_round(
                    agents=agent_dicts,
                    conversation_history=conversation_history,
                    round_num=current_round_num,
                    num_rounds=total_rounds,
                    agenda=meeting.agenda or "",
                    agenda_questions=meeting.agenda_questions or [],
                    agenda_rules=meeting.agenda_rules or [],
                    output_type=meeting.output_type or "code",
                    preferred_lang=preferred_lang,
                )
            else:
                round_topic = topic if round_idx == 0 else None
                round_messages = engine.run_round(agent_dicts, conversation_history, round_topic)

            round_number = meeting.current_round + 1
            for msg_data in round_messages:
                message = MeetingMessage(
                    meeting_id=meeting_id,
                    agent_id=msg_data["agent_id"],
                    role=msg_data["role"],
                    agent_name=msg_data["agent_name"],
                    content=msg_data["content"],
                    round_number=round_number,
                )
                db.add(message)
                conversation_history.append(
                    ChatMessage(role="user", content=f"[{msg_data['agent_name']}]: {msg_data['content']}")
                )

            meeting.current_round = round_number
            db.commit()

        # Final status
        if meeting.current_round >= meeting.max_rounds:
            meeting.status = MeetingStatus.completed.value
        else:
            meeting.status = MeetingStatus.pending.value
        db.commit()

        # Auto-extract artifacts on completion
        if meeting.status == MeetingStatus.completed.value:
            _auto_extract_artifacts(db, meeting_id)

    except Exception:
        logger.exception("Background meeting run failed for %s", meeting_id)
        try:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting:
                meeting.status = MeetingStatus.failed.value
                db.commit()
        except Exception:
            logger.exception("Failed to mark meeting %s as failed", meeting_id)
    finally:
        db.close()
        with _lock:
            _running.pop(meeting_id, None)


def _auto_extract_artifacts(db: Session, meeting_id: str) -> None:
    """Extract code artifacts from meeting messages after completion."""
    try:
        messages = db.query(MeetingMessage).filter(
            MeetingMessage.meeting_id == meeting_id,
            MeetingMessage.role == "assistant",
        ).order_by(MeetingMessage.created_at).all()

        msg_dicts = [
            {"content": m.content, "agent_name": m.agent_name, "role": m.role}
            for m in messages
        ]
        extracted = extract_from_meeting_messages(msg_dicts)

        for block in extracted:
            artifact = CodeArtifact(
                meeting_id=meeting_id,
                filename=block.suggested_filename,
                language=block.language,
                content=block.content,
                description=f"Auto-extracted from {block.source_agent or 'agent'} response",
            )
            db.add(artifact)

        if extracted:
            db.commit()
    except Exception:
        logger.exception("Auto-extract artifacts failed for meeting %s", meeting_id)


def cleanup_stuck_meetings(session_factory: sessionmaker) -> int:
    """Reset any meetings stuck in 'running' status (e.g. after server restart).
    Returns the number of meetings cleaned up."""
    db: Session = session_factory()
    try:
        stuck = (
            db.query(Meeting)
            .filter(Meeting.status == MeetingStatus.running.value)
            .all()
        )
        count = 0
        for m in stuck:
            if not is_running(m.id):
                m.status = MeetingStatus.failed.value
                count += 1
        if count:
            db.commit()
        return count
    except Exception:
        # Schema mismatch (e.g. new columns not yet in DB) — skip cleanup
        logger.debug("cleanup_stuck_meetings skipped due to schema mismatch")
        return 0
    finally:
        db.close()
