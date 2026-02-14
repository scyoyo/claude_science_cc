from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Team, Agent, Meeting, MeetingMessage, MeetingStatus, CodeArtifact
from app.core.code_extractor import extract_from_meeting_messages
from app.schemas.meeting import (
    MeetingCreate,
    MeetingUpdate,
    MeetingResponse,
    MeetingWithMessages,
    MeetingRunRequest,
    UserMessageRequest,
    MeetingMessageResponse,
    MeetingSummary,
    ContextPreviewResponse,
    BatchMeetingRunRequest,
    BatchMeetingRunResponse,
    RewriteRequest,
    AgendaAutoRequest,
    AgendaAutoResponse,
    AgentVotingRequest,
    AgentVotingResponse,
    AgentProposal,
    ChainRecommendRequest,
    RecommendStrategyRequest,
    RecommendStrategyResponse,
)
from app.core.meeting_engine import MeetingEngine
from app.core.llm_client import create_provider, detect_provider, resolve_llm_call
from app.core.lang_detect import meeting_preferred_lang
from app.core.context_extractor import extract_relevant_context, extract_keywords_from_agenda
from app.core.agenda_proposer import AgendaProposer
from app.core.meeting_prompts import rewrite_meeting_prompt
from app.core.background_runner import start_background_run, is_running
from app.schemas.onboarding import ChatMessage
from app.schemas.pagination import PaginatedResponse
from app.database import SessionLocal
from app.api.deps import pagination_params, build_paginated_response

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("/compare")
def compare_meetings(
    ids: str = Query(..., description="Comma-separated meeting IDs (2 required)"),
    db: Session = Depends(get_db),
):
    """Compare two meetings side by side."""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if len(id_list) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly 2 meeting IDs required (comma-separated)",
        )

    meetings = []
    for mid in id_list:
        m = db.query(Meeting).filter(Meeting.id == mid).first()
        if not m:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting {mid} not found")
        meetings.append(m)

    comparisons = []
    for m in meetings:
        msgs = db.query(MeetingMessage).filter(MeetingMessage.meeting_id == m.id).all()
        participants = list({msg.agent_name for msg in msgs if msg.agent_name and msg.role == "assistant"})
        comparisons.append({
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "rounds": m.current_round,
            "max_rounds": m.max_rounds,
            "message_count": len(msgs),
            "participants": participants,
        })

    # Find shared participants
    p1 = set(comparisons[0]["participants"])
    p2 = set(comparisons[1]["participants"])

    return {
        "meetings": comparisons,
        "shared_participants": list(p1 & p2),
        "unique_to_first": list(p1 - p2),
        "unique_to_second": list(p2 - p1),
    }


@router.post("/batch-run", response_model=BatchMeetingRunResponse)
def batch_run_meetings(
    request: BatchMeetingRunRequest,
    db: Session = Depends(get_db),
):
    """Clone a meeting N times, run all iterations, optionally create a merge meeting.

    Flow: clone N meetings -> run all -> create merge meeting with source_meeting_ids.
    Note: actual running is left to the caller (via /run endpoint) since it requires LLM.
    This endpoint creates the meetings and returns their IDs.
    """
    original = db.query(Meeting).filter(Meeting.id == request.meeting_id).first()
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    iteration_ids = []
    for i in range(request.num_iterations):
        clone = Meeting(
            team_id=original.team_id,
            title=f"{original.title} (iteration {i + 1})",
            description=original.description,
            agenda=original.agenda,
            agenda_questions=original.agenda_questions,
            agenda_rules=original.agenda_rules,
            output_type=original.output_type,
            context_meeting_ids=getattr(original, "context_meeting_ids", None) or [],
            participant_agent_ids=getattr(original, "participant_agent_ids", None) or [],
            meeting_type=original.meeting_type or "team",
            individual_agent_id=original.individual_agent_id,
            agenda_strategy=original.agenda_strategy or "manual",
            max_rounds=original.max_rounds,
        )
        db.add(clone)
        db.flush()
        iteration_ids.append(clone.id)

    merge_id = None
    if request.auto_merge:
        merge = Meeting(
            team_id=original.team_id,
            title=f"{original.title} (merge)",
            description=f"Merge of {request.num_iterations} iterations",
            agenda=original.agenda,
            agenda_questions=original.agenda_questions,
            agenda_rules=original.agenda_rules,
            output_type=original.output_type,
            participant_agent_ids=getattr(original, "participant_agent_ids", None) or [],
            meeting_type="merge",
            source_meeting_ids=iteration_ids,
            agenda_strategy=original.agenda_strategy or "manual",
            max_rounds=min(original.max_rounds, 2),
        )
        db.add(merge)
        db.flush()
        merge_id = merge.id

    db.commit()
    return BatchMeetingRunResponse(
        iteration_meeting_ids=iteration_ids,
        merge_meeting_id=merge_id,
    )


