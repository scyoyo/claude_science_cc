# Virtual Lab Web App (aka Claude Science)

AI-powered research team collaboration platform. Create virtual research teams with AI agents, run collaborative meetings, generate executable code, and export results.

Based on [virtual-lab](https://github.com/zou-group/virtual-lab) by Zou Group @ Stanford.

## Features

- **AI Agent Teams** - Configure AI agents with specific roles (ML Researcher, Bioinformatician, Statistician, etc.) or use built-in templates
- **Collaborative Meetings** - Agents discuss research problems in rounds, with real-time WebSocket streaming; start a meeting with only selected agents from the team page
- **Code Generation** - Auto-extract code from meeting discussions into versioned artifacts
- **Visual Editor** - Drag-and-drop agent graph with React Flow + inline prompt editing with Monaco Editor
- **Multi-Format Export** - ZIP download, Jupyter/Colab notebook, GitHub-ready files
- **Multi-User Support** - JWT auth, RBAC (owner/editor/viewer), team sharing
- **Search & Analytics** - Full-text search, team stats, agent metrics, meeting comparison
- **Onboarding** - AI-guided team composition with semantic stages and editable agent cards; see [docs/ONBOARDING_FLOW.md](docs/ONBOARDING_FLOW.md)

## Quick Start (Local Development)

### Prerequisites

- Python 3.13+
- Node.js 18+
- (Optional) Docker & Docker Compose

### One Command Start

```bash
cd local

# First time only: set up backend + frontend
cd ../backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt && cd ../local
cd ../frontend && npm install && cd ../local
npm install

# Start both backend and frontend
npm run dev
```

This launches both services concurrently:

- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000 (API docs at http://localhost:8000/docs)

Other commands:

```bash
npm test              # Run backend tests (pytest)
npm run build         # Build frontend for production
npm run dev:backend  # Start backend only
npm run dev:frontend # Start frontend only
```

### Configure LLM API Keys

Open **http://localhost:3000/settings** and add your API key for one of:

- OpenAI (GPT-4)
- Anthropic (Claude)
- DeepSeek

You can also set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY` in `local/.env` as fallback.

## Deployment

### Docker Compose

**Development (SQLite, no auth)**

```bash
cd local
docker compose up -d
```

- Frontend: http://localhost:3000  
- Backend: http://localhost:8000

**Production (PostgreSQL + Redis + Nginx)**

```bash
cd cloud
cp .env.example .env
# Edit .env — generate secrets with: openssl rand -hex 32
docker compose up -d
```

### Railway (single service, no Docker)

One Railway service runs frontend + backend; Next.js proxies `/api/*` to the backend. See [docs/DEPLOY.md](docs/DEPLOY.md) for step-by-step env vars and setup.

### Kubernetes

```bash
cd cloud/k8s && ./deploy.sh
```

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v              # All tests
pytest tests/ -v --cov=app    # With coverage
```

There are 33 test files (550+ tests) covering API, core logic, auth, WebSocket, background runner, webhooks, search, templates, and more.

## Project Structure

```
├── backend/                    # FastAPI backend (shared)
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── config.py           # Settings (pydantic-settings, env vars)
│   │   ├── database.py        # SQLAlchemy (SQLite/PostgreSQL)
│   │   ├── models/             # DB models (Team, Agent, Meeting, APIKey, etc.)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── api/                # API routers (teams, agents, meetings, auth, etc.)
│   │   ├── core/               # Business logic (LLM, meeting engine, team builder, etc.)
│   │   └── middleware/         # Logging, rate limiting
│   ├── tests/                  # pytest (33 test files)
│   ├── alembic/                # DB migrations (PostgreSQL)
│   └── requirements.txt
├── frontend/                   # Next.js 16 + React 19 (shared)
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   ├── components/         # React components (e.g. AgentNode, editor)
│   │   ├── contexts/           # Auth context
│   │   ├── hooks/              # WebSocket hook
│   │   ├── lib/                # API client, auth helpers
│   │   └── types/              # TypeScript types
│   └── package.json
├── local/                      # Single-user local deployment
│   ├── package.json            # npm run dev (concurrently)
│   └── docker-compose.yml      # SQLite, no auth
├── cloud/                      # Multi-user cloud deployment
│   ├── docker-compose.yml      # PostgreSQL + Redis + Nginx
│   ├── nginx/                  # Nginx reverse proxy config
│   └── k8s/                    # Kubernetes manifests
├── docs/                       # Architecture and flows
│   ├── DEPLOY.md               # Railway deployment guide
│   ├── ONBOARDING_FLOW.md      # Onboarding wizard behavior
│   └── V2_ARCHITECTURE.md      # V2 multi-user architecture
└── CLAUDE.md                   # Development guide (env, migrations, API list)
```

## API Overview

Endpoints are available under `/api/` and `/api/v1/`. Interactive docs: http://localhost:8000/docs .

| Group      | Description |
|-----------|-------------|
| Teams     | CRUD, sharing, statistics, config export/import, members |
| Agents    | CRUD, batch ops, clone, templates, metrics |
| Meetings  | CRUD, run, run-background, status, message, summary, transcript, clone, compare |
| Artifacts | CRUD, auto-extract code from meeting messages |
| Onboarding| AI-guided team composition: `/api/onboarding/chat`, `/api/onboarding/generate-team` |
| LLM       | Providers, API key management, `/api/llm/chat` |
| Auth      | Register, login, refresh, profile |
| Search    | Full-text search teams & agents |
| Templates | Predefined agent presets |
| Webhooks  | Event notifications (e.g. meeting complete) |
| Dashboard | Aggregated stats |
| Export    | ZIP, Jupyter notebook, GitHub-ready files |
| WebSocket | Real-time meeting streaming: `/ws/meetings/{meeting_id}` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/virtuallab.db` | Database connection string |
| `ENCRYPTION_SECRET` | (insecure default) | Secret for encrypting stored API keys |
| `AUTH_ENABLED` | `false` | Enable JWT authentication |
| `JWT_SECRET` | (insecure default) | Secret for signing JWT tokens |
| `REDIS_URL` | (empty = in-memory) | Redis for cache/rate limiting |
| `FRONTEND_URL` | `http://localhost:3000` | Used for CORS |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` | (empty) | Optional env fallback for LLM calls |

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Pydantic v2, SQLite/PostgreSQL
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS, React Flow, Monaco Editor
- **Infra**: Docker Compose, Nginx, Redis, Alembic, Kubernetes

## Documentation

- **[CLAUDE.md](CLAUDE.md)** — Development guide: environment setup, database migrations, testing, API reference
- **[docs/DEPLOY.md](docs/DEPLOY.md)** — Railway deployment guide (single-service setup)
- **[docs/ONBOARDING_FLOW.md](docs/ONBOARDING_FLOW.md)** — AI-guided team composition flow
- **[docs/V2_ARCHITECTURE.md](docs/V2_ARCHITECTURE.md)** — Multi-user cloud architecture design

## Testing

The project has **555+ tests** covering all features:

```bash
cd backend && source venv/bin/activate
pytest tests/ -v                    # Run all tests
pytest tests/ -v --cov=app          # With coverage report
```

Test categories:
- **Unit tests**: Core logic (LLM client, meeting engine, code extractor, team builder)
- **API tests**: All endpoints (teams, agents, meetings, auth, search, webhooks)
- **Integration tests**: End-to-end workflows
- **WebSocket tests**: Real-time meeting streaming
- **Background tests**: Async meeting execution

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`cd backend && pytest tests/ -v`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Based on [virtual-lab](https://github.com/zou-group/virtual-lab) by Zou Group @ Stanford
- Built with FastAPI, Next.js, React Flow, and Monaco Editor
