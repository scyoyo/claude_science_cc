from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import init_db
from app.api import teams, agents, onboarding, llm, meetings, artifacts, export, auth, ws, search, templates, webhooks
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    init_db()
    yield


tags_metadata = [
    {"name": "teams", "description": "Team management and sharing"},
    {"name": "agents", "description": "AI agent CRUD and batch operations"},
    {"name": "meetings", "description": "Meeting lifecycle and execution"},
    {"name": "artifacts", "description": "Code artifact management"},
    {"name": "onboarding", "description": "AI-powered team composition assistant"},
    {"name": "llm", "description": "LLM provider and API key management"},
    {"name": "auth", "description": "Authentication and user management"},
    {"name": "search", "description": "Full-text search across teams and agents"},
    {"name": "templates", "description": "Predefined agent templates and presets"},
    {"name": "export", "description": "Export meetings as ZIP, notebook, or GitHub"},
    {"name": "websocket", "description": "Real-time meeting execution via WebSocket"},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Virtual Lab: AI-powered research team collaboration platform. "
    "Create virtual research teams, configure AI agents, run collaborative meetings, "
    "and export generated code.",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

# Middleware (order matters: last added = first executed)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers under both /api/ and /api/v1/ for versioning
_api_routers = [
    teams.router, agents.router, onboarding.router, llm.router,
    meetings.router, artifacts.router, export.router, auth.router,
    search.router, templates.router, webhooks.router,
]
for router in _api_routers:
    app.include_router(router, prefix="/api")
    app.include_router(router, prefix="/api/v1")

app.include_router(ws.router)


@app.get("/")
def read_root():
    return {
        "message": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "type": "single-user-local"
    }


@app.get("/health")
def health_check():
    """Detailed health check: DB connectivity + cache/Redis status."""
    checks = {}

    # Database check
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Cache/Redis check
    try:
        from app.core.cache import get_cache
        cache = get_cache()
        cache.set("health_check", "1", ttl=10)
        checks["cache"] = "ok"
    except Exception as e:
        checks["cache"] = f"error: {e}"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks, "version": settings.VERSION}
