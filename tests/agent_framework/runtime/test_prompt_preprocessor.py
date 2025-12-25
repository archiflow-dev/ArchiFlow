"""
Unit tests for PromptPreprocessor (Option 3: Pre-Processing Hook).

Tests the pre-processor that refines user prompts BEFORE they reach the agent,
ensuring zero contamination of system prompt and conversation history.
"""
import asyncio
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.runtime.prompt_preprocessor import (
    PromptPreprocessor,
    create_refinement_notification,
    get_last_refinement_action,
    _set_last_refinement_action,
)
from agent_framework.messages.types import UserMessage
from agent_framework.llm.mock import MockLLMProvider


class MockToolResult:
    """Mock ToolResult for testing."""
    def __init__(self, output, error=None):
        self.output = output
        self.error = error


class TestPromptPreprocessor(unittest.TestCase):
    """Test suite for PromptPreprocessor."""

    def setUp(self):
        """Set up test fixtures."""
        self.llm = MockLLMProvider(model="mock-model")

    def test_initialization_default_values(self):
        """Test that preprocessor initializes with default values."""
        with patch.dict(os.environ, {}, clear=True):
            preprocessor = PromptPreprocessor(llm=self.llm)

            # Should be disabled by default
            self.assertFalse(preprocessor.enabled)
            self.assertEqual(preprocessor.threshold, 8.0)  # Updated default
            self.assertEqual(preprocessor.min_length, 10)

    def test_initialization_from_env(self):
        """Test initialization from environment variables."""
        with patch.dict(os.environ, {
            "AUTO_REFINE_PROMPTS": "true",
            "AUTO_REFINE_THRESHOLD": "8.5",
            "AUTO_REFINE_MIN_LENGTH": "20"
        }):
            preprocessor = PromptPreprocessor(llm=self.llm)

            self.assertTrue(preprocessor.enabled)
            self.assertEqual(preprocessor.threshold, 8.5)
            self.assertEqual(preprocessor.min_length, 20)

    def test_initialization_with_parameters(self):
        """Test initialization with explicit parameters."""
        preprocessor = PromptPreprocessor(
            llm=self.llm,
            threshold=7.0,
            min_length=5,
            enabled=True
        )

        self.assertTrue(preprocessor.enabled)
        self.assertEqual(preprocessor.threshold, 7.0)
        self.assertEqual(preprocessor.min_length, 5)

    def test_disabled_returns_original(self):
        """Test that when disabled, original message is returned unchanged."""
        preprocessor = PromptPreprocessor(llm=self.llm, enabled=False)

        async def test():
            message = UserMessage(
                session_id="test",
                sequence=1,
                content="Fix the bug"
            )

            result = await preprocessor.process(message)
            self.assertEqual(result.content, "Fix the bug")
            self.assertIs(result, message)

        asyncio.run(test())

    def test_short_message_passes_through(self):
        """Test that short messages pass through unchanged."""
        preprocessor = PromptPreprocessor(
            llm=self.llm,
            enabled=True,
            min_length=10
        )

        async def test():
            message = UserMessage(
                session_id="test",
                sequence=1,
                content="yes"
            )

            result = await preprocessor.process(message)
            self.assertEqual(result.content, "yes")

        asyncio.run(test())

    def test_command_passes_through(self):
        """Test that commands (starting with /) pass through unchanged."""
        preprocessor = PromptPreprocessor(llm=self.llm, enabled=True)

        async def test():
            message = UserMessage(
                session_id="test",
                sequence=1,
                content="/help"
            )

            result = await preprocessor.process(message)
            self.assertEqual(result.content, "/help")

        asyncio.run(test())

    def test_quality_above_threshold_passes_through(self):
        """Test that prompts with quality >= threshold pass through unchanged."""
        preprocessor = PromptPreprocessor(
            llm=self.llm,
            enabled=True,
            threshold=9.0
        )

        # Create a mock refiner tool
        mock_refiner = Mock()
        mock_result = MockToolResult(
            output='{"quality_score": 9.5, "refined_prompt": "Same content", "task_type": "coding", "refinement_level": "pass_through"}'
        )

        async def mock_execute(prompt):
            return mock_result

        mock_refiner.execute = mock_execute
        preprocessor._refiner = mock_refiner  # Directly set the mock

        async def test():
            message = UserMessage(
                session_id="test",
                sequence=1,
                content="Fix the authentication bug in src/auth.py:42"
            )

            result = await preprocessor.process(message)
            self.assertEqual(result.content, "Fix the authentication bug in src/auth.py:42")

        asyncio.run(test())

    def test_quality_below_threshold_gets_refined(self):
        """Test that prompts with quality < threshold get refined."""
        preprocessor = PromptPreprocessor(
            llm=self.llm,
            enabled=True,
            threshold=9.0
        )

        # Create a mock refiner tool
        mock_refiner = Mock()
        mock_result = MockToolResult(
            output='{"quality_score": 5.0, "refined_prompt": "Fix the authentication timeout bug in src/auth.py", "task_type": "coding", "refinement_level": "full_transformation"}'
        )

        async def mock_execute(prompt):
            return mock_result

        mock_refiner.execute = mock_execute
        preprocessor._refiner = mock_refiner  # Directly set the mock

        async def test():
            message = UserMessage(
                session_id="test",
                sequence=1,
                content="Fix the bug"
            )

            result = await preprocessor.process(message)
            self.assertEqual(result.content, "Fix the authentication timeout bug in src/auth.py")

        asyncio.run(test())

    def test_refiner_error_returns_original(self):
        """Test that if refiner returns an error, original message is returned."""
        preprocessor = PromptPreprocessor(llm=self.llm, enabled=True)

        # Create a mock refiner tool
        mock_refiner = Mock()
        mock_result = MockToolResult(
            output=None,
            error="Refiner failed"
        )

        async def mock_execute(prompt):
            return mock_result

        mock_refiner.execute = mock_execute
        preprocessor._refiner = mock_refiner  # Directly set the mock

        async def test():
            message = UserMessage(
                session_id="test",
                sequence=1,
                content="Fix the bug"
            )

            result = await preprocessor.process(message)
            self.assertEqual(result.content, "Fix the bug")

        asyncio.run(test())

    def test_json_parsing_handles_plain_json(self):
        """Test JSON parsing with plain JSON output."""
        preprocessor = PromptPreprocessor(llm=self.llm, enabled=True)

        json_str = '{"quality_score": 8.5, "refined_prompt": "Test", "task_type": "coding", "refinement_level": "light"}'
        result = preprocessor._parse_analysis(json_str)

        self.assertIsNotNone(result)
        self.assertEqual(result["quality_score"], 8.5)
        self.assertEqual(result["refined_prompt"], "Test")

    def test_json_parsing_handles_markdown_wrapped(self):
        """Test JSON parsing with markdown code blocks."""
        preprocessor = PromptPreprocessor(llm=self.llm, enabled=True)

        markdown_json = '```json\n{"quality_score": 8.5, "refined_prompt": "Test", "task_type": "coding", "refinement_level": "light"}\n```'
        result = preprocessor._parse_analysis(markdown_json)

        self.assertIsNotNone(result)
        self.assertEqual(result["quality_score"], 8.5)

    def test_json_parsing_handles_text_around_json(self):
        """Test JSON parsing with text before/after JSON."""
        preprocessor = PromptPreprocessor(llm=self.llm, enabled=True)

        messy_json = 'Some text before\n```json\n{"quality_score": 8.5}\n```\nSome text after'
        result = preprocessor._parse_analysis(messy_json)

        self.assertIsNotNone(result)
        self.assertEqual(result["quality_score"], 8.5)

    def test_json_parsing_returns_none_on_invalid(self):
        """Test JSON parsing returns None for invalid input."""
        preprocessor = PromptPreprocessor(llm=self.llm, enabled=True)

        result = preprocessor._parse_analysis("not json at all")
        self.assertIsNone(result)

        result = preprocessor._parse_analysis("")
        self.assertIsNone(result)

        result = preprocessor._parse_analysis(None)
        self.assertIsNone(result)


