# Virtual Lab Web Application - Development Guide

## Project Overview

Building a web app based on https://github.com/zou-group/virtual-lab that allows users to:
1. Create custom virtual lab team members (AI agents)
2. Visually edit each member's prompt and model configuration
3. Generate executable code (not just reports)
4. Multiple export methods: ZIP download, GitHub push, Google Colab notebook

## Tech Stack

- **Backend**: FastAPI + Python + SQLAlchemy + SQLite (V1)
- **Frontend**: Next.js + React + React Flow + Monaco Editor (to be implemented)
- **LLM**: User-configured API keys, supports OpenAI / Claude / DeepSeek
- **Deployment**: Docker Compose (V1 local) → Kubernetes (V2 cloud)

## Project Structure

```
/Users/chengyao/Code/claude_science/
├── single-user-local/           # Version 1: Single-user local version
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py          # FastAPI app entry point
│   │   │   ├── config.py        # Settings (pydantic-settings)
│   │   │   ├── database.py      # SQLite + SQLAlchemy setup
│   │   │   ├── models/          # DB models (Team, Agent)
│   │   │   ├── schemas/         # Pydantic schemas
│   │   │   ├── api/             # API routers (teams, agents)
│   │   │   └── core/            # Business logic (team_builder, mirror_validator)
│   │   ├── tests/               # pytest tests (conftest + 4 test files)
│   │   ├── venv/                # Python 3.13 virtual environment
│   │   ├── requirements.txt     # Updated for Python 3.13 compatibility
│   │   └── Dockerfile
│   ├── frontend/                # Next.js (to be implemented)
│   └── docker-compose.yml
├── shared/                      # Shared components (to be implemented)
├── docs/                        # Documentation (to be implemented)
├── IMPLEMENTATION_STATUS.md     # Detailed progress tracking
└── CLAUDE.md                    # This file
```

## Development Environment

- **Python**: 3.13.2
- **Virtual env**: `single-user-local/backend/venv/`
- **Activate**: `source single-user-local/backend/venv/bin/activate`
- **Run tests**: `cd single-user-local/backend && source venv/bin/activate && pytest tests/ -v`
- **Run with coverage**: `pytest tests/ -v --cov=app --cov-report=term-missing`
- **Working directory for backend**: `/Users/chengyao/Code/claude_science/single-user-local/backend`

## Key Technical Decisions

1. **File-based SQLite for tests** (`sqlite:///./test.db`) - in-memory SQLite has threading issues with TestClient
2. **conftest.py uses autouse fixture** `setup_test_database` that drops/creates tables per test
3. **Pydantic schemas use `from_attributes = True`** (was `orm_mode` in v1)
4. **Forward reference in team.py**: `TeamWithAgents` imports `AgentResponse` at bottom and calls `model_rebuild()`
5. **System prompt auto-generated** from agent's title/expertise/goal/role fields
6. **Mirror agent support**: Agent model has `is_mirror` and `primary_agent_id` fields

## Current Dependency Versions (Python 3.13 compatible)

```
fastapi==0.115.0
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
pydantic==2.10.3
pydantic-settings==2.6.1
python-dotenv==1.0.1
pytest==8.3.4
pytest-cov==6.0.0
httpx==0.28.1
cryptography==44.0.0
```

## API Endpoints (Currently Implemented)

```
GET    /                                   # Root info
GET    /health                             # Health check
GET    /api/teams/                         # List all teams
POST   /api/teams/                         # Create team
GET    /api/teams/{team_id}                # Get team with agents
PUT    /api/teams/{team_id}                # Update team
DELETE /api/teams/{team_id}                # Delete team (cascades to agents)
POST   /api/agents/                        # Create agent (auto-generates system_prompt)
GET    /api/agents/{agent_id}              # Get agent
PUT    /api/agents/{agent_id}              # Update agent (regenerates system_prompt if needed)
DELETE /api/agents/{agent_id}              # Delete agent
GET    /api/agents/team/{team_id}          # List agents in team
POST   /api/onboarding/chat               # Multi-stage onboarding conversation
POST   /api/onboarding/generate-team      # Generate team from onboarding config
GET    /api/llm/providers                 # List available LLM providers
GET    /api/llm/api-keys                  # List stored API keys (masked)
POST   /api/llm/api-keys                  # Store new API key (encrypted)
PUT    /api/llm/api-keys/{key_id}         # Update API key
DELETE /api/llm/api-keys/{key_id}         # Delete API key
POST   /api/llm/chat                      # Send chat to LLM (auto-detects provider)
POST   /api/meetings/                     # Create meeting
GET    /api/meetings/{meeting_id}         # Get meeting with messages
GET    /api/meetings/team/{team_id}       # List team meetings
PUT    /api/meetings/{meeting_id}         # Update meeting
DELETE /api/meetings/{meeting_id}         # Delete meeting
POST   /api/meetings/{meeting_id}/message # Add user message
POST   /api/meetings/{meeting_id}/run     # Run meeting rounds
```

## Database Models

**Team**: id, name, description, is_public, created_at, updated_at
**Agent**: id, team_id(FK), name, title, expertise, goal, role, system_prompt, model, model_params(JSON), position_x, position_y, is_mirror, primary_agent_id(FK self), created_at, updated_at
**APIKey**: id, provider, encrypted_key, is_active, created_at, updated_at
**Meeting**: id, team_id(FK), title, description, status, max_rounds, current_round, created_at, updated_at
**MeetingMessage**: id, meeting_id(FK), agent_id(FK nullable), role, agent_name, content, round_number, created_at

