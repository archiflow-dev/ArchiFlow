"""Tests for PromptRefinerTool."""
import unittest
import asyncio
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.tools.prompt_refiner_tool import PromptRefinerTool
from agent_framework.llm.provider import LLMProvider, LLMResponse, FinishReason
from agent_framework.runtime.context import ExecutionContext


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, response_content: str):
        # Call parent with a dummy model name
        super().__init__(model="mock-model", usage_tracker=None)
        self.response_content = response_content
        self.last_messages = None

    def generate(self, messages, tools=None, **kwargs):
        """Mock generate method."""
        self.last_messages = messages
        return LLMResponse(
            content=self.response_content,
            finish_reason=FinishReason.STOP
        )

    def stream(self, messages, tools=None, **kwargs):
        """Mock stream method (not used in tests)."""
        raise NotImplementedError("Streaming not implemented in mock")


class TestPromptRefinerTool(unittest.TestCase):
    """Test PromptRefinerTool functionality."""

    def test_initialization(self):
        """Test tool can be initialized."""
        tool = PromptRefinerTool()

        self.assertEqual(tool.name, "refine_prompt")
        self.assertIsNotNone(tool.description)
        self.assertIn("prompt", tool.parameters["properties"])
        self.assertEqual(tool.parameters["required"], ["prompt"])

    def test_parameters_schema(self):
        """Test parameter schema is correct."""
        tool = PromptRefinerTool()

        # Check prompt parameter
        self.assertIn("prompt", tool.parameters["properties"])
        self.assertEqual(tool.parameters["properties"]["prompt"]["type"], "string")

        # Check session_context parameter
        self.assertIn("session_context", tool.parameters["properties"])
        self.assertEqual(tool.parameters["properties"]["session_context"]["type"], "string")
        self.assertEqual(tool.parameters["properties"]["session_context"]["default"], "")

    def test_execute_without_llm(self):
        """Test execute fails gracefully without LLM provider."""
        # Mock environment to prevent auto-creation
        with patch.dict(os.environ, {}, clear=True):
            # Create tool without LLM (and env is empty)
            tool = PromptRefinerTool()

            # Run async test
            async def run_test():
                result = await tool.execute(prompt="Test prompt")
                self.assertIsNotNone(result.error)
                self.assertIn("LLM provider", result.error)

            asyncio.run(run_test())

    def test_auto_create_llm_from_env(self):
        """Test LLM provider is auto-created from environment."""
        # Mock environment with valid settings
        env = {
            'DEFAULT_LLM_PROVIDER': 'mock',
        }

        with patch.dict(os.environ, env, clear=True):
            # Create tool without explicit LLM
            tool = PromptRefinerTool()

            # Should have auto-created an LLM provider
            self.assertIsNotNone(tool.llm)
            # Verify it's a valid LLM provider (has generate method)
            self.assertTrue(hasattr(tool.llm, 'generate'))

    def test_auto_create_with_custom_model(self):
        """Test LLM auto-creation with PROMPT_REFINER_MODEL override."""
        # Mock environment with custom model
        env = {
            'DEFAULT_LLM_PROVIDER': 'mock',
            'PROMPT_REFINER_MODEL': 'custom-model-123'
        }

        with patch.dict(os.environ, env, clear=True):
            # Create tool without explicit LLM
            tool = PromptRefinerTool()

            # Should have auto-created with custom model
            self.assertIsNotNone(tool.llm)
            self.assertEqual(tool.llm.model, 'custom-model-123')

    def test_execute_with_empty_prompt(self):
        """Test execute fails with empty prompt."""
        mock_llm = MockLLMProvider("{}")
        tool = PromptRefinerTool(llm=mock_llm)

        async def run_test():
            result = await tool.execute(prompt="")
            self.assertIsNotNone(result.error)
            self.assertIn("empty", result.error.lower())

        asyncio.run(run_test())

    def test_execute_with_valid_prompt(self):
        """Test execute with valid prompt and LLM response."""
        # Mock LLM response
        mock_response = {
            "detected_task_type": "software_development",
            "detected_domain": "backend_api",
            "user_intent": "Build an API",
            "quality_score": 3.2,
            "refinement_level": "full_transformation",
            "assessment_summary": "Needs significant enhancement",
            "quality_analysis": {
                "clarity": 4,
                "specificity": 2,
                "actionability": 2,
                "completeness": 3,
                "structure": 5
            },
            "issues_identified": ["Missing technology stack"],
            "original_prompt": "Build an API",
            "refined_prompt": "Build a RESTful API with...",
            "refinement_rationale": "Added structure",
            "suggested_follow_up_questions": ["What framework?"]
        }

        mock_llm = MockLLMProvider(json.dumps(mock_response))
        tool = PromptRefinerTool(llm=mock_llm)

        async def run_test():
            result = await tool.execute(prompt="Build an API")

            # Should succeed
            self.assertIsNone(result.error)
            self.assertIsNotNone(result.output)

            # Parse output
            output = json.loads(result.output)
            self.assertEqual(output["detected_task_type"], "software_development")
            self.assertEqual(output["quality_score"], 3.2)
            self.assertEqual(output["refinement_level"], "full_transformation")

        asyncio.run(run_test())

    def test_execute_with_session_context(self):
        """Test execute includes session context in meta-prompt."""
        mock_response = {
            "detected_task_type": "test",
            "detected_domain": "test",
            "user_intent": "test",
            "quality_score": 8.0,
            "refinement_level": "pass_through",
            "assessment_summary": "Good",
            "quality_analysis": {"clarity": 8, "specificity": 8, "actionability": 8, "completeness": 8, "structure": 8},
            "issues_identified": [],
            "original_prompt": "Test",
            "refined_prompt": "Test",
            "refinement_rationale": "None",
            "suggested_follow_up_questions": []
        }

        mock_llm = MockLLMProvider(json.dumps(mock_response))
        tool = PromptRefinerTool(llm=mock_llm)

        async def run_test():
            await tool.execute(
                prompt="Build an API",
                session_context="User is working on Python FastAPI project"
            )

            # Check that session context was included in the meta-prompt
            self.assertIsNotNone(mock_llm.last_messages)
            meta_prompt = mock_llm.last_messages[0]["content"]
            self.assertIn("Python FastAPI project", meta_prompt)

        asyncio.run(run_test())

    def test_hierarchical_meta_prompt_loading_embedded(self):
        """Test meta-prompt loads embedded fallback when no files exist."""
        tool = PromptRefinerTool()

        # Load with no working directory and no files
        template = tool._load_meta_prompt_template()

        # Should have loaded something (embedded or framework default)
        self.assertIsNotNone(template)
        self.assertIn("prompt", template.lower())

    def test_hierarchical_meta_prompt_loading_project_specific(self):
        """Test meta-prompt loads from project-specific location."""
        # Create temporary directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project-specific meta-prompt
            project_prompt_dir = Path(tmpdir) / ".archiflow" / "tools" / "prompt_refiner"
            project_prompt_dir.mkdir(parents=True)
            project_prompt_file = project_prompt_dir / "system_prompt.md"
            project_prompt_file.write_text("PROJECT SPECIFIC META-PROMPT")

            # Create execution context with temp directory
            context = ExecutionContext(
                session_id="test",
                working_directory=tmpdir
            )

            # Create tool with context
            tool = PromptRefinerTool()
            tool.execution_context = context
            tool.meta_prompt_template_cache = None  # Reset cache

            # Load template
            template = tool._load_meta_prompt_template()

            # Should have loaded project-specific version
            self.assertEqual(template, "PROJECT SPECIFIC META-PROMPT")

    def test_meta_prompt_caching(self):
        """Test meta-prompt template is cached after first load."""
        tool = PromptRefinerTool()

        # First load
        template1 = tool._load_meta_prompt_template()

        # Second load should use cache
        template2 = tool._load_meta_prompt_template()

        # Should be same instance (cached)
        self.assertIs(template1, template2)

    def test_build_meta_prompt_replaces_placeholders(self):
        """Test _build_meta_prompt replaces placeholders correctly."""
        tool = PromptRefinerTool()
        tool.meta_prompt_template_cache = "User prompt: {prompt}\nContext: {session_context}"

        result = tool._build_meta_prompt(
            prompt="Test prompt",
            session_context="Test context"
        )

        self.assertIn("Test prompt", result)
        self.assertIn("Test context", result)
        self.assertNotIn("{prompt}", result)
        self.assertNotIn("{session_context}", result)

    def test_invalid_json_response(self):
        """Test handling of invalid JSON from LLM."""
        mock_llm = MockLLMProvider("This is not JSON")
        tool = PromptRefinerTool(llm=mock_llm)

        async def run_test():
            result = await tool.execute(prompt="Test prompt")

            # Should fail with JSON parse error
            self.assertIsNotNone(result.error)
            self.assertIn("JSON", result.error)

        asyncio.run(run_test())

    def test_missing_fields_in_response(self):
        """Test handling of missing fields in LLM response."""
        # Response missing some fields
        incomplete_response = {
            "detected_task_type": "test",
            "quality_score": 8.0
            # Missing many required fields
        }

        mock_llm = MockLLMProvider(json.dumps(incomplete_response))
        tool = PromptRefinerTool(llm=mock_llm)

        async def run_test():
            result = await tool.execute(prompt="Test prompt")

            # Should still succeed by adding defaults
            self.assertIsNone(result.error)
            output = json.loads(result.output)

            # Check default values were added
            self.assertIn("quality_analysis", output)
            self.assertIn("issues_identified", output)

        asyncio.run(run_test())

    def test_parse_json_response_pure(self):
        """Test parsing pure JSON."""
        tool = PromptRefinerTool()

        pure_json = '{"key": "value", "number": 123}'
        result = tool._parse_json_response(pure_json)

        self.assertEqual(result["key"], "value")
        self.assertEqual(result["number"], 123)

    def test_parse_json_response_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        tool = PromptRefinerTool()

        # Test ```json ... ```
        markdown_json = '```json\n{"key": "value"}\n```'
        result = tool._parse_json_response(markdown_json)
        self.assertEqual(result["key"], "value")

        # Test ``` ... ```
        markdown_json2 = '```\n{"key": "value2"}\n```'
        result2 = tool._parse_json_response(markdown_json2)
        self.assertEqual(result2["key"], "value2")

    def test_parse_json_response_with_text(self):
        """Test parsing JSON with surrounding text."""
        tool = PromptRefinerTool()

        # JSON with text before and after
        mixed_content = 'Here is the result:\n{"key": "value"}\nThat was the result.'
        result = tool._parse_json_response(mixed_content)
        self.assertEqual(result["key"], "value")

    def test_parse_json_response_invalid(self):
        """Test parsing fails with invalid content."""
        tool = PromptRefinerTool()

        # No JSON at all
        with self.assertRaises(json.JSONDecodeError):
            tool._parse_json_response("This is just text with no JSON")

        # Malformed JSON
        with self.assertRaises(json.JSONDecodeError):
            tool._parse_json_response("{key: invalid}")


if __name__ == '__main__':
    unittest.main()
