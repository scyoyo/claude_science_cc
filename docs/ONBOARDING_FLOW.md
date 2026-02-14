# Onboarding Flow

This document describes the onboarding wizard flow and recent improvements (semantic stages and editable agent cards).

## Overview

The onboarding flow guides users to create a virtual lab team via a conversational chat. Steps are:

1. **problem** – User describes their research problem; the system asks clarifying questions.
2. **clarification** – User shares preferences (team size, model, focus); the system may ask for more detail or propose a team.
3. **team_suggestion** – User reviews the proposed team (accept / request changes).
4. **mirror_config** – User decides whether to enable mirror agents and which model to use.
5. **complete** – Team is created; user can go to the team page or start over.

## Semantic Stage (No Longer One-Step-Per-Round)

Previously, the frontend sent an explicit `stage` with every message and advanced one step per assistant reply, so the flow felt rigid.

### Current behavior

- **Backend infers stage when `stage` is omitted.** The client may send `stage` as a hint, but the backend can infer the current step from `context` and `conversation_history`:
  - `context.mirror_config` + `context.team_suggestion` → **mirror_config**
  - `context.team_suggestion` → **team_suggestion**
  - `context.analysis` or at least two messages in history → **clarification**
  - Otherwise → **problem**

- **Multi-turn at the same step:**  
  - In **problem**, the backend keeps `next_stage = "problem"` until there are at least two user messages, so the user can discuss the research question over several turns before moving to clarification.  
  - In **clarification**, if the LLM does not yet produce a valid team JSON, the backend returns `next_stage = "clarification"` and asks for more detail, so the user can continue the conversation without being forced to the next step.

- **Frontend:** The client no longer sends `stage`; it sends only `message`, `conversation_history`, and `context`. The UI updates its step from `response.stage` and `response.next_stage`.

Result: the flow advances by **meaning** (what’s in context and conversation), not by a fixed “one message = one step” rule, and users can have multiple back-and-forth messages at any step.

## Editable Agent Cards (Steps 3 & 4)

When the assistant shows a proposed team (cards for each agent), the **latest** proposal in the thread is editable:

- **Where:** Only the most recent message that contains a proposed team has editable cards.
- **How:** Click (or tap) an agent card to open an “Edit agent” dialog. Fields: Name, Title, Expertise, Goal, Role, Model.
- **Effect:** Saving updates both the displayed cards in that message and the internal `team_suggestion` used when the user finishes onboarding (e.g. “Create team”). No need to type in chat to change an agent; editing in place is enough.

Implementation details:

- **Frontend:** `WizardChat` keeps `teamSuggestion` and the last message with `proposedTeam` in sync. `MessageBubble` receives `isEditable` and `onEditAgent(agentIndex, updatedAgent)`. Edits update `teamSuggestion` and the last proposal message’s `proposedTeam`.
- **Backend:** No change; `POST /api/onboarding/generate-team` still receives the final `GenerateTeamRequest` (team name, description, agents, optional mirror_config). The frontend submits the current `teamSuggestion` (including any in-chat edits) when the user completes the flow.

## API Summary

- **`POST /api/onboarding/chat`**  
  - Body: `message`, `conversation_history`, `context`, and optional `stage`.  
  - If `stage` is omitted, the backend infers it (semantic flow).  
  - Response: `stage`, `next_stage`, `message`, `data` (e.g. `team_suggestion`, `analysis`).

- **`POST /api/onboarding/generate-team`**  
  - Body: `team_name`, `team_description`, `agents`, optional `mirror_config`.  
  - Creates the team and agents (and mirrors if configured). The frontend uses the current wizard state (including any card edits) to build this payload.

## Related files

- Backend: `backend/app/api/onboarding.py`, `backend/app/schemas/onboarding.py`, `backend/app/core/team_builder.py`
- Frontend: `frontend/src/components/wizard/WizardChat.tsx`, `frontend/src/types/index.ts`
- Tests: `backend/tests/test_onboarding.py`
