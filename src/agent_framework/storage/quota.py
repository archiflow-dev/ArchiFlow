"""
Storage quota interface for enforcing storage limits.

Provides abstraction for enforcing storage quotas at different levels:
- Per-workspace
- Per-user
- Global
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class StorageQuota(ABC):
    """
    Interface for storage quota enforcement.

    Implementations can enforce quotas at different levels:
    - Per-workspace (default for SandboxRuntime)
    - Per-user (multi-tenant systems)
    - Global (system-wide limits)

    Usage:
        quota = InMemoryQuota(limit_bytes=1024*1024*1024)  # 1GB

        # Check before operation
        if await quota.check_quota(session_id, workspace, 1024):
            # Safe to proceed
            pass
    """

    @abstractmethod
    async def check_quota(
        self,
        session_id: str,
        workspace_path: Path,
        additional_bytes: int,
    ) -> bool:
        """
        Check if adding additional bytes would exceed quota.

        Args:
            session_id: Session identifier
            workspace_path: Path to workspace directory
            additional_bytes: Bytes to add

        Returns:
            True if within quota, False if would exceed

        Raises:
            ValueError: If parameters are invalid
        """
        pass

    @abstractmethod
    def get_usage(self, workspace_path: Path) -> int:
        """
        Get current storage usage in bytes.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            Current usage in bytes (non-negative integer)

        Raises:
            ValueError: If path is invalid
        """
        pass

    @abstractmethod
    def get_limit(self) -> int:
        """
        Get storage quota limit in bytes.

        Returns:
            Limit in bytes (positive integer)

        Note:
            This is a constant for the quota instance
        """
        pass

    @abstractmethod
    async def reserve_space(
        self,
        session_id: str,
        workspace_path: Path,
        bytes_to_reserve: int,
    ) -> bool:
        """
        Reserve space for an operation.

        This is a hint to the quota system that space will be used.
        Some implementations may pre-allocate, others may just check.

        Args:
            session_id: Session identifier
            workspace_path: Path to workspace directory
            bytes_to_reserve: Bytes to reserve

        Returns:
            True if space reserved successfully, False if insufficient

        Note:
            Not all implementations support true reservation.
            Most will just call check_quota().
        """
        pass


class QuotaExceededError(Exception):
    """Raised when storage quota is exceeded."""

    def __init__(
        self,
        message: str,
        current_usage: int,
        requested_bytes: int,
        limit: int,
    ):
        """
        Initialize quota exceeded error.

        Args:
            message: Error message
            current_usage: Current usage in bytes
            requested_bytes: Bytes requested
            limit: Quota limit in bytes
        """
        self.current_usage = current_usage
        self.requested_bytes = requested_bytes
        self.limit = limit
        super().__init__(message)

    def __str__(self) -> str:
        """Format error message with details."""
        mb_usage = self.current_usage / (1024 * 1024)
        mb_requested = self.requested_bytes / (1024 * 1024)
        mb_limit = self.limit / (1024 * 1024)

        return (
            f"{super().__str__()}: "
            f"Current: {mb_usage:.2f}MB, "
            f"Requested: {mb_requested:.2f}MB, "
            f"Limit: {mb_limit:.2f}MB"
        )
