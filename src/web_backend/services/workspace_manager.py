"""
Workspace Manager for ArchiFlow Web Backend.

Manages session workspaces with security sandboxing.
All file operations must go through this manager to ensure
agents cannot access files outside their workspace.
"""

from pathlib import Path
from typing import Optional
import os
import shutil
import logging

from ..config import settings

logger = logging.getLogger(__name__)


class WorkspaceSecurityError(Exception):
    """Raised when a path escape attempt is detected."""
    pass


class WorkspaceManager:
    """
    Manages session workspaces with path sandboxing.

    Each session has an isolated workspace directory where the agent
    can safely read, write, and modify files without affecting other
    sessions or the host system.

    Workspace structure:
        data/workspaces/{user_id}/{session_id}/
            ├── .archiflow/      (session metadata - hidden from agent)
            │   ├── session.json
            │   ├── workflow.json
            │   ├── messages.jsonl
            │   └── audit.jsonl
            ├── artifacts/       (agent-generated files)
            └── exports/         (final outputs: PDF, etc.)
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize WorkspaceManager.

        Args:
            base_path: Base directory for all workspaces.
                      Defaults to settings.WORKSPACE_BASE_DIR
        """
        self.base_path = Path(base_path or settings.WORKSPACE_BASE_DIR).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_workspace_path(self, user_id: str, session_id: str) -> Path:
        """
        Get the absolute path to a session workspace.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Absolute path to workspace directory
        """
        workspace = self.base_path / user_id / session_id
        return workspace.resolve()

    def validate_path(self, workspace: Path, requested_path: str) -> Path:
        """
        Validate that a requested path stays within the workspace.

        CRITICAL: This prevents path traversal attacks like:
        - ../../etc/passwd
        - /etc/passwd
        - symlink escapes

        Args:
            workspace: The session's workspace directory
            requested_path: The path requested by the agent

        Returns:
            Resolved absolute path within workspace

        Raises:
            WorkspaceSecurityError: If path escapes workspace
        """
        # Normalize the path (resolve .., ., etc.)
        if os.path.isabs(requested_path):
            # Absolute paths not allowed - must be relative to workspace
            raise WorkspaceSecurityError(
                f"Absolute paths not allowed: {requested_path}"
            )

        # Join with workspace and resolve
        full_path = (workspace / requested_path).resolve()

        # Verify the resolved path is still within workspace
        try:
            full_path.relative_to(workspace.resolve())
        except ValueError:
            # Path escapes workspace!
            raise WorkspaceSecurityError(
                f"Path escapes workspace: {requested_path} -> {full_path}"
            )

        # Additional check: no symlinks that escape
        if full_path.exists() and full_path.is_symlink():
            real_path = full_path.resolve()
            try:
                real_path.relative_to(workspace.resolve())
            except ValueError:
                raise WorkspaceSecurityError(
                    f"Symlink escapes workspace: {requested_path}"
                )

        return full_path

    def create_workspace(self, user_id: str, session_id: str) -> Path:
        """
        Create a new session workspace.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Path to created workspace
        """
        workspace = self.get_workspace_path(user_id, session_id)

        # Create directory structure
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".archiflow").mkdir(exist_ok=True)
        (workspace / "artifacts").mkdir(exist_ok=True)
        (workspace / "exports").mkdir(exist_ok=True)

        # Set restrictive permissions (owner only) on Unix
        try:
            os.chmod(workspace, 0o700)
        except OSError:
            # Windows doesn't support chmod the same way
            pass

        logger.info(f"Created workspace: {workspace}")
        return workspace

    def delete_workspace(self, user_id: str, session_id: str) -> bool:
        """
        Delete a session workspace and all its contents.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        workspace = self.get_workspace_path(user_id, session_id)

        if not workspace.exists():
            return False

        # Verify it's actually within our base path (extra safety)
        try:
            workspace.relative_to(self.base_path)
        except ValueError:
            raise WorkspaceSecurityError("Attempted to delete path outside workspaces")

        shutil.rmtree(workspace)
        logger.info(f"Deleted workspace: {workspace}")

        # Clean up empty user directory
        user_dir = self.base_path / user_id
        if user_dir.exists() and not any(user_dir.iterdir()):
            user_dir.rmdir()

        return True

    def get_workspace_size(self, user_id: str, session_id: str) -> int:
        """
        Calculate total size of workspace in bytes.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Total size in bytes
        """
        workspace = self.get_workspace_path(user_id, session_id)

        if not workspace.exists():
            return 0

        total = 0
        for path in workspace.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
        return total

    def workspace_exists(self, user_id: str, session_id: str) -> bool:
        """Check if a workspace exists."""
        workspace = self.get_workspace_path(user_id, session_id)
        return workspace.exists() and workspace.is_dir()

    def list_user_workspaces(self, user_id: str) -> list[str]:
        """
        List all session IDs for a user.

        Args:
            user_id: User ID

        Returns:
            List of session IDs
        """
        user_dir = self.base_path / user_id
        if not user_dir.exists():
            return []

        return [
            d.name for d in user_dir.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ]


# Global singleton instance
_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """Get the global WorkspaceManager instance."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager
