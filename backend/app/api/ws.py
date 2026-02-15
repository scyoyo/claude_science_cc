"""WebSocket endpoint for real-time meeting execution.

Protocol:
  Client -> Server:
    {"type": "start_round", "rounds": 1, "topic": "optional topic"}
    {"type": "user_message", "content": "user input"}

  Server -> Client:
    {"type": "agent_speaking", "agent_name": "Dr. X", "agent_id": "..."}
    {"type": "message", "agent_name": "Dr. X", "agent_id": "...", "content": "..."}
    {"type": "round_complete", "round": 1, "total_rounds": 5}
    {"type": "meeting_complete", "status": "completed"}
    {"type": "error", "detail": "..."}
"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import Meeting, Agent, MeetingMessage, MeetingStatus, CodeArtifact
from app.schemas.onboarding import ChatMessage
from app.core.meeting_engine import MeetingEngine
from app.core.meeting_prompts import content_for_user_message
from app.core.lang_detect import meeting_preferred_lang
from app.core.llm_client import resolve_llm_call, LLMQuotaError
from app.core.code_extractor import extract_from_meeting_messages

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/meetings/{meeting_id}")
async def meeting_websocket(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for real-time meeting execution."""
    await websocket.accept()

    # Create a DB session for this connection
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            await websocket.send_json({"type": "error", "detail": "Meeting not found"})
            await websocket.close()
            return

        while True:
            # Wait for client message
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "user_message":
                await _handle_user_message(websocket, db, meeting, data)

            elif msg_type == "start_round":
                await _handle_start_round(websocket, db, meeting, data)

            else:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass
    finally:
        db.close()


async def _handle_user_message(websocket: WebSocket, db: Session, meeting: Meeting, data: dict):
    """Handle incoming user message."""
    content = data.get("content", "")
    if not content:
        await websocket.send_json({"type": "error", "detail": "Empty message"})
        return

    message = MeetingMessage(
        meeting_id=meeting.id,
        role="user",
        content=content,
        round_number=meeting.current_round,
    )
    db.add(message)
    db.commit()

    await websocket.send_json({
        "type": "message_saved",
        "role": "user",
        "content": content,
    })


async def _handle_start_round(websocket: WebSocket, db: Session, meeting: Meeting, data: dict):
    """Handle start_round: run agent discussions and stream results."""
    rounds = data.get("rounds", 1)
    topic = data.get("topic")

    # Validate meeting state
    if meeting.status == MeetingStatus.completed.value:
        await websocket.send_json({"type": "error", "detail": "Meeting already completed"})
        return

    remaining = meeting.max_rounds - meeting.current_round
    rounds_to_run = min(rounds, remaining)
    if rounds_to_run <= 0:
        await websocket.send_json({"type": "error", "detail": "Max rounds reached"})
        return

    # Get agents (optionally restricted to participant_agent_ids)
    agents = db.query(Agent).filter(
        Agent.team_id == meeting.team_id,
        Agent.is_mirror == False,
    ).all()
    participant_ids = getattr(meeting, "participant_agent_ids", None) or []
    if participant_ids:
        id_set = set(str(aid) for aid in participant_ids)
        agents = [a for a in agents if str(a.id) in id_set]

    if not agents:
        await websocket.send_json({"type": "error", "detail": "No agents in team"})
        return

    agent_dicts = [
        {"id": str(a.id), "name": a.name, "system_prompt": a.system_prompt, "model": a.model}
        for a in agents
    ]

    # Build conversation history
    existing = db.query(MeetingMessage).filter(
        MeetingMessage.meeting_id == meeting.id,
    ).order_by(MeetingMessage.created_at).all()

    history = []
    for msg in existing:
        if msg.role == "user":
            content = content_for_user_message(
                msg.role, getattr(msg, "agent_id", None), getattr(msg, "agent_name", None), msg.content
            )
            history.append(ChatMessage(role="user", content=content))
        else:
            label = msg.agent_name or "Assistant"
            history.append(ChatMessage(role="user", content=f"[{label}]: {msg.content}"))

    # Try to create LLM callable
    try:
        llm_call = resolve_llm_call(db)
    except RuntimeError as e:
        await websocket.send_json({"type": "error", "detail": str(e)})
        return

    meeting.status = MeetingStatus.running.value
    db.commit()

    use_structured = bool(meeting.agenda)
    locale = data.get("locale")
    from app.models import Team as TeamModel
    team_obj = db.query(TeamModel).filter(TeamModel.id == meeting.team_id).first()
    team_language = getattr(team_obj, "language", None) if team_obj else None
    preferred_lang = meeting_preferred_lang(existing, topic, locale, team_language=team_language)

    try:
        engine = MeetingEngine(llm_call=llm_call)

        for round_idx in range(rounds_to_run):
            round_number = meeting.current_round + round_idx + 1

            if use_structured:
                round_messages = engine.run_structured_round(
                    agents=agent_dicts,
                    conversation_history=history,
                    round_num=round_number,
                    num_rounds=meeting.max_rounds,
                    agenda=meeting.agenda or "",
                    agenda_questions=meeting.agenda_questions or [],
                    agenda_rules=meeting.agenda_rules or [],
                    output_type=meeting.output_type or "code",
                    preferred_lang=preferred_lang,
                )
            else:
                round_messages = engine.run_round(
                    agent_dicts, history, topic=topic,
                    preferred_lang=preferred_lang if round_idx == 0 else None,
                )

            for msg_data in round_messages:
                # Notify client agent is speaking
                await websocket.send_json({
                    "type": "agent_speaking",
                    "agent_name": msg_data["agent_name"],
                    "agent_id": msg_data["agent_id"],
                })

                # Send agent's response
                await websocket.send_json({
                    "type": "message",
                    "agent_name": msg_data["agent_name"],
                    "agent_id": msg_data["agent_id"],
                    "content": msg_data["content"],
                    "round": round_number,
                })

                # Store in DB
                message = MeetingMessage(
                    meeting_id=meeting.id,
                    agent_id=msg_data["agent_id"],
                    role=msg_data["role"],
                    agent_name=msg_data["agent_name"],
                    content=msg_data["content"],
                    round_number=round_number,
                )
                db.add(message)

                # Add to history for next agent
                history.append(
                    ChatMessage(role="user", content=f"[{msg_data['agent_name']}]: {msg_data['content']}")
                )

            db.commit()

            await websocket.send_json({
                "type": "round_complete",
                "round": round_number,
                "total_rounds": meeting.max_rounds,
            })

        meeting.current_round += rounds_to_run
        if meeting.current_round >= meeting.max_rounds:
            meeting.status = MeetingStatus.completed.value
        else:
            meeting.status = MeetingStatus.pending.value
        db.commit()

        if meeting.status == MeetingStatus.completed.value:
            # Auto-extract artifacts
            _auto_extract_artifacts(db, meeting.id)
            await websocket.send_json({"type": "meeting_complete", "status": "completed"})

    except LLMQuotaError:
        meeting.status = MeetingStatus.failed.value
        db.commit()
        await websocket.send_json({
            "type": "error",
            "detail": "API quota exhausted. Please check your API key billing or switch to another provider in Settings.",
        })
    except Exception as e:
        meeting.status = MeetingStatus.failed.value
        db.commit()
        await websocket.send_json({"type": "error", "detail": f"Execution failed: {str(e)}"})


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
        pass
