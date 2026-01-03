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
from .routes import sessions, agents, artifacts, workflow, messages
from .websocket.server import sio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


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

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")
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


# For direct uvicorn usage: uvicorn src.web_backend.main:socket_app --reload
