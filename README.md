# Virtual Lab Web App (aka Claude Science)

AI-powered research team collaboration platform. Create virtual research teams with AI agents, run collaborative meetings, generate executable code, and export results.

Based on [virtual-lab](https://github.com/zou-group/virtual-lab) by Zou Group @ Stanford.

## Features

- **AI Agent Teams** - Configure AI agents with specific roles (ML Researcher, Bioinformatician, Statistician, etc.) or use 10 built-in templates
- **Collaborative Meetings** - Agents discuss research problems in rounds, with real-time WebSocket streaming
- **Code Generation** - Auto-extract code from meeting discussions into versioned artifacts
- **Visual Editor** - Drag-and-drop agent graph with React Flow + inline prompt editing with Monaco Editor
- **Multi-Format Export** - ZIP download, Jupyter notebook, GitHub push
- **Multi-User Support** - JWT auth, RBAC (owner/editor/viewer), team sharing
- **Search & Analytics** - Full-text search, team stats, agent metrics, meeting comparison

## Quick Start (Local Development)

### Prerequisites

- Python 3.13+
- Node.js 18+
- (Optional) Docker & Docker Compose

### 1. Backend

```bash
cd single-user-local/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload
```

Backend runs at **http://localhost:8000**. API docs at **http://localhost:8000/docs**.

### 2. Frontend

```bash
cd single-user-local/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at **http://localhost:3000**.

### 3. Configure LLM API Keys

Open **http://localhost:3000/settings** and add your API key for one of:
- OpenAI (GPT-4)
- Anthropic (Claude)
- DeepSeek

## Docker Compose

### Development (SQLite, no auth)

```bash
cd single-user-local
docker compose up -d
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### Production (PostgreSQL + Redis + Nginx)

```bash
cd single-user-local
cp .env.example .env

# Edit .env - generate real secrets with: openssl rand -hex 32
vim .env

docker compose -f docker-compose.prod.yml up -d
```

## Running Tests

```bash
cd single-user-local/backend
source venv/bin/activate
pytest tests/ -v              # 329 tests
pytest tests/ -v --cov=app    # with coverage
```

## Project Structure

```
single-user-local/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (env vars)
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/              # DB models (Team, Agent, Meeting, etc.)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── api/                 # API routers (13 modules)
│   │   ├── core/                # Business logic (LLM, meetings, auth, etc.)
│   │   └── middleware/          # Logging, rate limiting
│   ├── tests/                   # 27 test files
│   ├── alembic/                 # DB migrations (PostgreSQL)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages
│   │   ├── components/          # React components
│   │   ├── contexts/            # Auth context
│   │   ├── hooks/               # WebSocket hook
│   │   ├── lib/                 # API client, auth helpers
│   │   └── types/               # TypeScript types
│   └── package.json
├── k8s/                         # Kubernetes manifests
├── nginx/                       # Nginx reverse proxy config
├── docker-compose.yml           # Dev (SQLite)
└── docker-compose.prod.yml      # Prod (PG + Redis + Nginx)
```

## API Overview

All endpoints available under `/api/` and `/api/v1/`. Full interactive docs at `/docs`.

| Group | Endpoints | Description |
|-------|-----------|-------------|
| Teams | 5 + stats/export/import/members | CRUD, sharing, statistics, config export |
| Agents | 5 + batch/clone/metrics | CRUD, batch ops, templates, performance metrics |
| Meetings | 6 + summary/transcript/clone/compare | CRUD, execution, analysis |
| Artifacts | 6 | Code artifact CRUD + auto-extraction |
| Onboarding | 2 | AI-guided team composition |
| LLM | 5 | API key management, provider config |
| Auth | 4 | Register, login, refresh, profile |
| Search | 2 | Full-text search teams & agents |
| Templates | 3 | 10 predefined agent presets |
| Webhooks | 5 | Event notifications (meeting complete, etc.) |
| Export | 3 | ZIP, Jupyter notebook, GitHub |
| WebSocket | 1 | Real-time meeting streaming |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/virtuallab.db` | Database connection string |
| `ENCRYPTION_SECRET` | (insecure default) | Secret for encrypting stored API keys |
| `AUTH_ENABLED` | `false` | Enable JWT authentication |
| `JWT_SECRET` | (insecure default) | Secret for signing JWT tokens |
| `REDIS_URL` | (empty = in-memory) | Redis connection for cache/rate limiting |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Pydantic v2, SQLite/PostgreSQL
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS, React Flow, Monaco Editor
- **Infra**: Docker Compose, Nginx, Redis, Alembic, Kubernetes, GitHub Actions CI

## License

MIT
