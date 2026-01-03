"""
Tests for configuration management.
"""

import pytest
from pathlib import Path


def test_settings_defaults():
    """Test that settings have sensible defaults."""
    from src.web_backend.config import Settings

    # Create settings with defaults
    settings = Settings()

    assert settings.APP_NAME == "ArchiFlow Web API"
    assert settings.APP_VERSION == "3.1.0"
    assert settings.DEBUG is False
    assert settings.API_PREFIX == "/api"
    assert settings.PORT == 8000


def test_settings_cors_origins():
    """Test CORS origins configuration."""
    from src.web_backend.config import Settings

    settings = Settings()

    assert isinstance(settings.CORS_ORIGINS, list)
    assert len(settings.CORS_ORIGINS) > 0
    # Default should include localhost dev servers
    assert any("localhost" in origin for origin in settings.CORS_ORIGINS)


def test_settings_workspace_limits():
    """Test workspace limit settings."""
    from src.web_backend.config import Settings

    settings = Settings()

    assert settings.MAX_WORKSPACE_SIZE_MB > 0
    assert settings.MAX_FILE_SIZE_MB > 0
    assert settings.MAX_USER_STORAGE_GB > 0
    assert settings.MAX_SESSIONS_PER_USER > 0
    assert settings.WORKSPACE_RETENTION_DAYS > 0


def test_settings_workspace_path():
    """Test workspace base path property."""
    from src.web_backend.config import Settings

    settings = Settings()

    path = settings.workspace_base_path
    assert isinstance(path, Path)
    assert path.is_absolute()


def test_settings_database_url():
    """Test database URL configuration."""
    from src.web_backend.config import Settings

    settings = Settings()

    assert settings.DATABASE_URL is not None
    assert "sqlite" in settings.DATABASE_URL or "postgresql" in settings.DATABASE_URL


def test_settings_security():
    """Test security settings."""
    from src.web_backend.config import Settings

    settings = Settings()

    assert settings.SECRET_KEY is not None
    assert len(settings.SECRET_KEY) > 0
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


def test_settings_websocket():
    """Test WebSocket settings."""
    from src.web_backend.config import Settings

    settings = Settings()

    assert settings.WEBSOCKET_PING_INTERVAL > 0
    assert settings.WEBSOCKET_PING_TIMEOUT > 0
    # Timeout should be greater than interval
    assert settings.WEBSOCKET_PING_TIMEOUT > settings.WEBSOCKET_PING_INTERVAL


def test_settings_environment_override():
    """Test that settings can be overridden via environment."""
    import os

    # Set environment variable
    os.environ["DEBUG"] = "true"
    os.environ["PORT"] = "9000"

    try:
        # Reload settings
        from src.web_backend.config import Settings
        settings = Settings()

        assert settings.DEBUG is True
        assert settings.PORT == 9000
    finally:
        # Clean up
        del os.environ["DEBUG"]
        del os.environ["PORT"]
