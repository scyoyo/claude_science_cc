# Virtual Lab Web Application - Development Guide

## Project Overview

Building a web app based on https://github.com/zou-group/virtual-lab that allows users to:
1. Create custom virtual lab team members (AI agents)
2. Visually edit each member's prompt and model configuration
3. Generate executable code (not just reports)
4. Multiple export methods: ZIP download, GitHub push, Google Colab notebook

## Tech Stack

- **Backend**: FastAPI + Python + SQLAlchemy + SQLite (V1)
- **Frontend**: Next.js 16 + React 19 + React Flow + Monaco Editor
- **LLM**: User-configured API keys, supports OpenAI / Claude / DeepSeek
- **Deployment**: Docker Compose (V1 local) → Kubernetes (V2 cloud)

## Project Structure

```
/Users/chengyao/Code/claude_science/
├── backend/                     # FastAPI backend (shared)
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # SQLAlchemy setup (SQLite/PostgreSQL)
│   │   ├── models/              # DB models (Team, Agent, Meeting, APIKey, etc.)
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── api/                 # API routers (13 modules)
│   │   ├── core/                # Business logic (team_builder, llm_client, background_runner, etc.)
│   │   └── middleware/          # Logging, rate limiting
│   ├── tests/                   # pytest tests (28 test files, 382 tests)
│   ├── alembic/                 # DB migrations (PostgreSQL)
│   ├── venv/                    # Python 3.13 virtual environment
│   ├── requirements.txt         # Python 3.13 compatible
│   └── Dockerfile
├── frontend/                    # Next.js 16 + React Flow + Monaco Editor
│   ├── src/
│   └── package.json
├── local/                       # Single-user local deployment
│   ├── package.json             # npm run dev (concurrently)
│   ├── docker-compose.yml       # SQLite, no auth
│   └── .env.example
├── cloud/                       # Multi-user cloud deployment
│   ├── docker-compose.yml       # PostgreSQL + Redis + Nginx
│   ├── nginx/                   # Nginx reverse proxy config
│   ├── k8s/                     # Kubernetes manifests
│   └── .env.example
├── docs/                        # V2 architecture plan
├── IMPLEMENTATION_STATUS.md     # Detailed progress tracking
└── CLAUDE.md                    # This file
```

## Development Environment

- **Python**: 3.13.2
- **Virtual env**: `backend/venv/`
- **Activate**: `source backend/venv/bin/activate`
- **Run tests**: `cd backend && source venv/bin/activate && pytest tests/ -v`
- **Run with coverage**: `pytest tests/ -v --cov=app --cov-report=term-missing`
- **Working directory for backend**: `/Users/chengyao/Code/claude_science/backend`
- **Local dev start**: `cd local && npm run dev` (starts backend + frontend concurrently)

## Key Technical Decisions

1. **File-based SQLite for tests** (`sqlite:///./test.db`) - in-memory SQLite has threading issues with TestClient
2. **conftest.py uses autouse fixture** `setup_test_database` that drops/creates tables per test
3. **Pydantic schemas use `from_attributes = True`** (was `orm_mode` in v1)
4. **Forward reference in team.py**: `TeamWithAgents` imports `AgentResponse` at bottom and calls `model_rebuild()`
5. **System prompt auto-generated** from agent's title/expertise/goal/role fields
6. **Mirror agent support**: Agent model has `is_mirror` and `primary_agent_id` fields
7. **Dual code extraction modes**:
   - **Regex-based** (`/extract`): Fast, rule-based extraction for standard markdown code blocks
   - Regex + JSON format extraction (agents output code in JSON path/code format for easy parsing)

## Database Migration Rules (CRITICAL)

### Alembic is the single source of truth for PostgreSQL schema

- **Every model change MUST have a corresponding Alembic migration file**
- `Base.metadata.create_all()` only creates NEW tables; it NEVER adds columns to existing tables
- SQLite local dev may hide missing migrations because `database.py` has band-aid functions (`_ensure_meetings_columns_sqlite`)
- **Always test on PostgreSQL** (or verify Alembic migration) before deploying to Railway

### Writing migrations

```bash
cd backend && source venv/bin/activate
alembic revision --autogenerate -m "description of change"
# Review generated file, then commit
```

### Making migrations idempotent (for DBs bootstrapped by create_all)

When a database was initially created by `create_all()` instead of Alembic, migrations must check before acting:

