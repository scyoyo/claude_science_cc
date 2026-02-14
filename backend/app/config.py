from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Look for .env in backend/ first, then local/ (for local dev via `cd local && npm run dev`)
_backend_dir = Path(__file__).resolve().parent.parent
_env_files = [_backend_dir / ".env", _backend_dir.parent / "local" / ".env"]
_env_file = next((f for f in _env_files if f.exists()), ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_env_file))

    PROJECT_NAME: str = "Virtual Lab - Single User"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # Database - SQLite local file
    DATABASE_URL: str = "sqlite:///./data/virtuallab.db"

    # LLM API Keys (env var fallback when no key stored in DB)
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""

    # GitHub (optional, for future GitHub push export)
    GITHUB_TOKEN: str = ""

    # Frontend URL (used for CORS)
    FRONTEND_URL: str = "http://localhost:3000"

    # Encryption secret for API key storage
    ENCRYPTION_SECRET: str = "change-me-in-production-use-a-real-secret"

    # Authentication
    AUTH_ENABLED: bool = False  # V1 backward compat: disabled by default
    JWT_SECRET: str = "change-me-jwt-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Onboarding LLM (empty API key = template mode, no LLM calls)
    ONBOARDING_API_KEY: str = ""
    ONBOARDING_LLM_PROVIDER: str = "anthropic"
    ONBOARDING_LLM_MODEL: str = "claude-sonnet-4-5-20250929"

    # Redis (empty string = use in-memory backend)
    REDIS_URL: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
