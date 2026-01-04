"""
Integration tests for web backend adapters (Phase 2).

Tests the WebStorageQuota and WebAuditTrail adapters that bridge
the web backend components to the framework interfaces.
"""

import pytest
import tempfile
from pathlib import Path
import asyncio

from web_backend.adapters import WebStorageQuota, WebAuditTrail
from web_backend.services.storage_manager import StorageManager, StorageLimits
from web_backend.services.audit_logger import AuditLogger
from web_backend.services.workspace_manager import WorkspaceManager


class TestWebStorageQuota:
    """Tests for WebStorageQuota adapter."""

    @pytest.fixture
    def workspace_manager(self):
        """Create a test workspace manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WorkspaceManager(base_path=Path(tmpdir))
            yield wm

    @pytest.fixture
    def storage_manager(self, workspace_manager):
        """Create a test storage manager."""
        limits = StorageLimits(
            max_workspace_size_mb=10,  # 10MB for testing
            max_file_size_mb=1,
            max_total_user_storage_gb=1,
            max_sessions_per_user=10,
        )
        return StorageManager(
            workspace_manager=workspace_manager,
            limits=limits,
        )

    @pytest.fixture
    def quota(self, storage_manager):
        """Create a WebStorageQuota adapter."""
        return WebStorageQuota(
            user_id="test_user",
            session_id="test_session",
            storage_manager=storage_manager,
        )

    @pytest.mark.asyncio
    async def test_check_quota_within_limit(self, quota, storage_manager):
        """Test checking quota when within limit."""
        workspace = quota.get_workspace_path()

        # Create workspace
        if not workspace.exists():
            storage_manager.workspace_manager.create_workspace(
                quota.user_id, quota.session_id
            )

        # Check if we can add 1MB (within 10MB limit)
        result = await quota.check_quota(
            session_id=quota.session_id,
            workspace_path=workspace,
            additional_bytes=1024 * 1024,  # 1MB
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_quota_exceeds_limit(self, quota, storage_manager):
        """Test checking quota when would exceed limit."""
        workspace = quota.get_workspace_path()

        # Create workspace
        if not workspace.exists():
            storage_manager.workspace_manager.create_workspace(
                quota.user_id, quota.session_id
            )

        # Check if we can add 20MB (exceeds 10MB limit)
        result = await quota.check_quota(
            session_id=quota.session_id,
            workspace_path=workspace,
            additional_bytes=20 * 1024 * 1024,  # 20MB
        )

        assert result is False

    def test_get_usage(self, quota, storage_manager):
        """Test getting current usage."""
        # Note: get_usage() uses storage_manager's workspace_manager
        # which is different from quota.get_workspace_path() (global singleton)
        # So we need to use the same workspace manager that storage_manager uses
        workspace = storage_manager.workspace_manager.get_workspace_path(
            quota.user_id, quota.session_id
        )
        storage_manager.workspace_manager.create_workspace(
            quota.user_id, quota.session_id
        )

        # Create a test file
        test_file = workspace / "test.txt"
        test_file.write_text("Hello, World!")  # 13 bytes

        # Get usage
        usage = quota.get_usage(workspace)

        # Should be at least 13 bytes (plus filesystem overhead)
        assert usage >= 13

    def test_get_limit(self, quota):
        """Test getting quota limit."""
        limit = quota.get_limit()

        # Should be 10MB in bytes
        expected = 10 * 1024 * 1024
        assert limit == expected

    def test_get_workspace_path(self, quota):
        """Test getting workspace path."""
        workspace = quota.get_workspace_path()

        # The workspace path should be a valid Path
        assert isinstance(workspace, Path)
        assert quota.user_id in str(workspace)
        assert quota.session_id in str(workspace)

        # Note: The quota uses the global workspace manager singleton,
        # which may have a different base path than the test's workspace manager

    def test_get_user_usage_info(self, quota, storage_manager):
        """Test getting user usage info."""
        info = quota.get_user_usage_info()

        assert "used_bytes" in info
        assert "used_gb" in info
        assert "max_gb" in info
        assert "session_count" in info
        assert "max_sessions" in info

        # Check max values match limits
        assert info["max_gb"] == storage_manager.limits.max_total_user_storage_gb
        assert info["max_sessions"] == storage_manager.limits.max_sessions_per_user

    def test_get_workspace_usage_info(self, quota, storage_manager):
        """Test getting workspace usage info."""
        workspace = quota.get_workspace_path()

        # Create workspace
        if not workspace.exists():
            storage_manager.workspace_manager.create_workspace(
                quota.user_id, quota.session_id
            )

        info = quota.get_workspace_usage_info()

        assert "used_bytes" in info
        assert "used_mb" in info
        assert "max_mb" in info
        assert "percent_used" in info
        assert "remaining_bytes" in info

        # Check max matches limits
        assert info["max_mb"] == storage_manager.limits.max_workspace_size_mb

    @pytest.mark.asyncio
    async def test_reserve_space_within_limit(self, quota, storage_manager):
        """Test reserving space when within limit."""
        workspace = quota.get_workspace_path()

        # Create workspace
        if not workspace.exists():
            storage_manager.workspace_manager.create_workspace(
                quota.user_id, quota.session_id
            )

        # Reserve 1MB
        result = await quota.reserve_space(
            session_id=quota.session_id,
            workspace_path=workspace,
            bytes_to_reserve=1024 * 1024,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_reserve_space_negative_bytes_raises(self, quota):
        """Test that reserving negative bytes raises error."""
        workspace = quota.get_workspace_path()

        with pytest.raises(ValueError):
            await quota.reserve_space(
                session_id=quota.session_id,
                workspace_path=workspace,
                bytes_to_reserve=-100,
            )


class TestWebAuditTrail:
    """Tests for WebAuditTrail adapter."""

    @pytest.fixture
    def workspace_manager(self):
        """Create a test workspace manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WorkspaceManager(base_path=Path(tmpdir))
            yield wm

    @pytest.fixture
    def audit(self, workspace_manager):
        """Create a WebAuditTrail adapter."""
        return WebAuditTrail(
            user_id="test_user",
            session_id="test_session",
            audit_logger=AuditLogger(workspace_manager=workspace_manager),
        )

    @pytest.mark.asyncio
    async def test_log_execution_success(self, audit):
        """Test logging successful tool execution."""
        await audit.log_execution(
            tool_name="read",
            params={"file_path": "test.txt"},
            success=True,
        )

        # Should not raise
        events = audit.get_session_events()
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_log_execution_failure(self, audit):
        """Test logging failed tool execution."""
        await audit.log_execution(
            tool_name="write",
            params={"file_path": "test.txt", "content": "x" * 100},
            success=False,
            error="Permission denied",
        )

        # Should not raise
        events = audit.get_session_events()
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_log_security_event(self, audit):
        """Test logging security event."""
        await audit.log_security_event(
            event_type="path_violation",
            severity="critical",
            message="Attempted path traversal",
            requested_path="../../../etc/passwd",
        )

        # Should not raise
        events = audit.get_session_events()
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_log_session_event(self, audit):
        """Test logging session event."""
        await audit.log_session_event(
            session_id="test_session",
            event_type="created",
            agent_type="coding",
        )

        # Should not raise
        events = audit.get_session_events()
        assert len(events) > 0

    def test_sanitize_params(self, audit):
        """Test parameter sanitization."""
        params = {
            "file_path": "test.txt",
            "api_key": "secret_key_12345",
            "password": "my_password",
            "content": "Hello",
        }

        sanitized = audit._sanitize_params(params)

        assert sanitized["file_path"] == "test.txt"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["content"] == "Hello"

    def test_sanitize_params_truncates_long_values(self, audit):
        """Test that long parameters are truncated."""
        long_content = "x" * 300

        params = {"content": long_content}
        sanitized = audit._sanitize_params(params)

        assert "[REDACTED]" not in str(sanitized["content"])
        assert "truncated" in str(sanitized["content"])

    def test_map_severity(self, audit):
        """Test severity mapping."""
        from web_backend.services.audit_logger import AuditSeverity as WebSeverity

        assert audit._map_severity("debug") == WebSeverity.DEBUG
        assert audit._map_severity("info") == WebSeverity.INFO
        assert audit._map_severity("warning") == WebSeverity.WARNING
        assert audit._map_severity("error") == WebSeverity.ERROR
        assert audit._map_severity("critical") == WebSeverity.CRITICAL

    def test_get_metrics(self, audit):
        """Test getting audit metrics."""
        metrics = audit.get_metrics()

        assert "event_counts" in metrics
        assert "total_events" in metrics

    def test_map_security_event_type(self, audit):
        """Test security event type mapping."""
        assert audit._map_security_event_type("path_violation") == "path_traversal"
        assert audit._map_security_event_type("command_violation") == "dangerous_command"
        assert audit._map_security_event_type("quota_exceeded") == "storage_limit"

    def test_map_session_event_type(self, audit):
        """Test session event type mapping."""
        assert audit._map_session_event_type("created") == "start"
        assert audit._map_session_event_type("started") == "start"
        assert audit._map_session_event_type("stopped") == "end"
        assert audit._map_session_event_type("deleted") == "end"
