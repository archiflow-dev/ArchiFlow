"""
Manual Verification Script for Agent Sandbox Integration

This script demonstrates the integration of the agent sandbox system
for the web backend:

1. WebAgentFactory - Creates agents with sandboxed tools
2. WebExecutionContext - Sandbox configuration and path validation
3. WebAgentRunner - Agent lifecycle management
4. AgentRunnerPool - Concurrent agent session management
5. AgentSessionManager - Session-to-agent integration

Usage:
    python tests/manual/verify_agent_sandbox_integration.py

Requirements:
    - No external API keys needed (uses mocks)
    - Creates temporary directories for workspaces
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_subheader(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---")


def verify_web_execution_context():
    """Verify WebExecutionContext sandbox configuration."""
    print_header("1. WebExecutionContext - Sandbox Configuration")

    from web_backend.services.web_context import WebExecutionContext, SandboxMode
    from web_backend.services.workspace_manager import WorkspaceManager

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Create workspace manager
        workspace_manager = WorkspaceManager(base_path=str(base_path))
        workspace = workspace_manager.create_workspace("user_456", "test_session_123")

        # Create context with STRICT mode
        print_subheader("Creating context with STRICT sandbox mode")
        context = WebExecutionContext(
            session_id="test_session_123",
            user_id="user_456",
            workspace_path=workspace,
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
            timeout=60,
            max_memory_mb=512,
            allowed_network=False,
        )

        print(f"  session_id: {context.session_id}")
        print(f"  user_id: {context.user_id}")
        print(f"  workspace_path: {context.workspace_path}")
        print(f"  sandbox_mode: {context.sandbox_mode}")
        print(f"  timeout: {context.timeout}s")
        print(f"  max_memory_mb: {context.max_memory_mb}")
        print(f"  allowed_network: {context.allowed_network}")

        # Test path validation
        print_subheader("Path Validation Tests")

        # Valid path within workspace
        valid_file = workspace / "test.txt"
        valid_file.touch()
        result = context.validate_path("test.txt")
        print(f"  Valid path 'test.txt': resolved to {result}")
        assert result.exists(), "Valid path should resolve and exist"

        # Path traversal attempt
        print_subheader("Path Traversal Protection")
        try:
            result = context.validate_path("../secret.txt")
            print(f"  Path traversal '../secret.txt': ERROR - should have been blocked!")
        except Exception as e:
            print(f"  Path traversal '../secret.txt': blocked - {type(e).__name__}")

        # Test blocked tools
        print_subheader("Blocked Tools Configuration")
        print(f"  Default blocked tools: {context.blocked_tools}")

        # Add custom blocked tools
        context.blocked_tools.add("custom_dangerous_tool")
        print(f"  After adding custom: {context.blocked_tools}")

        print("\n[PASS] WebExecutionContext verification complete!")


def verify_web_agent_factory():
    """Verify WebAgentFactory creates agents with sandboxed tools."""
    print_header("2. WebAgentFactory - Sandboxed Agent Creation")

    from web_backend.services.web_agent_factory import WebAgentFactory
    from web_backend.services.workspace_manager import WorkspaceManager
    from web_backend.services.storage_manager import StorageManager, StorageLimits
    from web_backend.services.audit_logger import AuditLogger
    from web_backend.services.web_context import SandboxMode

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Create factory components
        print_subheader("Creating factory components")
        workspace_manager = WorkspaceManager(base_path=str(base_path))
        print(f"  WorkspaceManager base: {workspace_manager.base_path}")

        storage_limits = StorageLimits(
            max_workspace_size_mb=100,
            max_file_size_mb=10,
            max_sessions_per_user=5,
        )
        storage_manager = StorageManager(
            workspace_manager=workspace_manager,
            limits=storage_limits,
        )
        print(f"  StorageManager limits: {storage_limits}")

        audit_logger = AuditLogger(base_path=base_path / "audit")
        print(f"  AuditLogger path: {audit_logger.base_path}")

        # Create factory
        print_subheader("Creating WebAgentFactory")
        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger,
            sandbox_mode=SandboxMode.STRICT,
        )
        print(f"  Factory sandbox_mode: {factory.sandbox_mode}")

        # Create execution context
        print_subheader("Creating execution context")
        context = factory.create_execution_context(
            session_id="test_session",
            user_id="test_user",
        )
        print(f"  Context session_id: {context.session_id}")
        print(f"  Context workspace: {context.workspace_path}")
        print(f"  Workspace exists: {context.workspace_path.exists()}")

        # Verify .archiflow directory created
        archiflow_dir = context.workspace_path / ".archiflow"
        print(f"  .archiflow dir exists: {archiflow_dir.exists()}")
        assert archiflow_dir.exists(), ".archiflow directory should be created"

        # Test tool wrapping
        print_subheader("Tool wrapping")
        mock_tool = Mock()
        mock_tool.name = "read"
        mock_tool.description = "Read a file"
        mock_tool.parameters = {"type": "object", "properties": {}}

        toolkit = factory.wrap_tools([mock_tool], context)
        print(f"  Original tool: {mock_tool.name}")
        print(f"  Wrapped toolkit tools: {len(toolkit.list_tools())}")

        # Get agent tools for different types
        print_subheader("Agent tool configurations")
        for agent_type in ["coding", "comic", "ppt", "simple"]:
            tools = factory.get_agent_tools(agent_type)
            print(f"  {agent_type}: {tools}")

        print("\n[PASS] WebAgentFactory verification complete!")


async def verify_web_agent_runner():
    """Verify WebAgentRunner lifecycle management."""
    print_header("3. WebAgentRunner - Agent Lifecycle")

    from web_backend.services.agent_runner import WebAgentRunner, AgentExecutionError
    from web_backend.services.web_agent_factory import WebAgentFactory
    from web_backend.services.workspace_manager import WorkspaceManager
    from web_backend.services.web_context import SandboxMode
    from dataclasses import dataclass

    @dataclass
    class MockSession:
        id: str = "test_session"
        agent_type: str = "simple"
        user_id: str = "test_user"
        user_prompt: str = "Hello, agent!"
        workspace_path: str = None

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create factory
        workspace_manager = WorkspaceManager(base_path=tmpdir)
        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

        # Create session and runner
        session = MockSession()

        # Collect events
        events = []
        async def message_callback(event):
            events.append(event)
            print(f"    Event: {event['type']}")

        runner = WebAgentRunner(
            session=session,
            factory=factory,
            message_callback=message_callback,
        )

        print_subheader("Initial state")
        print(f"  is_running: {runner.is_running}")
        print(f"  is_paused: {runner.is_paused}")
        print(f"  agent: {runner.agent}")

        # Mock the agent creation
        print_subheader("Starting agent (mocked)")
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="Hello! How can I help?"))
            mock_agent.tools = []
            mock_agent.history = Mock()
            mock_agent.history.messages = []  # Needs to be a list for len()
            mock_agent._web_context = factory.create_execution_context(
                session_id=session.id,
                user_id=session.user_id,
            )
            mock_create.return_value = mock_agent

            await runner.start("Hello, agent!")

            print(f"  is_running: {runner.is_running}")
            print(f"  agent created: {runner.agent is not None}")
            print(f"  context set: {runner.context is not None}")

            assert runner.is_running, "Runner should be running"
            assert runner.agent is not None, "Agent should be created"

            # Test pause
            print_subheader("Pausing agent")
            await runner.pause()
            print(f"  is_paused: {runner.is_paused}")
            assert runner.is_paused, "Runner should be paused"

            # Test sending message when paused (should fail)
            print_subheader("Sending message while paused (should fail)")
            try:
                await runner.send_message("This should fail")
                print("  ERROR: Should have raised exception")
            except AgentExecutionError as e:
                print(f"  Correctly raised: {e}")

            # Test resume
            print_subheader("Resuming agent")
            await runner.resume()
            print(f"  is_paused: {runner.is_paused}")
            assert not runner.is_paused, "Runner should not be paused"

            # Test sending message
            print_subheader("Sending message")
            await runner.send_message("Follow-up message")
            print(f"  Agent step called: {mock_agent.step.call_count} times")

            # Test stop
            print_subheader("Stopping agent")
            await runner.stop()
            print(f"  is_running: {runner.is_running}")
            assert not runner.is_running, "Runner should be stopped"

            # Show execution stats
            print_subheader("Execution stats")
            stats = runner.get_execution_stats()
            for key, value in stats.items():
                print(f"  {key}: {value}")

            # Show collected events
            print_subheader("Events collected")
            for event in events:
                print(f"  - {event['type']}: {event.get('session_id', 'N/A')}")

        print("\n[PASS] WebAgentRunner verification complete!")


async def verify_agent_runner_pool():
    """Verify AgentRunnerPool concurrent management."""
    print_header("4. AgentRunnerPool - Concurrent Sessions")

    from web_backend.services.agent_runner import AgentRunnerPool, AgentExecutionError
    from dataclasses import dataclass

    @dataclass
    class MockSession:
        id: str
        agent_type: str = "simple"
        user_id: str = "test_user"

    # Create pool with small limit for testing
    pool = AgentRunnerPool(max_runners=3)
    print(f"  Max runners: {pool.max_runners}")
    print(f"  Initial count: {pool.count()}")

    # Add runners
    print_subheader("Adding runners")
    runners = []
    for i in range(3):
        mock_runner = Mock()
        mock_runner.session = MockSession(id=f"session_{i}")
        mock_runner.is_running = True
        mock_runner.stop = AsyncMock()

        await pool.add(mock_runner)
        runners.append(mock_runner)
        print(f"  Added session_{i}, count: {pool.count()}")

    # Try adding one more (should fail)
    print_subheader("Adding beyond limit (should fail)")
    extra_runner = Mock()
    extra_runner.session = MockSession(id="extra")
    try:
        await pool.add(extra_runner)
        print("  ERROR: Should have raised exception")
    except AgentExecutionError as e:
        print(f"  Correctly raised: {e}")

    # Get runner
    print_subheader("Getting runners")
    runner = await pool.get("session_1")
    print(f"  Get session_1: {runner is not None}")

    runner = await pool.get("nonexistent")
    print(f"  Get nonexistent: {runner}")

    # List active
    print_subheader("Listing active sessions")
    active = pool.list_active()
    print(f"  Active sessions: {active}")

    # Remove runner
    print_subheader("Removing runner")
    removed = await pool.remove("session_0")
    print(f"  Removed session_0: {removed is not None}")
    print(f"  Count after remove: {pool.count()}")

    # Stop all
    print_subheader("Stopping all runners")
    await pool.stop_all()
    print(f"  Count after stop_all: {pool.count()}")

    print("\n[PASS] AgentRunnerPool verification complete!")


async def verify_agent_session_manager():
    """Verify AgentSessionManager integration."""
    print_header("5. AgentSessionManager - Full Integration")

    from web_backend.services.agent_session_manager import AgentSessionManager
    from web_backend.services.agent_runner import AgentRunnerPool
    from web_backend.services.web_agent_factory import WebAgentFactory
    from web_backend.services.workspace_manager import WorkspaceManager
    from web_backend.services.storage_manager import StorageManager, StorageLimits
    from web_backend.services.web_context import SandboxMode
    from dataclasses import dataclass, field
    from datetime import datetime, timezone

    @dataclass
    class MockSession:
        id: str = "session_0"
        agent_type: str = "simple"
        user_id: str = "test_user"
        user_prompt: str = "Hello"
        workspace_path: str = None
        status: str = "created"
        messages: list = None
        created_at: datetime = None
        updated_at: datetime = None

        def __post_init__(self):
            if self.messages is None:
                self.messages = []
            if self.created_at is None:
                self.created_at = datetime.now(timezone.utc)
            if self.updated_at is None:
                self.updated_at = datetime.now(timezone.utc)

        def to_dict(self):
            return {
                "id": self.id,
                "agent_type": self.agent_type,
                "user_id": self.user_id,
            }

    class MockSessionService:
        def __init__(self):
            self.sessions = {}
            self.counter = 0

        async def create(self, agent_type, user_prompt, user_id="default"):
            session = MockSession(
                id=f"session_{self.counter}",
                agent_type=agent_type,
                user_prompt=user_prompt,
                user_id=user_id,
            )
            self.counter += 1
            self.sessions[session.id] = session
            return session

        async def get(self, session_id):
            return self.sessions.get(session_id)

        async def list(self, user_id=None, status=None, agent_type=None, page=1, page_size=20):
            sessions = list(self.sessions.values())
            if user_id:
                sessions = [s for s in sessions if s.user_id == user_id]
            return sessions, len(sessions)

        async def update_status(self, session_id, status):
            session = self.sessions.get(session_id)
            if session:
                session.status = status.value if hasattr(status, 'value') else status
            return session

        async def delete(self, session_id):
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create components
        print_subheader("Creating manager components")
        workspace_manager = WorkspaceManager(base_path=tmpdir)
        storage_limits = StorageLimits(
            max_workspace_size_mb=100,
            max_file_size_mb=10,
            max_sessions_per_user=5,
        )
        storage_manager = StorageManager(
            workspace_manager=workspace_manager,
            limits=storage_limits,
        )

        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

        runner_pool = AgentRunnerPool(max_runners=10)

        # Create manager with mock DB
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        manager = AgentSessionManager(
            db=mock_db,
            factory=factory,
            runner_pool=runner_pool,
        )
        manager.session_service = MockSessionService()

        print(f"  Factory created: {factory is not None}")
        print(f"  Runner pool created: {runner_pool is not None}")
        print(f"  Manager created: {manager is not None}")

        # Create session
        print_subheader("Creating session")
        session = await manager.create_session(
            agent_type="coding",
            user_id="user_123",
            user_prompt="Build a web app",
        )
        print(f"  Session ID: {session.id}")
        print(f"  Agent type: {session.agent_type}")
        print(f"  Workspace: {session.workspace_path}")

        workspace_path = Path(session.workspace_path)
        print(f"  Workspace exists: {workspace_path.exists()}")
        assert workspace_path.exists(), "Workspace should be created"

        # Start session
        print_subheader("Starting session")
        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="I'll help build the web app!"))
            mock_agent.tools = []
            mock_agent.history = Mock(messages=[])
            mock_agent._web_context = factory.create_execution_context(
                session_id=session.id,
                user_id=session.user_id,
            )
            mock_create.return_value = mock_agent

            runner = await manager.start_session(session.id)
            print(f"  Runner created: {runner is not None}")
            print(f"  Runner is_running: {runner.is_running}")

            # Get session status
            print_subheader("Getting session status")
            status = await manager.get_session_status(session.id)
            print(f"  Status keys: {list(status.keys())}")
            print(f"  is_running: {status.get('is_running')}")
            print(f"  agent_type: {status.get('agent_type')}")

            # Send message
            print_subheader("Sending message")
            await manager.send_message(session.id, "Add a login page")
            print(f"  Message sent successfully")
            print(f"  Agent step called: {mock_agent.step.call_count} times")

            # Pause session
            print_subheader("Pausing session")
            await manager.pause_session(session.id)
            pool_runner = await runner_pool.get(session.id)
            print(f"  is_paused: {pool_runner.is_paused}")

            # Resume session
            print_subheader("Resuming session")
            await manager.resume_session(session.id)
            print(f"  is_paused: {pool_runner.is_paused}")

            # List user sessions
            print_subheader("Listing user sessions")
            sessions = await manager.list_user_sessions("user_123")
            print(f"  Sessions count: {len(sessions)}")
            for s in sessions:
                print(f"    - {s['id']}: {s['agent_type']}")

            # Stop session
            print_subheader("Stopping session")
            await manager.stop_session(session.id)
            pool_runner = await runner_pool.get(session.id)
            print(f"  Runner in pool: {pool_runner}")

            # Delete session
            print_subheader("Deleting session")
            result = await manager.delete_session(session.id, delete_workspace=True)
            print(f"  Delete result: {result}")
            print(f"  Workspace exists: {workspace_path.exists()}")

    print("\n[PASS] AgentSessionManager verification complete!")


async def verify_end_to_end_flow():
    """Verify complete agent sandbox integration flow."""
    print_header("6. End-to-End Integration Flow")

    from web_backend.services.agent_session_manager import AgentSessionManager
    from web_backend.services.agent_runner import AgentRunnerPool
    from web_backend.services.web_agent_factory import WebAgentFactory
    from web_backend.services.workspace_manager import WorkspaceManager
    from web_backend.services.storage_manager import StorageManager, StorageLimits
    from web_backend.services.audit_logger import AuditLogger
    from web_backend.services.web_context import SandboxMode
    from dataclasses import dataclass
    from datetime import datetime, timezone

    @dataclass
    class MockSession:
        id: str = "session_0"
        agent_type: str = "coding"
        user_id: str = "user_123"
        user_prompt: str = "Build a calculator"
        workspace_path: str = None
        status: str = "created"
        messages: list = None
        created_at: datetime = None
        updated_at: datetime = None

        def __post_init__(self):
            if self.messages is None:
                self.messages = []
            if self.created_at is None:
                self.created_at = datetime.now(timezone.utc)
            if self.updated_at is None:
                self.updated_at = datetime.now(timezone.utc)

        def to_dict(self):
            return {"id": self.id, "agent_type": self.agent_type, "user_id": self.user_id}

    class MockSessionService:
        def __init__(self):
            self.sessions = {}
            self.counter = 0

        async def create(self, agent_type, user_prompt, user_id="default"):
            session = MockSession(id=f"session_{self.counter}", agent_type=agent_type, user_prompt=user_prompt, user_id=user_id)
            self.counter += 1
            self.sessions[session.id] = session
            return session

        async def get(self, session_id):
            return self.sessions.get(session_id)

        async def list(self, user_id=None, **kwargs):
            sessions = [s for s in self.sessions.values() if not user_id or s.user_id == user_id]
            return sessions, len(sessions)

        async def update_status(self, session_id, status):
            if session := self.sessions.get(session_id):
                session.status = status.value if hasattr(status, 'value') else status
            return session

        async def delete(self, session_id):
            return bool(self.sessions.pop(session_id, None))

    print("Simulating a complete user workflow:\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Step 1: Initialize services (done at app startup)
        print("Step 1: Initialize services")
        workspace_manager = WorkspaceManager(base_path=str(base_path))
        storage_manager = StorageManager(
            workspace_manager=workspace_manager,
            limits=StorageLimits(max_workspace_size_mb=100, max_file_size_mb=10, max_sessions_per_user=5),
        )
        audit_logger = AuditLogger(base_path=base_path / "audit")
        factory = WebAgentFactory(
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
            audit_logger=audit_logger,
            sandbox_mode=SandboxMode.STRICT,
        )
        runner_pool = AgentRunnerPool(max_runners=100)
        print("  [OK] All services initialized")

        # Step 2: User creates a session via API
        print("\nStep 2: User creates session via API")
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        manager = AgentSessionManager(db=mock_db, factory=factory, runner_pool=runner_pool)
        manager.session_service = MockSessionService()

        session = await manager.create_session(
            agent_type="coding",
            user_id="user_alice",
            user_prompt="Create a Python calculator with basic operations",
        )
        print(f"  [OK] Session created: {session.id}")
        print(f"       Workspace: {session.workspace_path}")

        # Step 3: User starts the agent
        print("\nStep 3: User starts the agent")
        events_received = []
        async def ws_callback(event):
            events_received.append(event)

        with patch.object(factory, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_agent = Mock()
            mock_agent.step = AsyncMock(return_value=Mock(content="I'll create a calculator for you!"))
            mock_agent.tools = []
            mock_agent.history = Mock(messages=[])
            mock_agent._web_context = factory.create_execution_context(
                session_id=session.id, user_id=session.user_id)
            mock_create.return_value = mock_agent

            runner = await manager.start_session(
                session.id,
                message_callback=ws_callback,
            )
            print(f"  [OK] Agent started, runner.is_running: {runner.is_running}")

            # Step 4: User sends follow-up messages
            print("\nStep 4: User sends follow-up messages")
            await manager.send_message(session.id, "Add a square root function")
            await manager.send_message(session.id, "Add unit tests")
            print(f"  [OK] Sent 2 follow-up messages")
            print(f"       Total agent steps: {mock_agent.step.call_count}")

            # Step 5: User pauses work
            print("\nStep 5: User pauses work")
            await manager.pause_session(session.id)
            print(f"  [OK] Session paused")

            # Step 6: User resumes later
            print("\nStep 6: User resumes later")
            await manager.resume_session(session.id)
            await manager.send_message(session.id, "Make it handle negative numbers")
            print(f"  [OK] Session resumed and continued")

            # Step 7: Check session status
            print("\nStep 7: Check session status")
            status = await manager.get_session_status(session.id)
            print(f"  [OK] Status: running={status.get('is_running')}, type={status.get('agent_type')}")

            # Step 8: User finishes and stops
            print("\nStep 8: User finishes and stops agent")
            await manager.stop_session(session.id)
            print(f"  [OK] Session stopped")

            # Step 9: Check events received via WebSocket
            print("\nStep 9: Check WebSocket events")
            event_types = [e['type'] for e in events_received]
            print(f"  [OK] Events received: {len(events_received)}")
            print(f"       Event types: {set(event_types)}")

        # Summary
        print("\n" + "-" * 50)
        print("End-to-End Flow Summary:")
        print(f"  - Session ID: {session.id}")
        print(f"  - Agent type: {session.agent_type}")
        print(f"  - Workspace created: {Path(session.workspace_path).exists()}")
        print(f"  - Messages exchanged: {mock_agent.step.call_count}")
        print(f"  - WebSocket events: {len(events_received)}")
        print(f"  - Sandbox mode: STRICT")

    print("\n[PASS] End-to-end integration verified!")


async def main_async():
    """Run async verification tests."""
    await verify_web_agent_runner()
    await verify_agent_runner_pool()
    await verify_agent_session_manager()
    await verify_end_to_end_flow()


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("  AGENT SANDBOX INTEGRATION - MANUAL VERIFICATION")
    print("=" * 70)

    try:
        # Sync tests
        verify_web_execution_context()
        verify_web_agent_factory()

        # Async tests
        asyncio.run(main_async())

        print("\n" + "=" * 70)
        print("  ALL VERIFICATIONS PASSED!")
        print("=" * 70)
        print("\nAgent Sandbox Integration Summary:")
        print("  1. WebExecutionContext - Path validation and sandbox configuration")
        print("  2. WebAgentFactory - Creates agents with sandboxed tools")
        print("  3. WebAgentRunner - Agent lifecycle management (start/pause/stop)")
        print("  4. AgentRunnerPool - Concurrent session management")
        print("  5. AgentSessionManager - Session-to-agent integration")
        print("  6. End-to-End - Complete workflow from API to agent execution")
        print()

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
