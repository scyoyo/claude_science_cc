from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api import teams, agents, onboarding, llm, meetings, artifacts, export, auth, ws
from app.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    init_db()
    yield


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# Middleware (order matters: last added = first executed)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(teams.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(llm.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
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
    return {"status": "healthy"}
