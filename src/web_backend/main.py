"""
ArchiFlow Web Backend - FastAPI Application

Main entry point for the web backend API server.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys

from .config import settings
from .database.connection import init_db, close_db
from .routes import sessions, agents, artifacts, workflow, messages, agent_execution
from .websocket.server import sio
from .services import (
    get_workspace_manager,
    get_storage_manager,
    get_audit_logger,
    init_web_agent_factory,
    get_runner_pool,
    SandboxMode,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Disable verbose SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)

# Enable detailed logging for agent-related modules
agent_modules = [
    'web_backend.services.agent_runner',
    'web_backend.services.agent_session_manager',
    'web_backend.services.web_agent_factory',
    'web_backend.websocket.session_emitter',
    'web_backend.websocket.server',
    'message_queue',
    'agent_framework',
]
for module in agent_modules:
    logging.getLogger(module).setLevel(logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize database
    await init_db()

    # Create data directories
    from pathlib import Path
    Path(settings.WORKSPACE_BASE_DIR).mkdir(parents=True, exist_ok=True)
    Path("./data").mkdir(parents=True, exist_ok=True)

    # Initialize services
    workspace_manager = get_workspace_manager()
    storage_manager = get_storage_manager()
    audit_logger = get_audit_logger()

    # Initialize WebAgentFactory
    sandbox_mode = SandboxMode.STRICT if not settings.DEBUG else SandboxMode.PERMISSIVE
    init_web_agent_factory(
        workspace_manager=workspace_manager,
        storage_manager=storage_manager,
        audit_logger=audit_logger,
        sandbox_mode=sandbox_mode,
    )
    logger.info(f"WebAgentFactory initialized with sandbox_mode={sandbox_mode.value}")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Stop all running agents
    runner_pool = get_runner_pool()
    await runner_pool.stop_all()
    logger.info("All agent runners stopped")

    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Web backend for ArchiFlow AI agent framework",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.exception(f"Unhandled exception: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        }
    )


# Health check endpoint
@app.get(f"{settings.API_PREFIX}/health")
async def health_check():
    """
    Health check endpoint.

    Returns application status and version information.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
    }


# Include API routers
app.include_router(
    sessions.router,
    prefix=f"{settings.API_PREFIX}/sessions",
    tags=["sessions"]
)

app.include_router(
    agents.router,
    prefix=f"{settings.API_PREFIX}/agents",
    tags=["agents"]
)

app.include_router(
    artifacts.router,
    prefix=f"{settings.API_PREFIX}/sessions/{{session_id}}/artifacts",
    tags=["artifacts"]
)

app.include_router(
    workflow.router,
    prefix=f"{settings.API_PREFIX}/sessions/{{session_id}}/workflow",
    tags=["workflow"]
)

app.include_router(
    messages.router,
    prefix=f"{settings.API_PREFIX}/sessions/{{session_id}}/messages",
    tags=["messages"]
)

app.include_router(
    agent_execution.router,
    prefix=f"{settings.API_PREFIX}/sessions",
    tags=["agent-execution"]
)


# Mount Socket.IO
# The Socket.IO server is mounted at /socket.io by default
import socketio

socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path="socket.io"
)


def create_app() -> socketio.ASGIApp:
    """
    Create the ASGI application.

    Returns the Socket.IO wrapped FastAPI app for use with uvicorn.
    """
    return socket_app


# ============================================================================
# IMPORTANT: Use socket_app NOT app when running with uvicorn!
#
# ❌ WRONG: uvicorn src.web_backend.main:app --reload
#           This only runs FastAPI, WebSocket connections will FAIL with 403
#
# ✅ CORRECT: uvicorn src.web_backend.main:socket_app --reload
#            This runs both FastAPI AND Socket.IO WebSocket server
# ============================================================================
