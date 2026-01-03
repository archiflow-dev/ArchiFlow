"""
Tests for WorkspaceManager.
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.web_backend.services.workspace_manager import (
    WorkspaceManager,
    WorkspaceSecurityError,
)


class TestWorkspaceManager:
    """Tests for WorkspaceManager class."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_base):
        """Create a WorkspaceManager with temp directory."""
        return WorkspaceManager(base_path=temp_base)

    def test_init_creates_base_directory(self, temp_base):
        """Test that init creates the base directory."""
        new_path = os.path.join(temp_base, "new_workspaces")
        manager = WorkspaceManager(base_path=new_path)
        assert Path(new_path).exists()

    def test_get_workspace_path(self, manager):
        """Test getting workspace path."""
        path = manager.get_workspace_path("user1", "session1")
        assert path == manager.base_path / "user1" / "session1"

    def test_create_workspace(self, manager):
        """Test workspace creation."""
        workspace = manager.create_workspace("user1", "session1")

        assert workspace.exists()
        assert (workspace / ".archiflow").exists()
        assert (workspace / "artifacts").exists()
        assert (workspace / "exports").exists()

    def test_create_workspace_idempotent(self, manager):
        """Test that creating workspace twice doesn't fail."""
        workspace1 = manager.create_workspace("user1", "session1")
        workspace2 = manager.create_workspace("user1", "session1")
        assert workspace1 == workspace2

    def test_workspace_exists(self, manager):
        """Test workspace existence check."""
        assert not manager.workspace_exists("user1", "session1")
        manager.create_workspace("user1", "session1")
        assert manager.workspace_exists("user1", "session1")

    def test_delete_workspace(self, manager):
        """Test workspace deletion."""
        manager.create_workspace("user1", "session1")
        assert manager.workspace_exists("user1", "session1")

        deleted = manager.delete_workspace("user1", "session1")
        assert deleted
        assert not manager.workspace_exists("user1", "session1")

    def test_delete_nonexistent_workspace(self, manager):
        """Test deleting a workspace that doesn't exist."""
        deleted = manager.delete_workspace("user1", "nonexistent")
        assert not deleted

    def test_validate_path_relative(self, manager):
        """Test that relative paths are validated correctly."""
        workspace = manager.create_workspace("user1", "session1")

        # Valid relative paths
        valid_path = manager.validate_path(workspace, "artifacts/test.txt")
        assert valid_path == workspace / "artifacts" / "test.txt"

        valid_path = manager.validate_path(workspace, "file.txt")
        assert valid_path == workspace / "file.txt"

    def test_validate_path_blocks_absolute_paths(self, manager):
        """Test that absolute paths are blocked."""
        workspace = manager.create_workspace("user1", "session1")

        with pytest.raises(WorkspaceSecurityError) as exc_info:
            manager.validate_path(workspace, "/etc/passwd")

        # On Windows, /etc/passwd is treated as relative and escapes workspace
        # On Unix, it's an absolute path - both should raise security error
        assert "not allowed" in str(exc_info.value) or "escapes workspace" in str(exc_info.value)

    def test_validate_path_blocks_traversal(self, manager):
        """Test that path traversal attempts are blocked."""
        workspace = manager.create_workspace("user1", "session1")

        with pytest.raises(WorkspaceSecurityError) as exc_info:
            manager.validate_path(workspace, "../other_session/file.txt")

        assert "escapes workspace" in str(exc_info.value)

    def test_validate_path_blocks_double_traversal(self, manager):
        """Test that double traversal is blocked."""
        workspace = manager.create_workspace("user1", "session1")

        with pytest.raises(WorkspaceSecurityError) as exc_info:
            manager.validate_path(workspace, "../../etc/passwd")

        assert "escapes workspace" in str(exc_info.value)

    def test_validate_path_handles_dots(self, manager):
        """Test that single dots are handled correctly."""
        workspace = manager.create_workspace("user1", "session1")

        # Single dot should resolve correctly
        valid_path = manager.validate_path(workspace, "./file.txt")
        assert valid_path == workspace / "file.txt"

    def test_get_workspace_size_empty(self, manager):
        """Test getting size of empty workspace."""
        manager.create_workspace("user1", "session1")
        size = manager.get_workspace_size("user1", "session1")
        assert size == 0  # Empty workspace

    def test_get_workspace_size_with_files(self, manager):
        """Test getting size of workspace with files."""
        workspace = manager.create_workspace("user1", "session1")

        # Create a test file
        test_file = workspace / "test.txt"
        test_content = "Hello, World!" * 100
        test_file.write_text(test_content)

        size = manager.get_workspace_size("user1", "session1")
        assert size == len(test_content.encode('utf-8'))

    def test_get_workspace_size_nonexistent(self, manager):
        """Test getting size of nonexistent workspace."""
        size = manager.get_workspace_size("user1", "nonexistent")
        assert size == 0

    def test_list_user_workspaces(self, manager):
        """Test listing user workspaces."""
        manager.create_workspace("user1", "session1")
        manager.create_workspace("user1", "session2")
        manager.create_workspace("user2", "session3")

        workspaces = manager.list_user_workspaces("user1")
        assert len(workspaces) == 2
        assert "session1" in workspaces
        assert "session2" in workspaces
        assert "session3" not in workspaces

    def test_list_user_workspaces_empty(self, manager):
        """Test listing workspaces for user with no workspaces."""
        workspaces = manager.list_user_workspaces("nonexistent_user")
        assert workspaces == []

    def test_delete_cleans_up_empty_user_dir(self, manager):
        """Test that deleting last workspace cleans up user directory."""
        manager.create_workspace("user1", "session1")
        user_dir = manager.base_path / "user1"
        assert user_dir.exists()

        manager.delete_workspace("user1", "session1")
        assert not user_dir.exists()

    def test_validate_path_with_nested_directories(self, manager):
        """Test path validation with nested directories."""
        workspace = manager.create_workspace("user1", "session1")

        valid_path = manager.validate_path(
            workspace, "artifacts/images/panel1/version2/image.png"
        )
        assert valid_path == workspace / "artifacts/images/panel1/version2/image.png"

    def test_validate_path_with_special_characters(self, manager):
        """Test path validation with special characters in filename."""
        workspace = manager.create_workspace("user1", "session1")

        # Spaces and other characters should work
        valid_path = manager.validate_path(workspace, "my file (1).txt")
        assert valid_path.name == "my file (1).txt"
