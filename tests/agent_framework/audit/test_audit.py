"""
Tests for audit trail components.
"""

import pytest
import asyncio
import logging
from io import StringIO
from pathlib import Path

from agent_framework.audit.trail import AuditTrail, AuditSeverity
from agent_framework.audit.null import NullAuditTrail
from agent_framework.audit.logger import LoggerAuditTrail


class TestNullAuditTrail:
    """Tests for NullAuditTrail (no-op implementation)."""

    @pytest.mark.asyncio
    async def test_log_execution_no_op(self):
        """Test that log_execution does nothing."""
        audit = NullAuditTrail()

        # Should not raise any exceptions
        await audit.log_execution(
            tool_name="read",
            params={"file_path": "test.txt"},
            success=True,
        )

    @pytest.mark.asyncio
    async def test_log_security_event_no_op(self):
        """Test that log_security_event does nothing."""
        audit = NullAuditTrail()

        await audit.log_security_event(
            event_type="violation",
            severity=AuditSeverity.WARNING,
            message="Test event",
        )

    @pytest.mark.asyncio
    async def test_log_session_event_no_op(self):
        """Test that log_session_event does nothing."""
        audit = NullAuditTrail()

        await audit.log_session_event(
            session_id="session_1",
            event_type="started",
        )


class TestLoggerAuditTrail:
    """Tests for LoggerAuditTrail implementation."""

    def test_initialization(self):
        """Test logger audit trail initialization."""
        audit = LoggerAuditTrail()
        assert audit.logger is not None
        assert audit.logger.name == "archiflow.audit"

    def test_initialization_with_custom_logger(self):
        """Test initialization with custom logger name."""
        audit = LoggerAuditTrail(logger_name="custom.audit")
        assert audit.logger.name == "custom.audit"

    @pytest.mark.asyncio
    async def test_log_execution_success(self):
        """Test logging successful tool execution."""
        # Capture log output
        logger = logging.getLogger("archiflow.audit")
        logger.setLevel(logging.INFO)

        string_stream = StringIO()
        handler = logging.StreamHandler(string_stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            audit = LoggerAuditTrail()

            await audit.log_execution(
                tool_name="read",
                params={"file_path": "test.txt"},
                success=True,
            )

            # Check log output
            log_output = string_stream.getvalue()
            assert "TOOL_EXECUTION" in log_output
            assert "SUCCESS" in log_output
            assert "tool=read" in log_output

        finally:
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_log_execution_failure(self):
        """Test logging failed tool execution."""
        logger = logging.getLogger("archiflow.audit")
        logger.setLevel(logging.INFO)

        string_stream = StringIO()
        handler = logging.StreamHandler(string_stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            audit = LoggerAuditTrail()

            await audit.log_execution(
                tool_name="read",
                params={"file_path": "test.txt"},
                success=False,
                error="File not found",
            )

            # Check log output
            log_output = string_stream.getvalue()
            assert "FAILED" in log_output
            assert "error=File not found" in log_output

        finally:
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_log_execution_with_long_params(self):
        """Test that long parameters are truncated."""
        logger = logging.getLogger("archiflow.audit")
        logger.setLevel(logging.INFO)

        string_stream = StringIO()
        handler = logging.StreamHandler(string_stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            audit = LoggerAuditTrail()

            # Create long content
            long_content = "x" * 2000

            await audit.log_execution(
                tool_name="write",
                params={"content": long_content},
                success=True,
            )

            # Check log output
            log_output = string_stream.getvalue()
            assert "truncated" in log_output
            assert "2000 chars" in log_output

        finally:
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_log_execution_with_sensitive_params(self):
        """Test that sensitive parameters are redacted."""
        logger = logging.getLogger("archiflow.audit")
        logger.setLevel(logging.INFO)

        string_stream = StringIO()
        handler = logging.StreamHandler(string_stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            audit = LoggerAuditTrail()

            await audit.log_execution(
                tool_name="api_call",
                params={
                    "endpoint": "/api/data",
                    "api_key": "secret_key_12345",
                    "password": "my_password",
                },
                success=True,
            )

            # Check log output
            log_output = string_stream.getvalue()
            assert "[REDACTED]" in log_output
            assert "secret_key_12345" not in log_output
            assert "my_password" not in log_output

        finally:
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_log_security_event(self):
        """Test logging security events."""
        logger = logging.getLogger("archiflow.audit")
        logger.setLevel(logging.INFO)

        string_stream = StringIO()
        handler = logging.StreamHandler(string_stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            audit = LoggerAuditTrail()

            await audit.log_security_event(
                event_type="path_violation",
                severity=AuditSeverity.WARNING,
                message="Attempted path traversal",
                session_id="session_1",
                requested_path="../../../etc/passwd",
            )

            # Check log output
            log_output = string_stream.getvalue()
            assert "SECURITY_EVENT" in log_output
            assert "path_violation" in log_output
            # Severity is logged in lowercase
            assert "warning" in log_output
            assert "session_1" in log_output

        finally:
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_log_security_event_critical(self):
        """Test logging critical security events."""
        logger = logging.getLogger("archiflow.audit")
        logger.setLevel(logging.CRITICAL)

        string_stream = StringIO()
        handler = logging.StreamHandler(string_stream)
        handler.setLevel(logging.CRITICAL)
        logger.addHandler(handler)

        try:
            audit = LoggerAuditTrail()

            await audit.log_security_event(
                event_type="system_breach",
                severity=AuditSeverity.CRITICAL,
                message="Critical security breach",
            )

            # Check log output
            log_output = string_stream.getvalue()
            # Severity is logged in lowercase
            assert "critical" in log_output

        finally:
            logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_log_session_event(self):
        """Test logging session events."""
        logger = logging.getLogger("archiflow.audit")
        logger.setLevel(logging.INFO)

        string_stream = StringIO()
        handler = logging.StreamHandler(string_stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            audit = LoggerAuditTrail()

            await audit.log_session_event(
                session_id="session_123",
                event_type="created",
                user_id="user_456",
                agent_type="coding",
            )

            # Check log output
            log_output = string_stream.getvalue()
            assert "SESSION_EVENT" in log_output
            assert "created" in log_output
            assert "session_123" in log_output

        finally:
            logger.removeHandler(handler)

    def test_format_params(self):
        """Test parameter formatting."""
        audit = LoggerAuditTrail()

        # Normal params
        params = {"file_path": "test.txt", "mode": "r"}
        formatted = audit._format_params(params)
        assert "file_path" in formatted
        assert "test.txt" in formatted

        # Long params
        long_params = {"content": "x" * 2000}
        formatted = audit._format_params(long_params)
        assert "truncated" in formatted
        assert "2000" in formatted  # Original length preserved in message

    def test_format_context(self):
        """Test context formatting."""
        audit = LoggerAuditTrail()

        context = {
            "session_id": "session_1",
            "user_id": "user_123",
            "workspace": "/workspace",
        }

        formatted = audit._format_context(context)

        assert "session_id=session_1" in formatted or "session_1" in formatted
        assert "user_id=user_123" in formatted or "user_123" in formatted

    def test_get_log_function(self):
        """Test getting log function for severity."""
        audit = LoggerAuditTrail()

        assert audit._get_log_function(AuditSeverity.INFO) == audit.logger.info
        assert audit._get_log_function(AuditSeverity.WARNING) == audit.logger.warning
        assert audit._get_log_function(AuditSeverity.ERROR) == audit.logger.error
        assert audit._get_log_function(AuditSeverity.CRITICAL) == audit.logger.critical

        # Unknown severity defaults to info
        assert audit._get_log_function("unknown") == audit.logger.info


class TestAuditSeverity:
    """Tests for AuditSeverity class."""

    def test_values(self):
        """Test severity values."""
        assert AuditSeverity.INFO == "info"
        assert AuditSeverity.WARNING == "warning"
        assert AuditSeverity.ERROR == "error"
        assert AuditSeverity.CRITICAL == "critical"

    def test_is_valid(self):
        """Test severity validation."""
        assert AuditSeverity.is_valid("info") is True
        assert AuditSeverity.is_valid("warning") is True
        assert AuditSeverity.is_valid("error") is True
        assert AuditSeverity.is_valid("critical") is True
        assert AuditSeverity.is_valid("invalid") is False


class TestAuditTrailInterface:
    """Tests that verify the AuditTrail interface contract."""

    @pytest.mark.asyncio
    async def test_all_methods_are_async(self):
        """Test that all interface methods are async."""
        audit = NullAuditTrail()

        # Should not raise TypeError
        await audit.log_execution("tool", {}, True)
        await audit.log_security_event("event", "info", "message")
        await audit.log_session_event("session", "created")

    @pytest.mark.asyncio
    async def test_methods_handle_none_parameters(self):
        """Test that methods handle None/error parameters gracefully."""
        audit = NullAuditTrail()

        # Should not raise exceptions
        await audit.log_execution("tool", {}, True, None)
        await audit.log_execution("tool", {}, False, error="Error message")

    @pytest.mark.asyncio
    async def test_methods_handle_metadata(self):
        """Test that methods accept arbitrary metadata."""
        audit = NullAuditTrail()

        # Should accept **kwargs
        await audit.log_execution("tool", {}, True, session_id="s1", user_id="u1")
        await audit.log_security_event("event", "info", "msg", key="value")
        await audit.log_session_event("session", "created", key="value", count=5)
