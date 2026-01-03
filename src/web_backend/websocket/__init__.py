"""
WebSocket (Socket.IO) server for real-time communication.
"""

from .server import sio, socket_app
from .manager import ConnectionManager

__all__ = ["sio", "socket_app", "ConnectionManager"]