# ==================== Agenda Strategy Endpoints ====================

@router.post("/agenda/auto-generate", response_model=AgendaAutoResponse)
def agenda_auto_generate(request: AgendaAutoRequest, db: Session = Depends(get_db)):
    """AI generates agenda + questions + rules based on team composition & goals."""
    team = db.query(Team).filter(Team.id == request.team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    agents = db.query(Agent).filter(Agent.team_id == request.team_id, Agent.is_mirror == False).all()
    if request.participant_agent_ids:
        id_set = set(request.participant_agent_ids)
        agents = [a for a in agents if str(a.id) in id_set]
    agent_dicts = [
        {"name": a.name, "title": a.title, "expertise": a.expertise, "system_prompt": a.system_prompt}
        for a in agents
    ]

    prev_meetings = []
    for mid in request.prev_meeting_ids:
        m = db.query(Meeting).filter(Meeting.id == mid).first()
        if m:
            prev_meetings.append({"title": m.title})

    try:
        llm_call = resolve_llm_call(db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No API key configured")

    proposer = AgendaProposer(llm_call=llm_call)
    result = proposer.auto_generate(
        agents=agent_dicts,
        team_desc=team.description or team.name,
        goal=request.goal or "",
        prev_meetings=prev_meetings or None,
    )
    return AgendaAutoResponse(**result)


@router.post("/agenda/agent-voting", response_model=AgentVotingResponse)
def agenda_agent_voting(request: AgentVotingRequest, db: Session = Depends(get_db)):
    """Each agent proposes 2-3 agenda items. Returns all proposals + merged agenda."""
    team = db.query(Team).filter(Team.id == request.team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    agents = db.query(Agent).filter(Agent.team_id == request.team_id, Agent.is_mirror == False).all()
    if not agents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No agents in team")

    agent_dicts = [
        {"name": a.name, "title": a.title, "expertise": a.expertise, "system_prompt": a.system_prompt}
        for a in agents
    ]

    try:
        llm_call = resolve_llm_call(db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No API key configured")

    proposer = AgendaProposer(llm_call=llm_call)
    result = proposer.agent_voting(agents=agent_dicts, topic=request.topic)
    return AgentVotingResponse(
        proposals=[AgentProposal(**p) for p in result["proposals"]],
        merged_agenda=result["merged_agenda"],
    )


@router.post("/agenda/chain-recommend", response_model=AgendaAutoResponse)
def agenda_chain_recommend(request: ChainRecommendRequest, db: Session = Depends(get_db)):
    """Based on previous meeting results, suggest next meeting agenda."""
    if not request.prev_meeting_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No previous meeting IDs provided")

    summaries = _load_context_summaries(db, request.prev_meeting_ids)
    if not summaries:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid previous meetings found")

    try:
        llm_call = resolve_llm_call(db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No API key configured")

    proposer = AgendaProposer(llm_call=llm_call)
    result = proposer.chain_recommend(prev_meeting_summaries=summaries)
    return AgendaAutoResponse(**result)


@router.post("/agenda/recommend-strategy", response_model=RecommendStrategyResponse)
def agenda_recommend_strategy(request: RecommendStrategyRequest, db: Session = Depends(get_db)):
    """AI recommends which agenda strategy is best for the situation."""
    team = db.query(Team).filter(Team.id == request.team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    agents = db.query(Agent).filter(Agent.team_id == request.team_id, Agent.is_mirror == False).all()
    agent_dicts = [{"name": a.name} for a in agents]

    proposer = AgendaProposer(llm_call=lambda s, m: "")  # Not needed for rule-based recommend
    result = proposer.recommend_strategy(
        agents=agent_dicts,
        has_prev=request.has_prev_meetings,
        topic=request.topic or "",
    )
    return RecommendStrategyResponse(**result)


@router.get("/", response_model=PaginatedResponse[MeetingResponse])
def list_meetings(
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    """List all meetings across all teams with pagination."""
    skip, limit = pagination
    query = db.query(Meeting).order_by(Meeting.updated_at.desc())
    return build_paginated_response(query, skip, limit)


@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(data: MeetingCreate, db: Session = Depends(get_db)):
    """Create a new meeting for a team."""
    from app.core.meeting_prompts import get_default_rules

    team = db.query(Team).filter(Team.id == data.team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Auto-inject default rules based on output_type if none provided
    rules = data.agenda_rules
    if not rules and data.output_type:
        rules = get_default_rules(data.output_type)

    meeting = Meeting(
        team_id=data.team_id,
        title=data.title,
        description=data.description,
        agenda=data.agenda,
        agenda_questions=data.agenda_questions,
        agenda_rules=rules,
        output_type=data.output_type,
        context_meeting_ids=data.context_meeting_ids,
        participant_agent_ids=data.participant_agent_ids or [],
        meeting_type=data.meeting_type,
        individual_agent_id=data.individual_agent_id,
        source_meeting_ids=data.source_meeting_ids or [],
        parent_meeting_id=data.parent_meeting_id,
        rewrite_feedback=data.rewrite_feedback,
        agenda_strategy=data.agenda_strategy,
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
        agenda=original.agenda,
        agenda_questions=original.agenda_questions,
        agenda_rules=original.agenda_rules,
        output_type=original.output_type,
        context_meeting_ids=getattr(original, "context_meeting_ids", None) or [],
        participant_agent_ids=getattr(original, "participant_agent_ids", None) or [],
        meeting_type=original.meeting_type or "team",
        individual_agent_id=original.individual_agent_id,
        source_meeting_ids=getattr(original, "source_meeting_ids", None) or [],
        agenda_strategy=original.agenda_strategy or "manual",
        max_rounds=original.max_rounds,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.post("/{meeting_id}/run-background")
def run_meeting_background(
    meeting_id: str,
    request: MeetingRunRequest,
    db: Session = Depends(get_db),
):
    """Start a background meeting run. Returns immediately."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    if meeting.status == MeetingStatus.completed.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting is already completed")

    if is_running(meeting_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Meeting is already running in background")

    agents = db.query(Agent).filter(Agent.team_id == meeting.team_id, Agent.is_mirror == False).all()
    if not agents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No agents found in this team")

    remaining = meeting.max_rounds - meeting.current_round
    rounds_to_run = min(request.rounds, remaining)
    if rounds_to_run <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting has reached maximum rounds")

    started = start_background_run(
        meeting_id=meeting_id,
        session_factory=SessionLocal,
        rounds=rounds_to_run,
        topic=request.topic,
    )
    if not started:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Meeting is already running in background")

    return {"meeting_id": meeting_id, "status": "started", "rounds": rounds_to_run}


@router.get("/{meeting_id}/status")
def get_meeting_status(meeting_id: str, db: Session = Depends(get_db)):
    """Lightweight status endpoint for polling."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    message_count = db.query(MeetingMessage).filter(MeetingMessage.meeting_id == meeting_id).count()

    return {
        "meeting_id": meeting_id,
        "status": meeting.status,
        "current_round": meeting.current_round,
        "max_rounds": meeting.max_rounds,
        "message_count": message_count,
        "background_running": is_running(meeting_id),
    }


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
    ]

    # Agenda info
    if meeting.agenda:
        lines.append(f"**Agenda:** {meeting.agenda}")
    if meeting.output_type:
        lines.append(f"**Output Type:** {meeting.output_type}")

    # Participants
    participants = list({
        m.agent_name for m in messages
        if m.agent_name and m.role == "assistant"
    })
    if participants:
        lines.append(f"**Participants:** {', '.join(sorted(participants))}")

    lines.append("")
    lines.append("---")
    lines.append("")

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

    # Artifacts section
    artifacts = db.query(CodeArtifact).filter(
        CodeArtifact.meeting_id == meeting_id,
    ).all()
    if artifacts:
        lines.append("---")
        lines.append("")
        lines.append("## Artifacts")
        lines.append("")
        for a in artifacts:
            lines.append(f"- `{a.filename}` ({a.language})")
        lines.append("")

    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{meeting.title}.md"'},
    )


@router.post("/{meeting_id}/rewrite", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def rewrite_meeting(meeting_id: str, request: RewriteRequest, db: Session = Depends(get_db)):
    """Create a new meeting that rewrites/improves a completed meeting based on feedback.

    Only works on completed meetings. Creates a new meeting with parent_meeting_id set.
    The original meeting output + feedback are injected as context.
    """
    original = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    if original.status != MeetingStatus.completed.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only rewrite completed meetings",
        )

    # Get original's last assistant message as the output to improve
    last_msg = db.query(MeetingMessage).filter(
        MeetingMessage.meeting_id == meeting_id,
        MeetingMessage.role == "assistant",
    ).order_by(MeetingMessage.created_at.desc()).first()

    original_output = last_msg.content if last_msg else ""

    # Create new meeting with parent reference
    rewrite = Meeting(
        team_id=original.team_id,
        title=f"{original.title} (rewrite)",
        description=original.description,
        agenda=original.agenda,
        agenda_questions=original.agenda_questions,
        agenda_rules=original.agenda_rules,
        output_type=original.output_type,
        context_meeting_ids=getattr(original, "context_meeting_ids", None) or [],
        participant_agent_ids=getattr(original, "participant_agent_ids", None) or [],
        meeting_type=original.meeting_type or "team",
        individual_agent_id=original.individual_agent_id,
        parent_meeting_id=meeting_id,
        rewrite_feedback=request.feedback,
        agenda_strategy=original.agenda_strategy or "manual",
        max_rounds=request.rounds,
    )

    # Inject rewrite context as a system message
    rewrite_context = rewrite_meeting_prompt(
        original_output=original_output,
        feedback=request.feedback,
        agenda=original.agenda or "",
        questions=original.agenda_questions or [],
    )

    db.add(rewrite)
    db.flush()

    # Add the rewrite context as first message
    context_msg = MeetingMessage(
        meeting_id=rewrite.id,
        role="user",
        content=rewrite_context,
        round_number=0,
    )
    db.add(context_msg)
    db.commit()
    db.refresh(rewrite)
    return rewrite


@router.post("/{meeting_id}/preview-context", response_model=ContextPreviewResponse)
def preview_context(meeting_id: str, db: Session = Depends(get_db)):
    """Preview what context would be injected for this meeting's context_meeting_ids."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    context_ids = getattr(meeting, "context_meeting_ids", None) or []
    if not context_ids:
        return ContextPreviewResponse(contexts=[], total_chars=0)

    keywords = extract_keywords_from_agenda(
        meeting.agenda or "", meeting.agenda_questions or []
    )
    contexts = extract_relevant_context(db, context_ids, keywords=keywords or None)
    total_chars = sum(len(c["summary"]) for c in contexts)
    return ContextPreviewResponse(contexts=contexts, total_chars=total_chars)


@router.get("/team/{team_id}", response_model=PaginatedResponse[MeetingResponse])
def list_team_meetings(
    team_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    """List all meetings for a team with pagination."""
    skip, limit = pagination
    query = db.query(Meeting).filter(Meeting.team_id == team_id)
    return build_paginated_response(query, skip, limit)


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

    # Get team agents (optionally restricted to participant_agent_ids)
    agents = db.query(Agent).filter(
        Agent.team_id == meeting.team_id,
        Agent.is_mirror == False,
    ).all()
    participant_ids = getattr(meeting, "participant_agent_ids", None) or []
    if participant_ids:
        id_set = set(str(aid) for aid in participant_ids)
        agents = [a for a in agents if str(a.id) in id_set]

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
        llm_call = resolve_llm_call(db)
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
        use_structured = bool(meeting.agenda)
        meeting_type = getattr(meeting, "meeting_type", "team") or "team"

        # Load context from previous meetings if configured (smart RAG extraction)
        context_summaries = None
        if meeting.context_meeting_ids:
            keywords = extract_keywords_from_agenda(
                meeting.agenda or "", meeting.agenda_questions or []
            )
            context_summaries = extract_relevant_context(
                db, meeting.context_meeting_ids, keywords=keywords or None
            )

        preferred_lang = meeting_preferred_lang(
            existing_messages, getattr(request, "topic", None), getattr(request, "locale", None)
        )

        if meeting_type == "individual":
            # Individual meeting: single agent + scientific critic
            ind_agent_id = getattr(meeting, "individual_agent_id", None)
            if ind_agent_id:
                ind_agent = db.query(Agent).filter(Agent.id == ind_agent_id).first()
                if not ind_agent:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Individual agent not found")
                agent_dict = {
                    "id": str(ind_agent.id),
                    "name": ind_agent.name,
                    "system_prompt": ind_agent.system_prompt,
                    "model": ind_agent.model,
                }
            else:
                # Fallback to first agent
                agent_dict = agent_dicts[0]

            all_rounds = engine.run_individual_meeting(
                agent=agent_dict,
                conversation_history=conversation_history,
                rounds=rounds_to_run,
                agenda=meeting.agenda or "",
                agenda_questions=meeting.agenda_questions or [],
                agenda_rules=meeting.agenda_rules or [],
                context_summaries=context_summaries,
                preferred_lang=preferred_lang,
            )
        elif meeting_type == "merge":
            # Merge meeting: synthesize source meetings
            source_ids = getattr(meeting, "source_meeting_ids", None) or []
            source_summaries = _load_context_summaries(db, source_ids) if source_ids else []
            all_rounds = engine.run_merge_meeting(
                agents=agent_dicts,
                source_summaries=source_summaries,
                conversation_history=conversation_history,
                rounds=rounds_to_run,
                agenda=meeting.agenda or "",
                agenda_questions=meeting.agenda_questions or [],
                agenda_rules=meeting.agenda_rules or [],
                output_type=meeting.output_type or "code",
                preferred_lang=preferred_lang,
            )
        elif use_structured:
            all_rounds = engine.run_structured_meeting(
                agents=agent_dicts,
                conversation_history=conversation_history,
                rounds=rounds_to_run,
                agenda=meeting.agenda,
                agenda_questions=meeting.agenda_questions or [],
                agenda_rules=meeting.agenda_rules or [],
                output_type=meeting.output_type or "code",
                start_round=meeting.current_round + 1,
                context_summaries=context_summaries,
                preferred_lang=preferred_lang,
            )
        else:
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

        # Auto-extract artifacts on completion
        if meeting.status == MeetingStatus.completed.value:
            _auto_extract_artifacts(db, meeting_id)

    except Exception as e:
        meeting.status = MeetingStatus.failed.value
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Meeting execution failed: {str(e)}",
        )

    return meeting


def _load_context_summaries(db: Session, context_meeting_ids: list) -> list:
    """Load final summaries from context meetings.

    For each referenced meeting, takes the last assistant message as the summary.
    """
    summaries = []
    for mid in context_meeting_ids:
        ctx_meeting = db.query(Meeting).filter(Meeting.id == mid).first()
        if not ctx_meeting:
            continue
        # Get last assistant message as summary
        last_msg = db.query(MeetingMessage).filter(
            MeetingMessage.meeting_id == mid,
            MeetingMessage.role == "assistant",
        ).order_by(MeetingMessage.created_at.desc()).first()
        if last_msg:
            summaries.append({
                "title": ctx_meeting.title,
                "summary": last_msg.content,
            })
    return summaries


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
        pass  # Don't fail the meeting if extraction fails
