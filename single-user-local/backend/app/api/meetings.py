from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import List

from app.config import settings
from app.database import get_db
from app.models import Team, Agent, Meeting, MeetingMessage, MeetingStatus, APIKey
from app.schemas.meeting import (
    MeetingCreate,
    MeetingUpdate,
    MeetingResponse,
    MeetingWithMessages,
    MeetingRunRequest,
    UserMessageRequest,
    MeetingMessageResponse,
    MeetingSummary,
)
from app.core.meeting_engine import MeetingEngine
from app.core.llm_client import create_provider, detect_provider
from app.core.encryption import decrypt_api_key
from app.schemas.onboarding import ChatMessage
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(data: MeetingCreate, db: Session = Depends(get_db)):
    """Create a new meeting for a team."""
    team = db.query(Team).filter(Team.id == data.team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    meeting = Meeting(
        team_id=data.team_id,
        title=data.title,
        description=data.description,
        max_rounds=data.max_rounds,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.post("/{meeting_id}/clone", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def clone_meeting(meeting_id: str, db: Session = Depends(get_db)):
    """Clone a meeting's configuration into a new meeting."""
    original = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    clone = Meeting(
        team_id=original.team_id,
        title=f"{original.title} (copy)",
        description=original.description,
        max_rounds=original.max_rounds,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/{meeting_id}", response_model=MeetingWithMessages)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    """Get meeting details with messages."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


@router.get("/{meeting_id}/summary", response_model=MeetingSummary)
def get_meeting_summary(meeting_id: str, db: Session = Depends(get_db)):
    """Generate a summary of the meeting from its messages."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    messages = db.query(MeetingMessage).filter(
        MeetingMessage.meeting_id == meeting_id,
    ).order_by(MeetingMessage.created_at).all()

    # Extract unique participants
    participants = list({
        m.agent_name for m in messages
        if m.agent_name and m.role == "assistant"
    })

    # Extract key points: first sentence of each agent message (deduped)
    key_points = []
    seen = set()
    for m in messages:
        if m.role == "assistant" and m.content:
            # Take the first sentence as a key point
            first_sentence = m.content.split(".")[0].strip()
            if first_sentence and len(first_sentence) > 10 and first_sentence not in seen:
                key_points.append(f"[{m.agent_name or 'Agent'}] {first_sentence}")
                seen.add(first_sentence)

    return MeetingSummary(
        meeting_id=meeting_id,
        title=meeting.title,
        total_rounds=meeting.current_round,
        total_messages=len(messages),
        participants=participants,
        key_points=key_points,
        status=meeting.status,
    )


@router.get("/{meeting_id}/transcript", response_class=PlainTextResponse)
def get_meeting_transcript(meeting_id: str, db: Session = Depends(get_db)):
    """Export meeting messages as a formatted markdown transcript."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    messages = db.query(MeetingMessage).filter(
        MeetingMessage.meeting_id == meeting_id,
    ).order_by(MeetingMessage.created_at).all()

    lines = [
        f"# {meeting.title}",
        "",
        f"**Status:** {meeting.status} | **Rounds:** {meeting.current_round}/{meeting.max_rounds}",
        f"**Created:** {meeting.created_at.strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]

    current_round = None
    for msg in messages:
        if msg.round_number != current_round:
            current_round = msg.round_number
            lines.append(f"## Round {current_round}")
            lines.append("")

        if msg.role == "user":
            lines.append(f"**User:** {msg.content}")
        else:
            speaker = msg.agent_name or "Agent"
            lines.append(f"**{speaker}:** {msg.content}")
        lines.append("")

    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{meeting.title}.md"'},
    )


@router.get("/team/{team_id}", response_model=PaginatedResponse[MeetingResponse])
def list_team_meetings(
    team_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all meetings for a team with pagination."""
    query = db.query(Meeting).filter(Meeting.team_id == team_id)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.put("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(meeting_id: str, data: MeetingUpdate, db: Session = Depends(get_db)):
    """Update a meeting."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(meeting, field, value)

    db.commit()
    db.refresh(meeting)
    return meeting


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meeting(meeting_id: str, db: Session = Depends(get_db)):
    """Delete a meeting."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    db.delete(meeting)
    db.commit()
    return None


@router.post("/{meeting_id}/message", response_model=MeetingMessageResponse, status_code=status.HTTP_201_CREATED)
def add_user_message(meeting_id: str, data: UserMessageRequest, db: Session = Depends(get_db)):
    """Add a user message to a meeting."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    message = MeetingMessage(
        meeting_id=meeting_id,
        role="user",
        content=data.content,
        round_number=meeting.current_round,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def _make_llm_call(db: Session):
    """Create an LLM callable that uses stored API keys."""
    def llm_call(system_prompt: str, messages: List[ChatMessage]) -> str:
        # For now, get the first agent's model from messages context
        # In a real implementation, the model would be passed per-agent
        # Try to find an active API key for any provider
        for provider_name in ["openai", "anthropic", "deepseek"]:
            api_key_record = db.query(APIKey).filter(
                APIKey.provider == provider_name,
                APIKey.is_active == True,
            ).first()
            if api_key_record:
                decrypted_key = decrypt_api_key(api_key_record.encrypted_key, settings.ENCRYPTION_SECRET)
                provider = create_provider(provider_name, decrypted_key)
                # Prepend system message
                all_messages = [ChatMessage(role="system", content=system_prompt)] + messages
                # Use a default model for the provider
                model_map = {"openai": "gpt-4", "anthropic": "claude-3-opus-20240229", "deepseek": "deepseek-chat"}
                response = provider.chat(all_messages, model_map[provider_name])
                return response.content
        raise RuntimeError("No active API key found for any LLM provider")
    return llm_call


@router.post("/{meeting_id}/run", response_model=MeetingWithMessages)
def run_meeting(
    meeting_id: str,
    request: MeetingRunRequest,
    db: Session = Depends(get_db),
):
    """Run meeting rounds with all agents discussing.

    Each round: every agent speaks once in order.
    Messages are stored and the meeting state is updated.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    if meeting.status == MeetingStatus.completed.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meeting is already completed",
        )

    # Get team agents
    agents = db.query(Agent).filter(
        Agent.team_id == meeting.team_id,
        Agent.is_mirror == False,
    ).all()

    if not agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No agents found in this team",
        )

    # Prepare agent data
    agent_dicts = [
        {
            "id": str(a.id),
            "name": a.name,
            "system_prompt": a.system_prompt,
            "model": a.model,
        }
        for a in agents
    ]

    # Build conversation history from existing messages
    existing_messages = db.query(MeetingMessage).filter(
        MeetingMessage.meeting_id == meeting_id,
    ).order_by(MeetingMessage.created_at).all()

    conversation_history = []
    for msg in existing_messages:
        if msg.role == "user":
            conversation_history.append(ChatMessage(role="user", content=msg.content))
        else:
            label = msg.agent_name or "Assistant"
            conversation_history.append(
                ChatMessage(role="user", content=f"[{label}]: {msg.content}")
            )

    # Create engine and run
    try:
        llm_call = _make_llm_call(db)
        engine = MeetingEngine(llm_call=llm_call)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to initialize LLM. Ensure an API key is configured.",
        )

    # Cap rounds
    remaining = meeting.max_rounds - meeting.current_round
    rounds_to_run = min(request.rounds, remaining)
    if rounds_to_run <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meeting has reached maximum rounds",
        )

    meeting.status = MeetingStatus.running.value
    db.commit()

    try:
        all_rounds = engine.run_meeting(
            agents=agent_dicts,
            conversation_history=conversation_history,
            rounds=rounds_to_run,
            topic=request.topic,
        )

        # Store messages
        for round_idx, round_messages in enumerate(all_rounds):
            round_number = meeting.current_round + round_idx + 1
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

        meeting.current_round += rounds_to_run
        if meeting.current_round >= meeting.max_rounds:
            meeting.status = MeetingStatus.completed.value
        else:
            meeting.status = MeetingStatus.pending.value

        db.commit()
        db.refresh(meeting)

    except Exception as e:
        meeting.status = MeetingStatus.failed.value
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Meeting execution failed: {str(e)}",
        )

    return meeting
