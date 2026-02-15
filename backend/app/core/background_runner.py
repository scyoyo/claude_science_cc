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
from app.core.meeting_prompts import content_for_user_message
from app.core.llm_client import resolve_llm_call, LLMQuotaError
from app.core.code_extractor import extract_from_meeting_messages
from app.core import event_bus

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
    locale: Optional[str] = None,
) -> bool:
    """Start a background meeting run. Returns True if started, False if already running."""
    with _lock:
        thread = _running.get(meeting_id)
        if thread is not None and thread.is_alive():
            return False

        t = threading.Thread(
            target=_run_meeting_thread,
            args=(meeting_id, session_factory, rounds, topic, llm_call_override, locale),
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
    locale: Optional[str] = None,
) -> None:
    """Background thread that runs meeting rounds one at a time, committing after each."""
    db: Session = session_factory()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            logger.error("Background run: meeting %s not found", meeting_id)
            return

        # Get agents (optionally restricted to participant_agent_ids)
        agents = (
            db.query(Agent)
            .filter(Agent.team_id == meeting.team_id, Agent.is_mirror == False)
            .all()
        )
        participant_ids = getattr(meeting, "participant_agent_ids", None) or []
        if participant_ids:
            id_set = set(str(aid) for aid in participant_ids)
            agents = [a for a in agents if str(a.id) in id_set]
        if not agents:
            meeting.status = MeetingStatus.failed.value
            db.commit()
            return

        agent_dicts = [
            {
                "id": str(a.id), "name": a.name, "system_prompt": a.system_prompt,
                "model": a.model, "title": a.title or "", "role": getattr(a, "role", "") or "",
            }
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

        # Clear any stale replay buffer from a previous run
        from app.core import event_bus
        event_bus.clear_replay_buffer(meeting_id)

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
                content = content_for_user_message(
                    msg.role, getattr(msg, "agent_id", None), getattr(msg, "agent_name", None), msg.content
                )
                conversation_history.append(ChatMessage(role="user", content=content))
            else:
                label = msg.agent_name or "Assistant"
                conversation_history.append(
                    ChatMessage(role="user", content=f"[{label}]: {msg.content}")
                )

        use_structured = bool(meeting.agenda)
        meeting_type = getattr(meeting, "meeting_type", "team") or "team"

        # Individual meeting: replace agent_dicts with [agent, synthetic_critic]
        if meeting_type == "individual":
            from app.core.meeting_engine import build_individual_agents
            ind_agent_id = getattr(meeting, "individual_agent_id", None)
            if ind_agent_id:
                ind_agents = [a for a in agents if str(a.id) == str(ind_agent_id)]
                if ind_agents:
                    ind_a = ind_agents[0]
                    ind_dict = {
                        "id": str(ind_a.id), "name": ind_a.name,
                        "system_prompt": ind_a.system_prompt, "model": ind_a.model,
                        "title": ind_a.title or "", "role": getattr(ind_a, "role", "") or "",
                    }
                else:
                    ind_dict = agent_dicts[0]
            else:
                ind_dict = agent_dicts[0]
            agent_dicts = build_individual_agents(ind_dict)
            use_structured = True  # Force structured path

        from app.core.lang_detect import meeting_preferred_lang
        from app.models import Team as TeamModel
        team_obj = db.query(TeamModel).filter(TeamModel.id == meeting.team_id).first()
        team_language = getattr(team_obj, "language", None) if team_obj else None
        preferred_lang = meeting_preferred_lang(
            existing_messages, topic, locale, team_language=team_language
        )

        # Build round_plans lookup for goal injection
        raw_plans = getattr(meeting, "round_plans", None) or []
        plans_by_round = {}
        for rp in raw_plans:
            if isinstance(rp, dict):
                plans_by_round[rp.get("round", 0)] = rp

        # Run round by round, committing after each.
        # Callbacks stream events to the frontend in real time as each agent responds.
        for round_idx in range(rounds_to_run):
            current_round_num = meeting.current_round + 1
            total_rounds = meeting.max_rounds

            # --- Real-time callbacks for per-agent streaming ---
            def _on_agent_start(agent: dict) -> None:
                """Publish 'agent_speaking' so frontend shows who is thinking."""
                event_bus.publish(meeting_id, {
                    "type": "agent_speaking",
                    "agent_name": agent["name"],
                    "agent_id": agent.get("id"),
                })

            def _on_agent_done(msg_data: dict, _round=current_round_num) -> None:
                """Save message to DB and publish it immediately so frontend can render."""
                message = MeetingMessage(
                    meeting_id=meeting_id,
                    agent_id=msg_data["agent_id"],
                    role=msg_data["role"],
                    agent_name=msg_data["agent_name"],
                    content=msg_data["content"],
                    round_number=_round,
                )
                db.add(message)
                db.flush()
                db.commit()
                event_bus.publish(meeting_id, {
                    "type": "message",
                    "id": message.id,
                    "agent_id": msg_data["agent_id"],
                    "agent_name": msg_data["agent_name"],
                    "role": msg_data["role"],
                    "content": msg_data["content"],
                    "round_number": _round,
                })
                conversation_history.append(
                    ChatMessage(role="user", content=f"[{msg_data['agent_name']}]: {msg_data['content']}")
                )

            if use_structured:
                engine.run_structured_round(
                    agents=agent_dicts,
                    conversation_history=conversation_history,
                    round_num=current_round_num,
                    num_rounds=total_rounds,
                    agenda=meeting.agenda or "",
                    agenda_questions=meeting.agenda_questions or [],
                    agenda_rules=meeting.agenda_rules or [],
                    output_type=meeting.output_type or "code",
                    preferred_lang=preferred_lang,
                    round_plan=plans_by_round.get(current_round_num),
                    on_agent_start=_on_agent_start,
                    on_agent_done=_on_agent_done,
                )
            else:
                round_topic = topic if round_idx == 0 else None
                engine.run_round(
                    agent_dicts, conversation_history, round_topic,
                    preferred_lang=preferred_lang if round_idx == 0 else None,
                    on_agent_start=_on_agent_start,
                    on_agent_done=_on_agent_done,
                )

            # Messages already saved via _on_agent_done callback above;
            # just update the round counter.
            meeting.current_round = current_round_num
            db.commit()
            event_bus.publish(meeting_id, {
                "type": "round_complete",
                "round": current_round_num,
                "total_rounds": meeting.max_rounds,
            })

        # Final status
        if meeting.current_round >= meeting.max_rounds:
            meeting.status = MeetingStatus.completed.value
        else:
            meeting.status = MeetingStatus.pending.value
        db.commit()

        event_bus.publish(meeting_id, {
            "type": "meeting_complete",
            "status": meeting.status,
        })

        # Auto-extract artifacts on completion
        if meeting.status == MeetingStatus.completed.value:
            _auto_extract_artifacts(db, meeting_id)

    except LLMQuotaError as e:
        logger.warning("API quota exhausted for meeting %s", meeting_id)
        event_bus.publish(meeting_id, {
            "type": "error",
            "detail": "API quota exhausted. Please check your API key billing or switch provider.",
            "provider": getattr(e, "provider", None),
        })
        try:
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting:
                meeting.status = MeetingStatus.failed.value
                meeting.description = (meeting.description or "") + "\n[ERROR] API quota exhausted. Please check your API key billing or switch provider."
                db.commit()
        except Exception:
            logger.exception("Failed to mark meeting %s as failed", meeting_id)
    except Exception:
        logger.exception("Background meeting run failed for %s", meeting_id)
        event_bus.publish(meeting_id, {
            "type": "error",
            "detail": "Meeting execution failed",
        })
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
