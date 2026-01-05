"""
Configuration management for ArchiFlow Web Backend.

Uses Pydantic settings for environment variable support.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "ArchiFlow Web API"
    APP_VERSION: str = "3.1.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/archiflow.db"

    # Security
    SECRET_KEY: str = Field(
        default="change-me-in-production-use-secrets-generate",
        description="Secret key for JWT signing"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Allow all localhost ports 5173-5199 for Vite dev server
        *[f"http://localhost:{port}" for port in range(5173, 5200)],
        *[f"http://127.0.0.1:{port}" for port in range(5173, 5200)],
    ]

    # Workspace Management
    WORKSPACE_BASE_DIR: str = "./data/workspaces"
    MAX_WORKSPACE_SIZE_MB: int = 500
    MAX_FILE_SIZE_MB: int = 50
    MAX_USER_STORAGE_GB: int = 5
    MAX_SESSIONS_PER_USER: int = 20
    WORKSPACE_RETENTION_DAYS: int = 30

    # Agent Framework
    DEFAULT_LLM_PROVIDER: str = "openai"

    # WebSocket
    WEBSOCKET_PING_INTERVAL: int = 25
    WEBSOCKET_PING_TIMEOUT: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def workspace_base_path(self) -> Path:
        """Get the workspace base path as a Path object."""
        return Path(self.WORKSPACE_BASE_DIR).resolve()


# Global settings instance
settings = Settings()
