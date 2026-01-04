"""
Filesystem-based storage quota implementation.

Calculates quota based on actual filesystem usage.
"""

import logging
from pathlib import Path
from typing import Optional

from .quota import StorageQuota

logger = logging.getLogger(__name__)


class FileSystemQuota(StorageQuota):
    """
    Quota based on actual filesystem usage.

    Calculates usage by scanning directory size.
    More accurate than InMemoryQuota but slower for large directories.

    Usage:
        quota = FileSystemQuota(limit_bytes=1024*1024*1024)  # 1GB

        usage = quota.get_usage(Path("/workspace/session_123"))
    """

    def __init__(self, limit_bytes: int, cache_ttl_seconds: float = 5.0):
        """
        Initialize filesystem quota.

        Args:
            limit_bytes: Total quota limit in bytes
            cache_ttl_seconds: How long to cache usage calculations (default 5s)
        """
        if limit_bytes <= 0:
            raise ValueError(f"Limit must be positive, got {limit_bytes}")

        self.limit = limit_bytes
        self.cache_ttl = cache_ttl_seconds
        self._cache: Optional[dict] = None

        logger.info(
            f"FileSystemQuota initialized: limit={limit_bytes} bytes, "
            f"cache_ttl={cache_ttl_seconds}s"
        )

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

        current = self.get_usage(workspace_path)
        return (current + additional_bytes) <= self.limit

    def get_usage(self, workspace_path: Path) -> int:
        """
        Calculate actual filesystem usage.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            Total usage in bytes
        """
        if not workspace_path.exists():
            return 0

        # Check cache
        if self._cache:
            key = str(workspace_path.resolve())
            if key in self._cache:
                cached_usage, timestamp = self._cache[key]
                # Import here to avoid circular dependency
                import time
                if time.time() - timestamp < self.cache_ttl:
                    return cached_usage

        # Calculate actual usage
        total = self._calculate_size(workspace_path)

        # Update cache
        if self._cache is None:
            self._cache = {}
        key = str(workspace_path.resolve())
        import time
        self._cache[key] = (total, time.time())

        return total

    def get_limit(self) -> int:
        """Get quota limit."""
        return self.limit

    async def reserve_space(
        self,
        session_id: str,
        workspace_path: Path,
        bytes_to_reserve: int,
    ) -> bool:
        """
        Check if space can be reserved.

        Note: This implementation doesn't pre-allocate space.
        It just checks if there's enough room.

        Args:
            session_id: Session identifier
            workspace_path: Path to workspace
            bytes_to_reserve: Bytes to reserve

        Returns:
            True if space available, False otherwise
        """
        return await self.check_quota(session_id, workspace_path, bytes_to_reserve)

    def _calculate_size(self, path: Path) -> int:
        """
        Calculate total size of directory in bytes.

        Args:
            path: Path to calculate

        Returns:
            Total size in bytes
        """
        total = 0

        try:
            for item in path.rglob("*"):
                if item.is_file() and not item.is_symlink():
                    try:
                        total += item.stat().st_size
                    except (OSError, PermissionError):
                        # File inaccessible, skip
                        logger.debug(f"Skipping inaccessible file: {item}")
                        pass
        except Exception as e:
            logger.warning(f"Error calculating size for {path}: {e}")

        return total

    def clear_cache(self) -> None:
        """Clear the usage cache."""
        self._cache = None
        logger.debug("Cleared usage cache")
