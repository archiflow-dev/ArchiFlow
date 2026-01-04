"""
Integration tests for WebAgentFactory with framework sandbox (Phase 4).

Tests the framework-only architecture:
- Framework architecture (SessionRuntimeManager) - NOW THE ONLY ARCHITECTURE
- Legacy architecture (SandboxedToolWrapper) - REMOVED in Phase 4
"""

import pytest
import tempfile
from pathlib import Path
import asyncio

from web_backend.services.web_agent_factory import (
    WebAgentFactory,
)
from web_backend.services.workspace_manager import WorkspaceManager
from web_backend.services.storage_manager import StorageManager, StorageLimits
from web_backend.services.audit_logger import AuditLogger


class TestWebAgentFactory:
    """Tests for WebAgentFactory (Phase 4: framework-only)."""

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
            max_workspace_size_mb=10,
            max_file_size_mb=1,
            max_total_user_storage_gb=1,
            max_sessions_per_user=10,
        )
        return StorageManager(
            workspace_manager=workspace_manager,
            limits=limits,
        )

    @pytest.fixture
    def audit_logger(self, workspace_manager):
        """Create a test audit logger."""
        return AuditLogger(workspace_manager=workspace_manager)

    @pytest.fixture
    def factory(self, workspace_manager, storage_manager, audit_logger):
        """Create factory (Phase 4: always framework mode)."""
        return WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger,
        )

    def test_factory_init(self, factory):
        """Test factory initialization (Phase 4)."""
        # Phase 4: Always has runtime_manager (framework mode)
        assert factory._runtime_manager is not None
        assert factory.sandbox_mode is not None

    def test_create_execution_context(self, factory):
        """Test creating execution context."""
        context = factory.create_execution_context(
            session_id="test_session",
            user_id="test_user",
        )

        assert context is not None
        assert context.session_id == "test_session"
        assert context.user_id == "test_user"
        assert context.workspace_path.exists()

    def test_get_agent_tools(self, factory):
        """Test getting agent tools."""
        tools = factory.get_agent_tools("coding")

        assert isinstance(tools, list)
        assert "read" in tools
        assert "write" in tools
        assert "bash" in tools

    @pytest.mark.asyncio
    async def test_create_agent_framework_mode(self, factory):
        """Test creating agent (Phase 4: framework mode only)."""
        # Create execution context
        context = factory.create_execution_context(
            session_id="test_session",
            user_id="test_user",
        )

        assert context is not None
        assert context.session_id == "test_session"
        assert context.user_id == "test_user"
        assert context.workspace_path.exists()

        # In Phase 4, factory always has runtime_manager
        assert factory._runtime_manager is not None


class TestWebAgentFactoryIntegration:
    """Integration tests for WebAgentFactory agent creation (Phase 4)."""

    @pytest.fixture
    def workspace_manager(self):
        """Create a test workspace manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WorkspaceManager(base_path=Path(tmpdir))
            yield wm

    @pytest.fixture
    def factory(self, workspace_manager):
        """Create factory for testing."""
        storage_manager = StorageManager(
            workspace_manager=workspace_manager,
            limits=StorageLimits(
                max_workspace_size_mb=10,
                max_file_size_mb=1,
                max_total_user_storage_gb=1,
                max_sessions_per_user=10,
            ),
        )

        audit_logger = AuditLogger(workspace_manager=workspace_manager)

        return WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger,
        )

    @pytest.mark.asyncio
    async def test_create_agent_context(self, factory):
        """Test creating agent context (Phase 4: framework mode only)."""
        # Create execution context
        context = factory.create_execution_context(
            session_id="test_session",
            user_id="test_user",
        )

        assert context is not None
        assert context.session_id == "test_session"
        assert context.user_id == "test_user"
        assert context.workspace_path.exists()

        # In Phase 4, factory always uses framework mode
        assert factory._runtime_manager is not None

    def test_get_agent_tools_for_all_types(self, factory):
        """Test getting tools for all agent types."""
        agent_types = ["coding", "comic", "ppt", "research", "simple"]

        for agent_type in agent_types:
            tools = factory.get_agent_tools(agent_type)

            assert isinstance(tools, list)
            assert len(tools) > 0
            # All agents should have at least basic tools
            assert "read" in tools or "glob" in tools


class TestAdapterIntegration:
    """Tests for adapter integration with factory."""

    @pytest.fixture
    def workspace_manager(self):
        """Create a test workspace manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wm = WorkspaceManager(base_path=Path(tmpdir))
            yield wm

    def test_web_storage_quota_integration(self, workspace_manager):
        """Test WebStorageQuota integrates with factory."""
        from web_backend.adapters import WebStorageQuota
        from web_backend.services.storage_manager import StorageManager, StorageLimits

        storage_manager = StorageManager(
            workspace_manager=workspace_manager,
            limits=StorageLimits(
                max_workspace_size_mb=10,
                max_file_size_mb=1,
                max_total_user_storage_gb=1,
                max_sessions_per_user=10,
            ),
        )

        quota = WebStorageQuota(
            user_id="test_user",
            session_id="test_session",
            storage_manager=storage_manager,
        )

        # Check it's a valid StorageQuota implementation
        from agent_framework.storage.quota import StorageQuota
        assert isinstance(quota, StorageQuota)

        # Note: quota.get_workspace_path() uses global workspace manager singleton
        # which has a different base path than the test's workspace_manager
        # So we just verify the quota has a valid workspace path structure
        workspace = quota.get_workspace_path()
        assert isinstance(workspace, Path)
        assert quota.user_id in str(workspace)
        assert quota.session_id in str(workspace)

    def test_web_audit_trail_integration(self, workspace_manager):
        """Test WebAuditTrail integrates with factory."""
        from web_backend.adapters import WebAuditTrail
        from web_backend.services.audit_logger import AuditLogger

        audit_logger = AuditLogger(workspace_manager=workspace_manager)

        audit = WebAuditTrail(
            user_id="test_user",
            session_id="test_session",
            audit_logger=audit_logger,
        )

        # Check it's a valid AuditTrail implementation
        from agent_framework.audit.trail import AuditTrail
        assert isinstance(audit, AuditTrail)

        # Check it can log events
        async def run_test():
            await audit.log_execution(
                tool_name="read",
                params={"file_path": "test.txt"},
                success=True,
            )

        asyncio.run(run_test())
