"""
Path validation for sandbox enforcement.

Validates that file paths stay within workspace boundaries.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PathValidationError(Exception):
    """Raised when path validation fails."""

    def __init__(self, message: str, requested_path: str = "", resolved_path: str = ""):
        """
        Initialize path validation error.

        Args:
            message: Error message
            requested_path: The original requested path
            resolved_path: The resolved (invalid) path
        """
        self.requested_path = requested_path
        self.resolved_path = resolved_path
        super().__init__(message)

    def __str__(self) -> str:
        """Format error with details."""
        if self.resolved_path:
            return f"{super().__str__()}: {self.requested_path} -> {self.resolved_path}"
        return super().__str__()


class PathValidator:
    """
    Validates that paths stay within workspace boundaries.

    Prevents:
    - Path traversal attacks (../../etc/passwd)
    - Absolute paths (/etc/passwd)
    - Symlink escapes

    Usage:
        validator = PathValidator(
            workspace_path=Path("/workspaces/session_123"),
            mode="strict",
        )

        # Validate a path
        try:
            validated = validator.validate("config.txt")
            # Returns: /workspaces/session_123/config.txt
        except PathValidationError:
            # Path escapes workspace
            pass
    """

    # Paths that are known to be safe (relative, no traversal)
    SAFE_PATTERN = {
        # Alphanumeric names, extensions, no special chars
        # Allows: a.txt, file.json, subdir/data.csv
        # Blocks: ../, /, ./, etc.
    }

    def __init__(
        self,
        workspace_path: Path,
        mode: str = "strict",
    ):
        """
        Initialize path validator.

        Args:
            workspace_path: The workspace boundary (must exist)
            mode: Validation mode
                - "strict": Full validation (block absolute, traversal, symlinks)
                - "permissive": Only block obvious escapes
                - "disabled": No validation (for testing)
        """
        self.workspace = workspace_path.resolve()
        self.mode = mode

        if not self.workspace.exists():
            raise ValueError(f"Workspace path does not exist: {self.workspace}")

        logger.info(
            f"PathValidator initialized: workspace={self.workspace}, mode={mode}"
        )

    def validate(self, requested_path: str) -> Path:
        """
        Validate and resolve a path.

        Args:
            requested_path: Path to validate (relative or absolute)

        Returns:
            Resolved absolute path within workspace

        Raises:
            PathValidationError: If path escapes workspace
        """
        logger.info(f"🔒 [PathValidator] Validating path: '{requested_path}' (mode={self.mode})")

        if self.mode == "disabled":
            # No validation, just resolve
            resolved = Path(requested_path).resolve()
            logger.warning(f"⚠️  [PathValidator] Validation DISABLED, resolved to: {resolved}")
            return resolved

        # Block absolute paths
        if os.path.isabs(requested_path):
            logger.error(f"❌ [PathValidator] BLOCKED absolute path: '{requested_path}'")
            raise PathValidationError(
                "Absolute paths are not allowed in sandbox",
                requested_path=requested_path,
            )

        # Join with workspace and resolve
        try:
            full_path = (self.workspace / requested_path).resolve()
            logger.debug(f"   Resolved to: {full_path}")
        except Exception as e:
            logger.error(f"❌ [PathValidator] Failed to resolve path: {e}")
            raise PathValidationError(
                f"Failed to resolve path: {e}",
                requested_path=requested_path,
            )

        # Verify still within workspace (path traversal check)
        try:
            relative = full_path.relative_to(self.workspace)
            logger.info(f"✅ [PathValidator] Path validated: '{requested_path}' -> '{relative}' (within {self.workspace})")
        except ValueError:
            # Path escapes workspace via ../
            logger.error(f"❌ [PathValidator] BLOCKED path traversal: '{requested_path}' -> '{full_path}' (escapes {self.workspace})")
            raise PathValidationError(
                "Path escapes workspace (path traversal detected)",
                requested_path=requested_path,
                resolved_path=str(full_path),
            )

        # Check for symlink escapes
        if full_path.exists() and full_path.is_symlink():
            real_path = full_path.resolve()
            logger.debug(f"   Checking symlink: {full_path} -> {real_path}")
            try:
                real_path.relative_to(self.workspace)
                logger.info(f"   Symlink is safe (points within workspace)")
            except ValueError:
                # Symlink points outside workspace
                logger.error(f"❌ [PathValidator] BLOCKED symlink escape: '{requested_path}' -> symlink -> '{real_path}' (escapes {self.workspace})")
                raise PathValidationError(
                    "Symlink escapes workspace",
                    requested_path=requested_path,
                    resolved_path=str(real_path),
                )

        return full_path

    def is_safe(self, path: str) -> bool:
        """
        Check if a path is safe without raising exception.

        Args:
            path: Path to check

        Returns:
            True if safe, False otherwise
        """
        try:
            self.validate(path)
            return True
        except PathValidationError:
            return False

    def make_relative_to_workspace(self, absolute_path: Path) -> str:
        """
        Convert an absolute workspace path to relative.

        Args:
            absolute_path: Absolute path within workspace

        Returns:
            Relative path from workspace root

        Raises:
            PathValidationError: If path is not within workspace
        """
        try:
            return str(absolute_path.relative_to(self.workspace))
        except ValueError:
            raise PathValidationError(
                "Path is not within workspace",
                requested_path=str(absolute_path),
            )

    def get_workspace_path(self) -> Path:
        """Get the workspace boundary path."""
        return self.workspace