## Test Results (Last Run)

- **100/100 tests passed**
- test_main.py (2 tests): root endpoint, health check
- test_models.py (4 tests): create team, create agent, cascade delete, mirror agent
- test_teams_api.py (6 tests): CRUD + 404 handling
- test_agents_api.py (7 tests): CRUD + invalid team + cascade delete
- test_onboarding.py (27 tests): TeamBuilder (10), MirrorValidator (6), Onboarding API (11)
- test_llm_client.py (35 tests): Encryption (3), Provider factory (10), Providers (11), API key mgmt (8), LLM chat (3)
- test_meetings.py (19 tests): MeetingEngine (4), Meeting CRUD (8), Meeting run (7)

## Git Commits

- `a300389` - feat: Add Next.js frontend with team/agent/meeting pages (Step 1.6)
- `67bf497` - feat: Add Meeting Execution Engine (Step 1.5)
- `cdb51c8` - feat: Add LLM API Client with provider factory (Step 1.4)
- `4d37bfe` - feat: Add Intelligent Onboarding System (Step 1.0)
- `3fb5516` - feat: Initial implementation - Steps 1.1, 1.2, 1.3 complete

## Development Rules

1. **Git commit after each step** with descriptive message
2. **Run tests before committing** - all must pass
3. **Incremental development** - each step independently testable
4. **No breaking changes** - existing tests must continue to pass

## Implementation Plan - Remaining Steps

### Step 1.0: Intelligent Onboarding System (DONE)
- `backend/app/core/__init__.py` ✅
- `backend/app/core/team_builder.py` ✅ - TeamBuilder with domain detection, team suggestion, mirror creation
- `backend/app/core/mirror_validator.py` ✅ - Jaccard similarity comparison, review threshold
- `backend/app/schemas/onboarding.py` ✅ - OnboardingStage enum, ChatMessage, DomainAnalysis, TeamSuggestion, etc.
- `backend/app/api/onboarding.py` ✅ - POST `/api/onboarding/chat` + POST `/api/onboarding/generate-team`
- `backend/tests/test_onboarding.py` ✅ - 27 tests covering all components
- LLM calls mockable via injectable `llm_func` callable

### Step 1.4: LLM API Client (DONE)
- `backend/app/core/llm_client.py` ✅ - Abstract LLMProvider + OpenAI/Anthropic/DeepSeek implementations
- `backend/app/core/encryption.py` ✅ - Fernet-based API key encryption
- `backend/app/models/api_key.py` ✅ - APIKey DB model
- `backend/app/schemas/api_key.py` ✅ - API key CRUD schemas
- `backend/app/api/llm.py` ✅ - API key management + LLM chat endpoints
- `backend/tests/test_llm_client.py` ✅ - 35 tests, all mocked (no real API calls)
- Provider factory with auto-detection from model name
- Retry logic with exponential backoff

### Step 1.5: Meeting Execution Engine (DONE)
- `backend/app/models/meeting.py` ✅ - Meeting + MeetingMessage models with status tracking
- `backend/app/schemas/meeting.py` ✅ - Meeting CRUD + run + user message schemas
- `backend/app/core/meeting_engine.py` ✅ - Round-robin agent conversation orchestration
- `backend/app/api/meetings.py` ✅ - Full CRUD + run + user message endpoints
- `backend/tests/test_meetings.py` ✅ - 19 tests with mocked LLM
- Agents see cumulative context; meetings track rounds and status
- Note: WebSocket real-time updates deferred to frontend phase

### Step 1.6: Frontend Basic UI (DONE)
- Next.js 16 + TypeScript + Tailwind CSS + App Router ✅
- `frontend/src/types/index.ts` ✅ - TypeScript types matching backend
- `frontend/src/lib/api.ts` ✅ - Fetch-based API client
- `frontend/src/app/page.tsx` ✅ - Home page with nav cards
- `frontend/src/app/teams/page.tsx` ✅ - Team list with create/delete
- `frontend/src/app/teams/[teamId]/page.tsx` ✅ - Team detail with agents + meetings
- `frontend/src/app/teams/[teamId]/meetings/[meetingId]/page.tsx` ✅ - Meeting with messages + run
- `frontend/src/app/settings/page.tsx` ✅ - API key management
- Build passes: `npm run build`

### Step 1.7: Visual Editor (NEXT)
- React Flow for agent graph visualization
- Monaco Editor for prompt editing
- Drag-and-drop agent creation

### Step 1.8: Code Generation
- Extract code from meeting discussions
- Code validation and formatting
- Artifact storage

### Step 1.9: Export Functionality
- ZIP download
- GitHub push
- Google Colab notebook generation

## Deprecation Warnings (Non-blocking, fix later)

- `declarative_base()` → use `sqlalchemy.orm.declarative_base()` (SQLAlchemy 2.0)
- `@app.on_event("startup")` → use lifespan event handlers (FastAPI)
- `datetime.utcnow()` → use `datetime.now(datetime.UTC)` (Python 3.12+)
- Pydantic `class Config` → use `ConfigDict` (Pydantic v2)
