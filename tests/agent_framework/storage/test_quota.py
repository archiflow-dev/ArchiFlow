"""
Tests for storage quota components.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from agent_framework.storage.quota import StorageQuota, QuotaExceededError
from agent_framework.storage.memory import InMemoryQuota
from agent_framework.storage.filesystem import FileSystemQuota


class TestInMemoryQuota:
    """Tests for InMemoryQuota implementation."""

    def test_initialization(self):
        """Test quota initialization."""
        quota = InMemoryQuota(limit_bytes=1024)
        assert quota.get_limit() == 1024

    def test_initialization_with_default_limit(self):
        """Test quota initialization with default 1GB limit."""
        quota = InMemoryQuota()
        assert quota.get_limit() == 1024 * 1024 * 1024

    def test_initialization_with_invalid_limit(self):
        """Test that invalid limit raises error."""
        with pytest.raises(ValueError):
            InMemoryQuota(limit_bytes=0)
        with pytest.raises(ValueError):
            InMemoryQuota(limit_bytes=-100)

    @pytest.mark.asyncio
    async def test_check_quota_within_limit(self):
        """Test checking quota when within limit."""
        quota = InMemoryQuota(limit_bytes=1000)

        result = await quota.check_quota(
            session_id="session_1",
            workspace_path=Path("/workspace"),
            additional_bytes=500,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_quota_exceeds_limit(self):
        """Test checking quota when would exceed limit."""
        quota = InMemoryQuota(limit_bytes=1000)

        result = await quota.check_quota(
            session_id="session_1",
            workspace_path=Path("/workspace"),
            additional_bytes=1500,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_quota_with_negative_bytes(self):
        """Test that negative bytes raises error."""
        quota = InMemoryQuota(limit_bytes=1000)

        with pytest.raises(ValueError):
            await quota.check_quota(
                session_id="session_1",
                workspace_path=Path("/workspace"),
                additional_bytes=-100,
            )

    def test_get_usage_initially_zero(self):
        """Test that usage is initially zero."""
        quota = InMemoryQuota(limit_bytes=1000)

        usage = quota.get_usage(Path("/workspace"))

        assert usage == 0

    def test_set_and_get_usage(self):
        """Test setting and getting usage."""
        quota = InMemoryQuota(limit_bytes=1000)

        workspace = Path("/workspace/test")
        quota.set_usage(workspace, 500)

        usage = quota.get_usage(workspace)

        assert usage == 500

    def test_set_usage_with_negative_value(self):
        """Test that setting negative usage raises error."""
        quota = InMemoryQuota(limit_bytes=1000)

        with pytest.raises(ValueError):
            quota.set_usage(Path("/workspace"), -100)

    @pytest.mark.asyncio
    async def test_reserve_space_within_limit(self):
        """Test reserving space when within limit."""
        quota = InMemoryQuota(limit_bytes=1000)

        result = await quota.reserve_space(
            session_id="session_1",
            workspace_path=Path("/workspace"),
            bytes_to_reserve=500,
        )

        assert result is True

        # Verify usage was updated
        usage = quota.get_usage(Path("/workspace"))
        assert usage == 500

    @pytest.mark.asyncio
    async def test_reserve_space_exceeds_limit(self):
        """Test that reserving beyond limit fails."""
        quota = InMemoryQuota(limit_bytes=1000)

        # Reserve some space first
        await quota.reserve_space(
            session_id="session_1",
            workspace_path=Path("/workspace"),
            bytes_to_reserve=800,
        )

        # Try to reserve more
        result = await quota.reserve_space(
            session_id="session_1",
            workspace_path=Path("/workspace"),
            bytes_to_reserve=500,
        )

        assert result is False

        # Usage should still be 800
        usage = quota.get_usage(Path("/workspace"))
        assert usage == 800

    @pytest.mark.asyncio
    async def test_reserve_space_with_negative_bytes(self):
        """Test that reserving negative bytes raises error."""
        quota = InMemoryQuota(limit_bytes=1000)

        with pytest.raises(ValueError):
            await quota.reserve_space(
                session_id="session_1",
                workspace_path=Path("/workspace"),
                bytes_to_reserve=-100,
            )

    def test_multiple_workspaces(self):
        """Test tracking multiple workspaces independently."""
        quota = InMemoryQuota(limit_bytes=1000)

        ws1 = Path("/workspace/session_1")
        ws2 = Path("/workspace/session_2")

        quota.set_usage(ws1, 300)
        quota.set_usage(ws2, 500)

        assert quota.get_usage(ws1) == 300
        assert quota.get_usage(ws2) == 500

    def test_get_all_usage(self):
        """Test getting usage for all workspaces."""
        quota = InMemoryQuota(limit_bytes=1000)

        ws1 = Path("/workspace/session_1")
        ws2 = Path("/workspace/session_2")

        quota.set_usage(ws1, 300)
        quota.set_usage(ws2, 500)

        all_usage = quota.get_all_usage()

        assert len(all_usage) == 2
        # Usage is stored with resolved paths
        assert str(ws1.resolve()) in all_usage
        assert str(ws2.resolve()) in all_usage
        assert all_usage[str(ws1.resolve())] == 300
        assert all_usage[str(ws2.resolve())] == 500

    def test_reset(self):
        """Test resetting all usage tracking."""
        quota = InMemoryQuota(limit_bytes=1000)

        ws1 = Path("/workspace/session_1")
        quota.set_usage(ws1, 300)

        quota.reset()

        assert quota.get_usage(ws1) == 0
        assert quota.get_all_usage() == {}


class TestFileSystemQuota:
    """Tests for FileSystemQuota implementation."""

    def test_initialization(self):
        """Test quota initialization."""
        quota = FileSystemQuota(limit_bytes=1024)
        assert quota.get_limit() == 1024

    def test_get_usage_nonexistent_directory(self):
        """Test that nonexistent directory returns 0 usage."""
        quota = FileSystemQuota(limit_bytes=1024)

        usage = quota.get_usage(Path("/nonexistent/path"))

        assert usage == 0

    def test_get_usage_of_directory(self):
        """Test calculating actual directory usage."""
        quota = FileSystemQuota(limit_bytes=1024 * 1024 * 1024)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")  # 13 bytes

            # Subdirectory
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            (subdir / "file2.txt").write_text("x" * 100)  # 100 bytes

            usage = quota.get_usage(Path(tmpdir))

            # Should be at least 113 bytes (files + directory overhead)
            assert usage >= 113

    @pytest.mark.asyncio
    async def test_check_quota(self):
        """Test quota checking with actual files."""
        quota = FileSystemQuota(limit_bytes=1024 * 1024)  # 1MB

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a small file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("x" * 100)

            # Check if we can add more
            result = await quota.check_quota(
                session_id="session_1",
                workspace_path=Path(tmpdir),
                additional_bytes=1024 * 1024,  # 1MB
            )

            # We have ~100 bytes, so adding 1MB should exceed
            assert result is False

    def test_clear_cache(self):
        """Test clearing the usage cache."""
        quota = FileSystemQuota(limit_bytes=1024, cache_ttl_seconds=1.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello")

            # First call calculates and caches
            usage1 = quota.get_usage(Path(tmpdir))

            # Delete file
            test_file.unlink()

            # Second call uses cache (still shows old usage)
            usage2 = quota.get_usage(Path(tmpdir))
            assert usage2 == usage1

            # Clear cache
            quota.clear_cache()

            # Now should show updated (lower) usage
            usage3 = quota.get_usage(Path(tmpdir))
            assert usage3 < usage2


class TestStorageQuotaInterface:
    """Tests that verify the StorageQuota interface contract."""

    @pytest.mark.asyncio
    async def test_quota_exceeded_error(self):
        """Test QuotaExceededError contains all information."""
        error = QuotaExceededError(
            message="Quota exceeded",
            current_usage=1000,
            requested_bytes=500,
            limit=1200,
        )

        assert error.current_usage == 1000
        assert error.requested_bytes == 500
        assert error.limit == 1200

        # Test string formatting
        error_str = str(error)
        assert "1000" in error_str or "0.00" in error_str  # Either bytes or MB
        assert "500" in error_str or "0.00" in error_str
        assert "1200" in error_str or "0.00" in error_str
