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
│   │   │   └── core/            # Business logic (to be implemented)
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
```

## API Endpoints (Currently Implemented)

```
GET    /                          # Root info
GET    /health                    # Health check
GET    /api/teams/                # List all teams
POST   /api/teams/                # Create team
GET    /api/teams/{team_id}       # Get team with agents
PUT    /api/teams/{team_id}       # Update team
DELETE /api/teams/{team_id}       # Delete team (cascades to agents)
POST   /api/agents/               # Create agent (auto-generates system_prompt)
GET    /api/agents/{agent_id}     # Get agent
PUT    /api/agents/{agent_id}     # Update agent (regenerates system_prompt if needed)
DELETE /api/agents/{agent_id}     # Delete agent
GET    /api/agents/team/{team_id} # List agents in team
```

## Database Models

**Team**: id, name, description, is_public, created_at, updated_at
**Agent**: id, team_id(FK), name, title, expertise, goal, role, system_prompt, model, model_params(JSON), position_x, position_y, is_mirror, primary_agent_id(FK self), created_at, updated_at

## Test Results (Last Run)

- **19/19 tests passed**, 96% coverage
- test_main.py (2 tests): root endpoint, health check
- test_models.py (4 tests): create team, create agent, cascade delete, mirror agent
- test_teams_api.py (6 tests): CRUD + 404 handling
- test_agents_api.py (7 tests): CRUD + invalid team + cascade delete

## Git Commits

- `3fb5516` - feat: Initial implementation - Steps 1.1, 1.2, 1.3 complete

## Development Rules

1. **Git commit after each step** with descriptive message
2. **Run tests before committing** - all must pass
3. **Incremental development** - each step independently testable
4. **No breaking changes** - existing tests must continue to pass

## Implementation Plan - Remaining Steps

### Step 1.0: Intelligent Onboarding System (NEXT)
- `backend/app/core/__init__.py`
- `backend/app/core/team_builder.py` - AI-powered team composition (TeamBuilder class)
  - `analyze_problem(problem_description)` → domain analysis JSON
  - `suggest_team_composition(analysis, preferences)` → agent list
  - `create_mirror_agents(primary_agents, mirror_model)` → mirror agents
  - `auto_generate_team(conversation_history, team_name)` → complete team config
- `backend/app/core/mirror_validator.py` - Compare primary/mirror agent outputs
  - `compare_responses(primary, mirror)` → consistency analysis
  - `should_flag_for_review(comparison)` → bool
- `backend/app/schemas/onboarding.py` - Request/response schemas for onboarding chat
- `backend/app/api/onboarding.py` - Onboarding chat API
  - POST `/api/onboarding/chat` - Multi-stage conversation (problem → clarification → team_suggestion → mirror_config → complete)
  - POST `/api/onboarding/generate-team` - Auto-generate team from config
- `backend/tests/test_onboarding.py` - Tests for onboarding flow
- **Note**: LLM calls should be mockable for testing (don't require real API keys in tests)

### Step 1.4: LLM API Client
- Unified interface for OpenAI/Claude/DeepSeek
- API key storage (encrypted)
- Provider factory pattern
- Rate limiting, error handling, retry logic

### Step 1.5: Meeting Execution Engine
- LangGraph orchestration
- Agent conversation management
- WebSocket real-time updates
- Meeting history storage

### Step 1.6: Frontend Basic UI (Next.js)
- Project setup with Next.js + TypeScript
- Team list/detail pages
- Agent list/detail pages
- Basic routing and navigation

### Step 1.7: Visual Editor
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
