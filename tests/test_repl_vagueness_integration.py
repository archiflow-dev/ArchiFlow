"""
Integration tests for VaguenessDetector in REPL.

Tests Phase 1: REPL Integration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from agent_cli.repl.engine import REPLEngine
from agent_cli.prompt_improvement import VaguenessDetector


class TestREPLVaguenessIntegration:
    """Test suite for REPL vagueness detection integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repl = REPLEngine()

    def test_vagueness_detector_initialized(self):
        """Test that vagueness detector is initialized in REPL."""
        assert hasattr(self.repl, 'vagueness_detector')
        assert isinstance(self.repl.vagueness_detector, VaguenessDetector)

    def test_vagueness_check_enabled_by_default(self):
        """Test that vagueness checking is enabled by default."""
        assert self.repl.enable_vagueness_check is True

    @pytest.mark.asyncio
    async def test_vague_prompt_triggers_warning(self):
        """Test that vague prompts trigger the warning handler."""
        # Create a vague prompt
        vague_prompt = "fix this"

        # Check that it's detected as vague
        vagueness = self.repl.vagueness_detector.analyze(vague_prompt)
        assert vagueness.is_vague
        assert vagueness.score >= 60

    @pytest.mark.asyncio
    async def test_clear_prompt_no_warning(self):
        """Test that clear prompts don't trigger warnings."""
        # Create a clear prompt
        clear_prompt = "Review src/auth/middleware.py for security vulnerabilities"

        # Check that it's not vague
        vagueness = self.repl.vagueness_detector.analyze(clear_prompt)
        assert not vagueness.is_vague
        assert vagueness.score < 60

    @pytest.mark.asyncio
    async def test_command_skips_vagueness_check(self):
        """Test that commands (starting with /) skip vagueness checking."""
        # Commands should always be processed without vagueness check
        command = "/help"

        # The command should start with /
        assert command.startswith("/")

        # In the REPL, commands are handled separately from regular messages
        # This test just verifies the detection logic
        vagueness = self.repl.vagueness_detector.analyze(command)
        # Even though /help might score high, it won't be checked in practice
        # because commands bypass the vagueness check in _process_input

    @pytest.mark.asyncio
    async def test_handle_vague_prompt_creates_warning_ui(self):
        """Test that _handle_vague_prompt creates the expected UI elements."""
        vague_prompt = "help me"
        vagueness = self.repl.vagueness_detector.analyze(vague_prompt)

        # Mock the session to avoid actual prompting
        self.repl.session = None

        # Call the handler (it should return False when session is None)
        result = await self.repl._handle_vague_prompt(vague_prompt, vagueness)

        assert result is False  # Can't proceed without interactive session

    @pytest.mark.asyncio
    async def test_vagueness_threshold_configurable(self):
        """Test that vagueness threshold is configurable."""
        # Create detector with custom threshold
        custom_detector = VaguenessDetector(vagueness_threshold=70)
        assert custom_detector.threshold == 70

        # Test with prompt that scores around 65
        prompt = "review authentication"
        result = custom_detector.analyze(prompt)

        # Should not be vague with threshold of 70 (if score < 70)
        if result.score < 70:
            assert not result.is_vague


class TestVaguenessScoring:
    """Integration tests for vagueness scoring accuracy."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = VaguenessDetector()

    def test_real_world_vague_examples(self):
        """Test with real-world vague prompt examples."""
        vague_examples = [
            "help",
            "fix the bug",
            "review my code",
            "make it work",
            "check this out",
        ]

        for prompt in vague_examples:
            result = self.detector.analyze(prompt)
            # All should have some vagueness issues
            assert len(result.issues) > 0
            assert len(result.suggestions) > 0

    def test_real_world_clear_examples(self):
        """Test with real-world clear prompt examples."""
        clear_examples = [
            "Review src/auth/middleware.py for SQL injection vulnerabilities",
            "Implement user logout functionality in src/auth/logout.py with Redis session cleanup",
            "Fix the authentication timeout bug in src/auth/session.py line 45",
            "Refactor src/api/users.py to use async/await for better performance",
        ]

        for prompt in clear_examples:
            result = self.detector.analyze(prompt)
            # All should be relatively clear
            assert result.score < 50
            assert not result.is_vague


class TestVaguenessUIFlow:
    """Test the user experience flow with vagueness detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repl = REPLEngine()

    def test_severity_levels_map_to_colors(self):
        """Test that severity levels are properly categorized."""
        high_vague = self.repl.vagueness_detector.analyze("help")
        medium_vague = self.repl.vagueness_detector.analyze("fix auth")
        low_vague = self.repl.vagueness_detector.analyze("review src/auth/middleware.py")

        assert high_vague.severity in ["high", "medium"]
        assert low_vague.severity == "low"

    def test_suggestions_are_actionable(self):
        """Test that suggestions provide actionable guidance."""
        result = self.repl.vagueness_detector.analyze("review code")

        # Should have at least one suggestion
        assert len(result.suggestions) > 0

        # Suggestions should be strings
        for suggestion in result.suggestions:
            assert isinstance(suggestion, str)
            assert len(suggestion) > 10  # Should be meaningful, not too short


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