```python
from sqlalchemy import inspect

def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in columns

def _table_exists(table):
    return table in inspect(op.get_bind()).get_table_names()

# In upgrade(): check before adding
if not _column_exists("meetings", "agenda"):
    op.add_column("meetings", sa.Column(...))
if not _table_exists("webhook_configs"):
    op.create_table(...)
```

### Pydantic + nullable DB columns = 500 errors

When adding new columns to existing tables, old rows will have `NULL`. Response schemas MUST use `Optional`:

```python
# WRONG - will 500 on old rows where value is NULL
agenda_questions: list = []

# CORRECT - accepts None from DB, falls back to default
agenda_questions: Optional[list] = []
```

## Railway Deployment (Nixpacks)

- Railway uses **Nixpacks** (not Docker) — config in `railway.json` + `nixpacks.toml`
- Startup script: **`start.sh`** (not `entrypoint.sh` which is for Docker only)
- `start.sh` runs `alembic upgrade head` before starting uvicorn (for PostgreSQL)
- First-time Alembic on existing DB: `start.sh` auto-stamps initial migration if `alembic_version` table is missing
- Frontend (Next.js) runs on Railway's `$PORT`, backend on internal `127.0.0.1:8000`
- Next.js rewrites proxy `/api/*` → backend

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
POST   /api/meetings/{meeting_id}/run     # Run meeting rounds (synchronous)
POST   /api/meetings/{meeting_id}/run-background # Run in background thread
GET    /api/meetings/{meeting_id}/status  # Lightweight status for polling
GET    /api/artifacts/meeting/{meeting_id} # List meeting artifacts
GET    /api/artifacts/{artifact_id}        # Get artifact
POST   /api/artifacts/                     # Create artifact
PUT    /api/artifacts/{artifact_id}        # Update artifact (bumps version)
DELETE /api/artifacts/{artifact_id}        # Delete artifact
POST   /api/artifacts/meeting/{id}/extract # Auto-extract code from messages (regex-based)
GET    /api/export/meeting/{id}/zip        # Download ZIP
GET    /api/export/meeting/{id}/notebook   # Download Colab notebook
GET    /api/export/meeting/{id}/github     # Get GitHub-ready files
```

## Database Models

**Team**: id, name, description, is_public, created_at, updated_at
**Agent**: id, team_id(FK), name, title, expertise, goal, role, system_prompt, model, model_params(JSON), position_x, position_y, is_mirror, primary_agent_id(FK self), created_at, updated_at
**APIKey**: id, provider, encrypted_key, is_active, created_at, updated_at
**Meeting**: id, team_id(FK), title, description, agenda, agenda_questions, agenda_rules, output_type, context_meeting_ids, participant_agent_ids (optional; if set, only these agents join), status, max_rounds, current_round, created_at, updated_at
**MeetingMessage**: id, meeting_id(FK), agent_id(FK nullable), role, agent_name, content, round_number, created_at
**CodeArtifact**: id, meeting_id(FK), filename, language, content, description, version, created_at, updated_at

## Test Results (Last Run)

- **397/397 tests passed** across 29 test files
- test_main.py (2): root endpoint, health check
- test_models.py (4): create team, create agent, cascade delete, mirror agent
- test_teams_api.py (6): CRUD + 404 handling
- test_agents_api.py (7): CRUD + invalid team + cascade delete
- test_onboarding.py (27): TeamBuilder, MirrorValidator, Onboarding API
- test_llm_client.py (35): Encryption, Provider factory, Providers, API key mgmt, LLM chat
- test_meetings.py (19): MeetingEngine, Meeting CRUD, Meeting run
- test_artifacts.py (19): CodeExtractor, Artifact CRUD, Auto-extract
- test_export.py (11): Exporter, Export API
- test_integration.py (9): Full end-to-end workflows
- test_auth.py (28): Password hashing, JWT tokens, Auth API, Protected endpoints
- test_cache.py (19): InMemoryBackend, RateLimiter, TokenBlocklist, Singleton
- test_ws.py (13): WebSocket connection, user messages, round execution
- test_background.py (13): Background runner, cleanup, API endpoints

## Git Commits

- `089f93a` - feat: Add Export Functionality - ZIP, Colab, GitHub (Step 1.9)
- `f3e18b3` - feat: Add Code Generation with extraction engine (Step 1.8)
- `0f0402d` - feat: Add Visual Editor with React Flow and Monaco Editor (Step 1.7)
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

## Implementation Plan - All Steps Complete

### Step 1.0: Intelligent Onboarding System (DONE)
- `backend/app/core/__init__.py` ✅
- `backend/app/core/team_builder.py` ✅ - TeamBuilder with domain detection, team suggestion, mirror creation
- `backend/app/core/mirror_validator.py` ✅ - Jaccard similarity comparison, review threshold
- `backend/app/schemas/onboarding.py` ✅ - OnboardingStage enum, ChatMessage, DomainAnalysis, TeamSuggestion, etc.
- `backend/app/api/onboarding.py` ✅ - POST `/api/onboarding/chat` + POST `/api/onboarding/generate-team`
- `backend/tests/test_onboarding.py` ✅ - 27 tests covering all components
- LLM calls mockable via injectable `llm_func` callable
- **Flow improvements:** Semantic stage (backend infers stage from context when client omits it; multi-turn at problem/clarification). Editable agent cards in chat (steps 3–4). Agent response language: first user message language, else context, else request `locale` (en/zh). See [docs/ONBOARDING_FLOW.md](docs/ONBOARDING_FLOW.md).

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
- **participant_agent_ids**: optional on Meeting; when set, only those agents participate in run/WS/background. Team page: select agents → "Start meeting (N selected)" creates meeting with only selected agents.
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

### Step 1.7: Visual Editor (DONE)
- `frontend/src/components/AgentNode.tsx` ✅ - Custom React Flow node component
- `frontend/src/app/teams/[teamId]/editor/page.tsx` ✅ - Full visual editor page
- React Flow graph with drag-and-drop agent positioning
- Monaco Editor for system prompt editing in side panel
- Mirror agent connections shown as animated edges

### Step 1.8: Code Generation (DONE)
- `backend/app/models/artifact.py` ✅ - CodeArtifact model with versioning
- `backend/app/core/code_extractor.py` ✅ - Regex code block extraction + filename suggestion
- `backend/app/api/artifacts.py` ✅ - CRUD + auto-extract endpoints (regex and LLM-assisted)
- `backend/tests/test_artifacts.py` ✅ - 19 tests

### Step 1.9: Export Functionality (DONE)
- `backend/app/core/exporter.py` ✅ - ZIP, Colab notebook, GitHub file format
- `backend/app/api/export.py` ✅ - Download endpoints for all formats
- `backend/tests/test_export.py` ✅ - 11 tests

## V1 COMPLETE - All Steps Implemented

All deprecation warnings fixed (SQLAlchemy DeclarativeBase, FastAPI lifespan, datetime.now(UTC), Pydantic ConfigDict).

## V2 Complete (Multi-User Cloud)

See `docs/V2_ARCHITECTURE.md` for architecture. All 6 phases implemented:

| Phase | Feature | Key Files |
|-------|---------|-----------|
| 2.1 | JWT Auth | `core/auth.py`, `api/auth.py`, `models/user.py` |
| 2.2 | PostgreSQL + Alembic | `alembic/`, `database.py` (auto-detect SQLite/PG) |
| 2.3 | Redis Cache | `core/cache.py`, `core/rate_limiter.py`, `core/token_blocklist.py` |
| 2.4 | WebSocket | `api/ws.py` (real-time meeting streaming) |
| 2.5 | Prod Docker | `cloud/docker-compose.yml`, `cloud/nginx/nginx.conf` |
| 2.6 | Kubernetes | `cloud/k8s/` (Deployments, StatefulSet, HPA, Ingress) |

### V2 New Endpoints
```
POST   /api/auth/register          # Create account
POST   /api/auth/login             # Get JWT token pair
POST   /api/auth/refresh           # Refresh access token
GET    /api/auth/me                # Current user info
PUT    /api/auth/me                # Update profile
WS     /ws/meetings/{meeting_id}   # Real-time meeting execution
```

### Deployment Options
```bash
# Local dev (SQLite, no auth)
cd local && npm run dev

# Local Docker (SQLite, no auth)
cd local && docker compose up -d

# Simple cloud (no Docker): Backend on Railway, Frontend on Vercel
# See docs/DEPLOY.md for step-by-step env vars and root directories.

# Production (Nginx + PostgreSQL + Redis + JWT auth)
cd cloud && cp .env.example .env && docker compose up -d

# Kubernetes
cd cloud/k8s && ./deploy.sh
```
