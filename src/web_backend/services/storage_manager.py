"""
Storage Manager for ArchiFlow Web Backend.

Manages storage quotas and limits for workspaces.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ..config import settings
from .workspace_manager import WorkspaceManager, get_workspace_manager

logger = logging.getLogger(__name__)


class StorageLimitError(Exception):
    """Raised when storage limits are exceeded."""
    pass


@dataclass
class StorageLimits:
    """Storage limits configuration."""
    max_workspace_size_mb: int = 500        # Max 500MB per session
    max_file_size_mb: int = 50              # Max 50MB per file
    max_total_user_storage_gb: int = 5      # Max 5GB per user (all sessions)
    max_sessions_per_user: int = 20         # Max 20 active sessions
    retention_days: int = 30                # Keep workspaces for 30 days

    @classmethod
    def from_settings(cls) -> 'StorageLimits':
        """Create StorageLimits from application settings."""
        return cls(
            max_workspace_size_mb=settings.MAX_WORKSPACE_SIZE_MB,
            max_file_size_mb=settings.MAX_FILE_SIZE_MB,
            max_total_user_storage_gb=settings.MAX_USER_STORAGE_GB,
            max_sessions_per_user=settings.MAX_SESSIONS_PER_USER,
            retention_days=settings.WORKSPACE_RETENTION_DAYS,
        )


class StorageManager:
    """
    Manages storage quotas and limits.

    Enforces:
    - Maximum file size
    - Maximum workspace size
    - Maximum user total storage
    - Maximum sessions per user
    """

    def __init__(
        self,
        workspace_manager: Optional[WorkspaceManager] = None,
        limits: Optional[StorageLimits] = None
    ):
        """
        Initialize StorageManager.

        Args:
            workspace_manager: WorkspaceManager instance
            limits: Storage limits configuration
        """
        self.workspace_manager = workspace_manager or get_workspace_manager()
        self.limits = limits or StorageLimits.from_settings()

    def check_file_size(self, file_size: int) -> bool:
        """
        Check if a file size is within limits.

        Args:
            file_size: Size in bytes

        Returns:
            True if within limits

        Raises:
            StorageLimitError: If file size exceeds limit
        """
        max_size = self.limits.max_file_size_mb * 1024 * 1024

        if file_size > max_size:
            raise StorageLimitError(
                f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds "
                f"limit of {self.limits.max_file_size_mb}MB"
            )

        return True

    def check_file_upload(
        self,
        user_id: str,
        session_id: str,
        file_size: int
    ) -> bool:
        """
        Check if a file upload is allowed.

        Args:
            user_id: User ID
            session_id: Session ID
            file_size: Size of file to upload in bytes

        Returns:
            True if upload is allowed

        Raises:
            StorageLimitError: If any limit would be exceeded
        """
        # Check file size limit
        self.check_file_size(file_size)

        # Check workspace size limit
        current_workspace_size = self.workspace_manager.get_workspace_size(
            user_id, session_id
        )
        max_workspace = self.limits.max_workspace_size_mb * 1024 * 1024

        if current_workspace_size + file_size > max_workspace:
            raise StorageLimitError(
                f"Workspace would exceed {self.limits.max_workspace_size_mb}MB limit"
            )

        # Check user total storage limit
        total_user_storage = self.get_user_total_storage(user_id)
        max_user = self.limits.max_total_user_storage_gb * 1024 * 1024 * 1024

        if total_user_storage + file_size > max_user:
            raise StorageLimitError(
                f"User storage would exceed {self.limits.max_total_user_storage_gb}GB limit"
            )

        return True

    def check_session_limit(self, user_id: str) -> bool:
        """
        Check if user can create a new session.

        Args:
            user_id: User ID

        Returns:
            True if user can create new session

        Raises:
            StorageLimitError: If session limit reached
        """
        session_count = self.get_user_session_count(user_id)

        if session_count >= self.limits.max_sessions_per_user:
            raise StorageLimitError(
                f"Maximum sessions ({self.limits.max_sessions_per_user}) reached"
            )

        return True

    def get_user_total_storage(self, user_id: str) -> int:
        """
        Calculate total storage used by a user across all sessions.

        Args:
            user_id: User ID

        Returns:
            Total storage in bytes
        """
        user_path = self.workspace_manager.base_path / user_id
        if not user_path.exists():
            return 0

        total = 0
        for session_dir in user_path.iterdir():
            if session_dir.is_dir():
                for path in session_dir.rglob("*"):
                    if path.is_file():
                        try:
                            total += path.stat().st_size
                        except OSError:
                            pass
        return total

    def get_user_session_count(self, user_id: str) -> int:
        """
        Count sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions
        """
        workspaces = self.workspace_manager.list_user_workspaces(user_id)
        return len(workspaces)

    def get_workspace_usage(self, user_id: str, session_id: str) -> dict:
        """
        Get storage usage information for a workspace.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Usage information dict
        """
        size = self.workspace_manager.get_workspace_size(user_id, session_id)
        max_size = self.limits.max_workspace_size_mb * 1024 * 1024

        return {
            "used_bytes": size,
            "used_mb": size / 1024 / 1024,
            "max_mb": self.limits.max_workspace_size_mb,
            "percent_used": (size / max_size * 100) if max_size > 0 else 0,
            "remaining_bytes": max(0, max_size - size),
        }

    def get_user_usage(self, user_id: str) -> dict:
        """
        Get storage usage information for a user.

        Args:
            user_id: User ID

        Returns:
            Usage information dict
        """
        total = self.get_user_total_storage(user_id)
        max_storage = self.limits.max_total_user_storage_gb * 1024 * 1024 * 1024
        session_count = self.get_user_session_count(user_id)

        return {
            "used_bytes": total,
            "used_gb": total / 1024 / 1024 / 1024,
            "max_gb": self.limits.max_total_user_storage_gb,
            "percent_used": (total / max_storage * 100) if max_storage > 0 else 0,
            "session_count": session_count,
            "max_sessions": self.limits.max_sessions_per_user,
        }


# Global singleton instance
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """Get the global StorageManager instance."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager
