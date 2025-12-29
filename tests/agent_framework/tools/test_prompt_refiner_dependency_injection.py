"""Tests for PromptRefinerTool explicit dependency injection."""

import unittest
from agent_framework.tools.prompt_refiner_tool import PromptRefinerTool
from agent_framework.llm.mock import MockLLMProvider


class TestPromptRefinerDependencyInjection(unittest.TestCase):
    """Test that PromptRefinerTool requires explicit LLM injection."""

    def test_requires_llm_provider(self):
        """Test that LLM provider is required."""
        with self.assertRaises(TypeError) as context:
            tool = PromptRefinerTool()  # Should fail - no LLM!

        # Verify error message is helpful
        error_msg = str(context.exception)
        self.assertIn("requires an explicit LLM provider", error_msg)
        self.assertIn("create_llm_provider()", error_msg)

    def test_requires_non_none_llm(self):
        """Test that None LLM is rejected."""
        with self.assertRaises(TypeError) as context:
            tool = PromptRefinerTool(llm=None)  # Should fail - None!

        error_msg = str(context.exception)
        self.assertIn("requires an explicit LLM provider", error_msg)

    def test_works_with_explicit_llm(self):
        """Test that tool works with explicit LLM."""
        llm = MockLLMProvider()
        tool = PromptRefinerTool(llm=llm)

        # Should succeed
        self.assertIsNotNone(tool)
        self.assertEqual(tool.llm, llm)

    def test_error_message_includes_example(self):
        """Test that error message includes usage example."""
        with self.assertRaises(TypeError) as context:
            tool = PromptRefinerTool()

        error_msg = str(context.exception)

        # Should include example code
        self.assertIn("from agent_cli.agents.llm_provider_factory", error_msg)
        self.assertIn("create_llm_provider()", error_msg)
        self.assertIn("PromptRefinerTool(llm=llm)", error_msg)


if __name__ == '__main__':
    unittest.main()
