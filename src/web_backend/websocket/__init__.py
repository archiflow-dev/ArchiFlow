"""
WebSocket (Socket.IO) server for real-time communication.

Note: socket_app is created in main.py to properly wrap both Socket.IO and FastAPI
"""

from .server import sio
from .manager import ConnectionManager

__all__ = ["sio", "ConnectionManager"]
