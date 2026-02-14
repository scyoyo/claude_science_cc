"""
Background meeting runner: executes meetings in a background thread so the
frontend can disconnect without losing progress.

Each round is committed individually so the frontend can poll for progress.
"""

import threading
import logging
from typing import Optional, Callable

from sqlalchemy.orm import Session, sessionmaker

from app.models import Meeting, MeetingMessage, MeetingStatus, Agent, APIKey
from app.schemas.onboarding import ChatMessage
from app.core.meeting_engine import MeetingEngine
from app.core.llm_client import create_provider
from app.core.encryption import decrypt_api_key
from app.config import settings

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


def _make_llm_call(db: Session) -> Callable:
    """Create an LLM callable from stored API keys (same logic as meetings.py)."""
    env_keys = {
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "deepseek": settings.DEEPSEEK_API_KEY,
    }
    model_map = {
        "openai": "gpt-4",
        "anthropic": "claude-3-opus-20240229",
        "deepseek": "deepseek-chat",
    }

    def llm_call(system_prompt: str, messages: list[ChatMessage]) -> str:
        for provider_name in ["openai", "anthropic", "deepseek"]:
            api_key_record = (
                db.query(APIKey)
                .filter(APIKey.provider == provider_name, APIKey.is_active == True)
                .first()
            )
            if api_key_record:
                key = decrypt_api_key(api_key_record.encrypted_key, settings.ENCRYPTION_SECRET)
            else:
                key = env_keys.get(provider_name, "")
            if key:
                provider = create_provider(provider_name, key)
                all_messages = [ChatMessage(role="system", content=system_prompt)] + messages
                response = provider.chat(all_messages, model_map[provider_name])
                return response.content
        raise RuntimeError("No active API key found for any LLM provider.")

    return llm_call


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
            llm_call = _make_llm_call(db)

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

        # Run round by round, committing after each
        for round_idx in range(rounds_to_run):
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
    finally:
        db.close()
