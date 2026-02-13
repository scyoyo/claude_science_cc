from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    PROJECT_NAME: str = "Virtual Lab - Single User"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # Database - SQLite local file
    DATABASE_URL: str = "sqlite:///./data/virtuallab.db"

    # Encryption secret for API key storage
    ENCRYPTION_SECRET: str = "change-me-in-production-use-a-real-secret"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
