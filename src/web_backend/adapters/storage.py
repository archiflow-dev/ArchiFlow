"""
Storage Quota Adapter for Web Backend.

Bridges the web backend's StorageManager to the framework's StorageQuota interface.
"""

from pathlib import Path
from typing import Optional

# Import framework interface
try:
    from agent_framework.storage.quota import StorageQuota
except ImportError:
    # For standalone testing
    StorageQuota = object

from ..services.storage_manager import StorageManager, StorageLimitError


class WebStorageQuota(StorageQuota):
    """
    Adapter that bridges StorageManager to StorageQuota interface.

    This allows the web backend's existing storage management to work with
    the framework's sandbox runtime.

    The adapter handles the semantic difference:
    - StorageManager: User/session-based storage limits (multi-tenant aware)
    - StorageQuota: Workspace-based storage tracking (framework level)

    Usage:
        quota = WebStorageQuota(
            user_id="user_123",
            session_id="session_456",
            storage_manager=storage_manager,
        )
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        storage_manager: Optional[StorageManager] = None,
    ):
        """
        Initialize the storage quota adapter.

        Args:
            user_id: User ID for this session
            session_id: Session ID
            storage_manager: StorageManager instance (uses singleton if None)
        """
        from ..services.storage_manager import get_storage_manager

        self.user_id = user_id
        self.session_id = session_id
        self.storage_manager = storage_manager or get_storage_manager()

        # Cache workspace path
        from ..services.workspace_manager import get_workspace_manager
        wm = get_workspace_manager()
        self._workspace_path = wm.get_workspace_path(user_id, session_id)

    async def check_quota(
        self,
        session_id: str,
        workspace_path: Path,
        additional_bytes: int,
    ) -> bool:
        """
        Check if adding additional_bytes would exceed quota.

        Args:
            session_id: Session identifier (ignored, uses self.session_id)
            workspace_path: Path to workspace (ignored, uses self._workspace_path)
            additional_bytes: Bytes to add

        Returns:
            True if within quota, False if would exceed

        Raises:
            ValueError: If additional_bytes is negative
        """
        if additional_bytes < 0:
            raise ValueError(f"Additional bytes must be non-negative, got {additional_bytes}")

        try:
            # Check if file upload would exceed limits
            self.storage_manager.check_file_upload(
                user_id=self.user_id,
                session_id=self.session_id,
                file_size=additional_bytes,
            )
            return True
        except StorageLimitError:
            return False

    def get_usage(self, workspace_path: Path) -> int:
        """
        Get current storage usage in bytes.

        Args:
            workspace_path: Path to workspace (ignored, uses self._workspace_path)

        Returns:
            Current usage in bytes
        """
        return self.storage_manager.workspace_manager.get_workspace_size(
            self.user_id,
            self.session_id,
        )

    def get_limit(self) -> int:
        """
        Get quota limit in bytes.

        Returns:
            Limit in bytes
        """
        # Convert MB to bytes
        return self.storage_manager.limits.max_workspace_size_mb * 1024 * 1024

    async def reserve_space(
        self,
        session_id: str,
        workspace_path: Path,
        bytes_to_reserve: int,
    ) -> bool:
        """
        Reserve space for an operation.

        Note: The web backend's StorageManager doesn't support reservation.
        This method always returns True if within quota, as actual usage
        is tracked by the filesystem.

        Args:
            session_id: Session identifier (ignored)
            workspace_path: Path to workspace (ignored)
            bytes_to_reserve: Bytes to reserve

        Returns:
            True if space available (always returns True for compatibility)

        Raises:
            ValueError: If bytes_to_reserve is negative
        """
        if bytes_to_reserve < 0:
            raise ValueError(f"Bytes to reserve must be non-negative, got {bytes_to_reserve}")

        # Just check quota - actual reservation not supported
        return await self.check_quota(session_id, workspace_path, bytes_to_reserve)

    def set_usage(self, workspace_path: Path, usage: int) -> None:
        """
        Set usage (no-op for web backend).

        The web backend tracks usage via filesystem scanning, not manual tracking.

        Args:
            workspace_path: Path to workspace (ignored)
            usage: Usage in bytes (ignored)

        Note:
            This is a no-op because StorageManager calculates usage from disk.
        """
        pass

    def reset(self) -> None:
        """
        Reset all usage tracking (no-op for web backend).

        Note:
            This is a no-op because StorageManager calculates usage from disk.
        """
        pass

    def get_all_usage(self) -> dict:
        """
        Get usage for all workspaces (not supported for web backend).

        Returns:
            Empty dict (web backend tracks per-user/session)

        Note:
            This returns an empty dict because WebStorageQuota is scoped
            to a single session. Use StorageManager.get_user_usage() instead
            for multi-workspace metrics.
        """
        return {}

    def get_workspace_path(self) -> Path:
        """
        Get the workspace path for this adapter.

        Returns:
            Workspace path
        """
        return self._workspace_path

    def get_user_usage_info(self) -> dict:
        """
        Get detailed user usage information.

        Returns:
            Dict with usage statistics from StorageManager

        Example:
            {
                "used_bytes": 1024000,
                "used_gb": 0.001,
                "max_gb": 5,
                "percent_used": 0.02,
                "session_count": 3,
                "max_sessions": 20,
            }
        """
        return self.storage_manager.get_user_usage(self.user_id)

    def get_workspace_usage_info(self) -> dict:
        """
        Get detailed workspace usage information.

        Returns:
            Dict with usage statistics from StorageManager

        Example:
            {
                "used_bytes": 512000,
                "used_mb": 0.5,
                "max_mb": 500,
                "percent_used": 0.1,
                "remaining_bytes": 523763000,
            }
        """
        return self.storage_manager.get_workspace_usage(
            self.user_id,
            self.session_id,
        )
