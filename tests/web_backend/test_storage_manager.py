"""
Tests for StorageManager.
"""

import pytest
import tempfile
from pathlib import Path

from src.web_backend.services.storage_manager import (
    StorageManager,
    StorageLimits,
    StorageLimitError,
)
from src.web_backend.services.workspace_manager import WorkspaceManager


class TestStorageLimits:
    """Tests for StorageLimits dataclass."""

    def test_default_limits(self):
        """Test default storage limits."""
        limits = StorageLimits()
        assert limits.max_workspace_size_mb == 500
        assert limits.max_file_size_mb == 50
        assert limits.max_total_user_storage_gb == 5
        assert limits.max_sessions_per_user == 20
        assert limits.retention_days == 30

    def test_custom_limits(self):
        """Test custom storage limits."""
        limits = StorageLimits(
            max_workspace_size_mb=100,
            max_file_size_mb=10,
            max_total_user_storage_gb=1,
            max_sessions_per_user=5,
            retention_days=7,
        )
        assert limits.max_workspace_size_mb == 100
        assert limits.max_file_size_mb == 10


class TestStorageManager:
    """Tests for StorageManager class."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def workspace_manager(self, temp_base):
        """Create a WorkspaceManager."""
        return WorkspaceManager(base_path=temp_base)

    @pytest.fixture
    def storage_manager(self, workspace_manager):
        """Create a StorageManager with small limits for testing."""
        limits = StorageLimits(
            max_workspace_size_mb=1,  # 1 MB
            max_file_size_mb=0.5,     # 512 KB
            max_total_user_storage_gb=0.01,  # 10 MB
            max_sessions_per_user=3,
        )
        return StorageManager(
            workspace_manager=workspace_manager,
            limits=limits,
        )

    def test_check_file_size_within_limit(self, storage_manager):
        """Test file size check within limits."""
        # 100 KB file should be fine
        assert storage_manager.check_file_size(100 * 1024)

    def test_check_file_size_exceeds_limit(self, storage_manager):
        """Test file size check exceeds limit."""
        # 1 MB file should fail (limit is 512 KB)
        with pytest.raises(StorageLimitError) as exc_info:
            storage_manager.check_file_size(1024 * 1024)

        assert "exceeds limit" in str(exc_info.value)

    def test_check_file_upload_success(self, storage_manager, workspace_manager):
        """Test successful file upload check."""
        workspace_manager.create_workspace("user1", "session1")

        # Small file should be allowed
        assert storage_manager.check_file_upload("user1", "session1", 1024)

    def test_check_file_upload_exceeds_workspace_limit(
        self, storage_manager, workspace_manager
    ):
        """Test file upload exceeds workspace limit."""
        workspace = workspace_manager.create_workspace("user1", "session1")

        # Create a file that fills most of the workspace
        large_file = workspace / "large.bin"
        large_file.write_bytes(b"x" * (900 * 1024))  # 900 KB

        # Now trying to upload another 200 KB should fail (would exceed 1 MB limit)
        with pytest.raises(StorageLimitError) as exc_info:
            storage_manager.check_file_upload("user1", "session1", 200 * 1024)

        assert "Workspace would exceed" in str(exc_info.value)

    def test_check_session_limit(self, storage_manager, workspace_manager):
        """Test session count limit check."""
        # First 2 sessions should be fine (limit is 3)
        for i in range(2):
            workspace_manager.create_workspace("user1", f"session{i}")
            assert storage_manager.check_session_limit("user1")

    def test_check_session_limit_exceeded(self, storage_manager, workspace_manager):
        """Test session count limit exceeded."""
        # Create max sessions
        for i in range(3):
            workspace_manager.create_workspace("user1", f"session{i}")

        # Next one should fail
        with pytest.raises(StorageLimitError) as exc_info:
            storage_manager.check_session_limit("user1")

        assert "Maximum sessions" in str(exc_info.value)

    def test_get_user_total_storage(self, storage_manager, workspace_manager):
        """Test total user storage calculation."""
        # Initially zero
        assert storage_manager.get_user_total_storage("user1") == 0

        # Create workspace with files
        workspace = workspace_manager.create_workspace("user1", "session1")
        (workspace / "file1.txt").write_text("Hello World")
        (workspace / "file2.txt").write_text("Another file")

        total = storage_manager.get_user_total_storage("user1")
        assert total > 0

    def test_get_user_session_count(self, storage_manager, workspace_manager):
        """Test user session count."""
        assert storage_manager.get_user_session_count("user1") == 0

        workspace_manager.create_workspace("user1", "session1")
        assert storage_manager.get_user_session_count("user1") == 1

        workspace_manager.create_workspace("user1", "session2")
        assert storage_manager.get_user_session_count("user1") == 2

    def test_get_workspace_usage(self, storage_manager, workspace_manager):
        """Test workspace usage info."""
        workspace = workspace_manager.create_workspace("user1", "session1")
        (workspace / "test.txt").write_bytes(b"x" * 10240)  # 10 KB

        usage = storage_manager.get_workspace_usage("user1", "session1")

        assert usage["used_bytes"] == 10240
        assert usage["used_mb"] == pytest.approx(0.01, rel=0.1)  # ~0.01 MB with 10% tolerance
        assert usage["max_mb"] == 1  # Our test limit
        assert usage["percent_used"] == pytest.approx(1.0, rel=0.1)  # ~1%
        assert usage["remaining_bytes"] > 0

    def test_get_user_usage(self, storage_manager, workspace_manager):
        """Test user usage info."""
        workspace_manager.create_workspace("user1", "session1")
        workspace_manager.create_workspace("user1", "session2")

        usage = storage_manager.get_user_usage("user1")

        assert "used_bytes" in usage
        assert "used_gb" in usage
        assert "max_gb" in usage
        assert "percent_used" in usage
        assert usage["session_count"] == 2
        assert usage["max_sessions"] == 3

    def test_check_file_upload_exceeds_user_limit(
        self, workspace_manager
    ):
        """Test file upload exceeds user total storage limit."""
        # Create a storage manager with larger file limit but small user limit
        limits = StorageLimits(
            max_workspace_size_mb=100,  # Large workspace limit
            max_file_size_mb=50,        # Large file limit
            max_total_user_storage_gb=0.01,  # 10 MB user limit
            max_sessions_per_user=10,
        )
        storage_manager = StorageManager(
            workspace_manager=workspace_manager,
            limits=limits,
        )

        workspace = workspace_manager.create_workspace("user1", "session1")

        # Fill up user storage (our test limit is 10 MB total)
        large_file = workspace / "large.bin"
        large_file.write_bytes(b"x" * (9 * 1024 * 1024))  # 9 MB

        # Trying to upload another 2 MB should fail due to user limit
        with pytest.raises(StorageLimitError) as exc_info:
            storage_manager.check_file_upload("user1", "session1", 2 * 1024 * 1024)

        assert "User storage would exceed" in str(exc_info.value)
