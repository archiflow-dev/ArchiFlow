"""
In-memory storage quota implementation for testing.

Tracks quota usage in memory. Useful for tests and development.
"""

import logging
from typing import Dict
from pathlib import Path

from .quota import StorageQuota, QuotaExceededError

logger = logging.getLogger(__name__)


class InMemoryQuota(StorageQuota):
    """
    In-memory quota implementation for testing.

    Tracks usage in a dictionary. Not persistent across restarts.

    Usage:
        quota = InMemoryQuota(limit_bytes=1024*1024)  # 1MB

        # Check and reserve
        if await quota.check_quota("session_1", Path("/workspace"), 1024):
            # Proceed with operation
            pass

        # Get current usage
        usage = quota.get_usage(Path("/workspace"))
    """

    def __init__(self, limit_bytes: int = 1024 * 1024 * 1024):  # 1GB default
        """
        Initialize in-memory quota.

        Args:
            limit_bytes: Total quota limit in bytes
        """
        if limit_bytes <= 0:
            raise ValueError(f"Limit must be positive, got {limit_bytes}")

        self.limit = limit_bytes
        self.usage: Dict[str, int] = {}  # workspace_path -> usage in bytes

        logger.info(f"InMemoryQuota initialized: limit={limit_bytes} bytes")

    async def check_quota(
        self,
        session_id: str,
        workspace_path: Path,
        additional_bytes: int,
    ) -> bool:
        """
        Check if adding bytes would exceed quota.

        Args:
            session_id: Session identifier
            workspace_path: Path to workspace
            additional_bytes: Bytes to check

        Returns:
            True if within quota, False otherwise
        """
        if additional_bytes < 0:
            raise ValueError(f"Additional bytes must be non-negative, got {additional_bytes}")

        key = str(workspace_path.resolve())
        current = self.usage.get(key, 0)

        within_quota = (current + additional_bytes) <= self.limit

        logger.debug(
            f"Quota check: workspace={key}, current={current}, "
            f"requested={additional_bytes}, limit={self.limit}, "
            f"within_quota={within_quota}"
        )

        return within_quota

    def get_usage(self, workspace_path: Path) -> int:
        """
        Get current usage for workspace.

        Args:
            workspace_path: Path to workspace

        Returns:
            Current usage in bytes
        """
        key = str(workspace_path.resolve())
        return self.usage.get(key, 0)

    def get_limit(self) -> int:
        """
        Get quota limit.

        Returns:
            Limit in bytes
        """
        return self.limit

    async def reserve_space(
        self,
        session_id: str,
        workspace_path: Path,
        bytes_to_reserve: int,
    ) -> bool:
        """
        Reserve space (adds to tracked usage).

        Note: This implementation just updates the usage counter.
        It doesn't actually pre-allocate filesystem space.

        Args:
            session_id: Session identifier
            workspace_path: Path to workspace
            bytes_to_reserve: Bytes to reserve

        Returns:
            True if reserved, False if insufficient space
        """
        if bytes_to_reserve < 0:
            raise ValueError(f"Bytes to reserve must be non-negative, got {bytes_to_reserve}")

        key = str(workspace_path.resolve())
        current = self.usage.get(key, 0)

        if (current + bytes_to_reserve) > self.limit:
            logger.warning(
                f"Cannot reserve {bytes_to_reserve} bytes: "
                f"would exceed limit ({self.limit})"
            )
            return False

        self.usage[key] = current + bytes_to_reserve
        logger.debug(f"Reserved {bytes_to_reserve} bytes for {key}")
        return True

    def set_usage(self, workspace_path: Path, usage_bytes: int) -> None:
        """
        Manually set usage for a workspace.

        Useful for testing to simulate existing usage.

        Args:
            workspace_path: Path to workspace
            usage_bytes: Usage in bytes
        """
        if usage_bytes < 0:
            raise ValueError(f"Usage must be non-negative, got {usage_bytes}")

        key = str(workspace_path.resolve())
        self.usage[key] = usage_bytes
        logger.debug(f"Set usage for {key} to {usage_bytes} bytes")

    def reset(self) -> None:
        """Reset all usage tracking. Useful for tests."""
        self.usage.clear()
        logger.debug("Reset all usage tracking")

    def get_all_usage(self) -> Dict[str, int]:
        """
        Get usage for all tracked workspaces.

        Returns:
            Dictionary mapping workspace paths to usage in bytes
        """
        return self.usage.copy()