class TestRefinementNotification(unittest.TestCase):
    """Test suite for refinement notification functions."""

    def test_create_refinement_notification(self):
        """Test notification message creation."""
        notification = create_refinement_notification(
            original="Fix the bug",
            refined="Fix the authentication bug in src/auth.py",
            quality=8.5,
            task_type="coding",
            refinement_level="light_enhancement"
        )

        self.assertIn("Auto-Refinement Applied", notification)
        self.assertIn("8.5/10", notification)
        self.assertIn("Fix the bug", notification)
        self.assertIn("Fix the authentication bug in src/auth.py", notification)
        self.assertIn("coding", notification)

    def test_last_refinement_action_storage(self):
        """Test storage and retrieval of last refinement action."""
        _set_last_refinement_action(
            original="Fix bug",
            refined="Fix auth bug",
            quality=8.0,
            task_type="coding",
            refinement_level="light"
        )

        action = get_last_refinement_action()
        self.assertIsNotNone(action)
        self.assertEqual(action["original"], "Fix bug")
        self.assertEqual(action["quality"], 8.0)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for pre-processor."""

    def setUp(self):
        """Set up test fixtures."""
        self.llm = MockLLMProvider(model="mock-model")

    def test_conservative_threshold_only_refines_very_poor(self):
        """Test conservative threshold (6.0) only refines very poor prompts."""
        preprocessor = PromptPreprocessor(
            llm=self.llm,
            enabled=True,
            threshold=6.0,
            min_length=3  # Allow short messages for this test
        )

        # Quality 5.0 - should refine
        mock_result_poor = MockToolResult(
            output='{"quality_score": 5.0, "refined_prompt": "Detailed fix", "task_type": "coding", "refinement_level": "full"}'
        )

        # Quality 7.0 - should pass through (above conservative threshold)
        mock_result_ok = MockToolResult(
            output='{"quality_score": 7.0, "refined_prompt": "Slightly better", "task_type": "coding", "refinement_level": "light"}'
        )

        # Test with poor quality - should refine
        async def mock_execute_poor(prompt):
            return mock_result_poor

        mock_refiner_poor = Mock()
        mock_refiner_poor.execute = mock_execute_poor
        preprocessor._refiner = mock_refiner_poor

        async def test_poor():
            message1 = UserMessage(session_id="test", sequence=1, content="Bad")
            result1 = await preprocessor.process(message1)
            self.assertEqual(result1.content, "Detailed fix")

        asyncio.run(test_poor())

        # Test with OK quality - should pass through
        async def mock_execute_ok(prompt):
            return mock_result_ok

        mock_refiner_ok = Mock()
        mock_refiner_ok.execute = mock_execute_ok
        preprocessor._refiner = mock_refiner_ok

        async def test_ok():
            message2 = UserMessage(session_id="test", sequence=2, content="OK prompt")
            result2 = await preprocessor.process(message2)
            self.assertEqual(result2.content, "OK prompt")  # Original, not refined

        asyncio.run(test_ok())

    def test_aggressive_threshold_always_refines(self):
        """Test aggressive threshold (10.0) always tries to refine."""
        preprocessor = PromptPreprocessor(
            llm=self.llm,
            enabled=True,
            threshold=10.0
        )

        # Even quality 9.5 should be refined with threshold of 10.0
        mock_result = MockToolResult(
            output='{"quality_score": 9.5, "refined_prompt": "Even better version", "task_type": "coding", "refinement_level": "light"}'
        )

        async def mock_execute(prompt):
            return mock_result

        mock_refiner = Mock()
        mock_refiner.execute = mock_execute
        preprocessor._refiner = mock_refiner

        async def test():
            message = UserMessage(
                session_id="test",
                sequence=1,
                content="Great prompt with 9.5 quality"
            )
            result = await preprocessor.process(message)
            # With threshold 10.0, even 9.5 gets refined
            self.assertEqual(result.content, "Even better version")

        asyncio.run(test())


if __name__ == '__main__':
    unittest.main()
