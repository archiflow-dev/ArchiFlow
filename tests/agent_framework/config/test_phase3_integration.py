"""
Unit Tests for Phase 3: Agent Integration with ConfigHierarchy.

Tests the integration of ConfigHierarchy with:
1. PromptPreprocessor
2. AgentController
3. BaseAgent
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from dataclasses import dataclass

from agent_framework.config.hierarchy import ConfigHierarchy, ConfigSnapshot
from agent_framework.runtime.prompt_preprocessor import PromptPreprocessor
from agent_framework.agent_controller import AgentController
from agent_framework.agents.base import BaseAgent, SimpleAgent
from agent_framework.llm.provider import LLMProvider
from agent_framework.tools.tool_base import ToolRegistry
from message_queue.broker import MessageBroker
from agent_framework.context import TopicContext


@dataclass
class MockModelConfig:
    """Mock model config for testing."""
    model_name: str = "test-model"
    context_window: int = 100000
    max_output_tokens: int = 4000
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    supports_tools: bool = True

    def get_available_context(
        self,
        system_prompt_tokens: int = 0,
        tools_tokens: int = 0,
        buffer_tokens: int = 500
    ) -> int:
        """Calculate available context tokens."""
        reserved = system_prompt_tokens + tools_tokens + self.max_output_tokens + buffer_tokens
        available = self.context_window - reserved
        return max(available, 1000)  # Minimum 1000 tokens


class TestPromptPreprocessorIntegration(unittest.TestCase):
    """Test PromptPreprocessor integration with ConfigHierarchy."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archiflow_dir = self.temp_dir / ".archiflow"
        self.archiflow_dir.mkdir(parents=True)

        # Create a mock LLM provider
        self.mock_llm = Mock(spec=LLMProvider)
        self.mock_llm.model = "test-model"
        self.mock_llm.model_config = MockModelConfig()
        self.mock_llm.generate.return_value = MagicMock(
            content='{"quality_score": 8.0, "refined_prompt": "Refined prompt"}',
            tool_calls=None
        )

        # Clean environment variables for testing
        self._env_backup = {}
        for key in ["AUTO_REFINE_THRESHOLD", "AUTO_REFINE_MIN_LENGTH", "AUTO_REFINE_PROMPTS"]:
            if key in os.environ:
                self._env_backup[key] = os.environ[key]
                del os.environ[key]

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

        # Restore environment variables
        for key, value in self._env_backup.items():
            os.environ[key] = value

    def test_preprocessor_with_config_snapshot(self):
        """Test PromptPreprocessor loads config from ConfigSnapshot."""
        # Create settings.json with autoRefinement config
        settings = {
            "autoRefinement": {
                "enabled": True,
                "threshold": 7.5,
                "minLength": 20
            }
        }
        settings_path = self.archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        # Load config hierarchy
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)
        snapshot = hierarchy.load()

        # Create preprocessor with config snapshot
        preprocessor = PromptPreprocessor(
            llm=self.mock_llm,
            config_snapshot=snapshot
        )

        # Verify settings from hierarchy
        self.assertTrue(preprocessor.enabled)
        self.assertEqual(preprocessor.threshold, 7.5)
        self.assertEqual(preprocessor.min_length, 20)

    def test_preprocessor_config_precedence(self):
        """Test configuration precedence: param > hierarchy > env > default."""
        # Create settings with threshold 8.0
        settings = {"autoRefinement": {"threshold": 8.0}}
        settings_path = self.archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)
        snapshot = hierarchy.load()

        # Test 1: Parameter has highest precedence
        preprocessor = PromptPreprocessor(
            llm=self.mock_llm,
            threshold=9.5,
            config_snapshot=snapshot
        )
        self.assertEqual(preprocessor.threshold, 9.5)

        # Test 2: ConfigSnapshot used when no parameter
        preprocessor2 = PromptPreprocessor(
            llm=self.mock_llm,
            config_snapshot=snapshot
        )
        self.assertEqual(preprocessor2.threshold, 8.0)

    def test_preprocessor_backward_compatibility(self):
        """Test backward compatibility with environment variables."""
        # Remove config file - should fall back to env vars
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)

        # Set environment variable
        os.environ["AUTO_REFINE_THRESHOLD"] = "7.0"

        try:
            preprocessor = PromptPreprocessor(
                llm=self.mock_llm,
                config_snapshot=hierarchy.load()  # Empty snapshot
            )
            # Should use env var when hierarchy has no value
            self.assertEqual(preprocessor.threshold, 7.0)
        finally:
            # Clean up
            if "AUTO_REFINE_THRESHOLD" in os.environ:
                del os.environ["AUTO_REFINE_THRESHOLD"]

    def test_preprocessor_defaults_when_no_config(self):
        """Test default values when no config is provided."""
        preprocessor = PromptPreprocessor(llm=self.mock_llm)

        self.assertEqual(preprocessor.threshold, 8.0)  # DEFAULT_THRESHOLD
        self.assertEqual(preprocessor.min_length, 10)  # DEFAULT_MIN_LENGTH
        self.assertFalse(preprocessor.enabled)  # Default


class TestAgentControllerIntegration(unittest.TestCase):
    """Test AgentController integration with ConfigHierarchy."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create mock agent
        self.mock_agent = Mock(spec=BaseAgent)
        self.mock_agent.llm = Mock()
        self.mock_agent.llm.model = "test-model"

        # Create mock broker and context
        self.mock_broker = Mock(spec=MessageBroker)
        self.mock_context = Mock(spec=TopicContext)
        self.mock_context.client_topic = "client"
        self.mock_context.agent_topic = "agent"
        self.mock_context.runtime_topic = "runtime"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_controller_creates_config_hierarchy(self):
        """Test AgentController creates ConfigHierarchy."""
        controller = AgentController(
            agent=self.mock_agent,
            broker=self.mock_broker,
            context=self.mock_context,
            working_dir=self.temp_dir
        )

        # Verify ConfigHierarchy was created
        self.assertIsInstance(controller.config_hierarchy, ConfigHierarchy)
        self.assertEqual(controller.working_dir, self.temp_dir)

    def test_controller_passes_config_to_preprocessor(self):
        """Test AgentController passes config to PromptPreprocessor."""
        # Create settings.json
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir(parents=True)
        settings = {
            "autoRefinement": {
                "enabled": True,
                "threshold": 8.5
            }
        }
        settings_path = archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        # Create controller
        controller = AgentController(
            agent=self.mock_agent,
            broker=self.mock_broker,
            context=self.mock_context,
            working_dir=self.temp_dir
        )

        # Verify preprocessor has correct config
        self.assertTrue(controller.prompt_preprocessor.enabled)
        self.assertEqual(controller.prompt_preprocessor.threshold, 8.5)

    def test_controller_default_working_dir(self):
        """Test AgentController uses current working directory by default."""
        import os
        expected_dir = Path(os.getcwd())

        controller = AgentController(
            agent=self.mock_agent,
            broker=self.mock_broker,
            context=self.mock_context
        )

        self.assertEqual(controller.working_dir, expected_dir)

    def test_controller_reload_config(self):
        """Test reload_config method."""
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir(parents=True)
        settings_path = archiflow_dir / "settings.json"

        # Initial settings
        settings = {"autoRefinement": {"threshold": 7.0}}
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        controller = AgentController(
            agent=self.mock_agent,
            broker=self.mock_broker,
            context=self.mock_context,
            working_dir=self.temp_dir
        )

        self.assertEqual(controller.prompt_preprocessor.threshold, 7.0)

        # Update settings
        settings["autoRefinement"]["threshold"] = 9.0
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        # Reload config
        controller.reload_config()

        # Verify preprocessor has new threshold
        self.assertEqual(controller.prompt_preprocessor.threshold, 9.0)


class TestBaseAgentIntegration(unittest.TestCase):
    """Test BaseAgent integration with working directory."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create mock LLM
        self.mock_llm = Mock(spec=LLMProvider)
        self.mock_llm.model = "test-model"
        self.mock_llm.model_config = MockModelConfig()
        self.mock_llm.count_tokens.return_value = 100
        self.mock_llm.count_tools_tokens.return_value = 50

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_baseagent_accepts_working_dir(self):
        """Test BaseAgent accepts working_dir parameter."""
        # Create SimpleAgent with working_dir
        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm,
            working_dir=self.temp_dir
        )

        self.assertEqual(agent.working_dir, self.temp_dir)

    def test_baseagent_default_working_dir(self):
        """Test BaseAgent uses current directory by default."""
        import os
        expected_dir = Path(os.getcwd())

        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm
        )

        self.assertEqual(agent.working_dir, expected_dir)

    def test_baseagent_system_message_includes_working_dir(self):
        """Test BaseAgent includes working directory in system message."""
        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm,
            working_dir=self.temp_dir
        )

        system_msg = agent.get_system_message()

        # Should include working directory
        self.assertIn(str(self.temp_dir), system_msg)
        self.assertIn("Working Directory:", system_msg)

    def test_baseagent_without_working_dir(self):
        """Test BaseAgent works without working_dir parameter."""
        # Should not raise error
        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm
        )

        # working_dir should be set to current directory
        self.assertIsNotNone(agent.working_dir)

    def test_simpleagent_passes_working_dir_to_base(self):
        """Test SimpleAgent passes working_dir to BaseAgent."""
        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm,
            working_dir=self.temp_dir
        )

        # Verify working_dir is set on the agent
        self.assertEqual(agent.working_dir, self.temp_dir)


class TestEndToEndIntegration(unittest.TestCase):
    """End-to-end integration tests for Phase 3."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.archiflow_dir = self.temp_dir / ".archiflow"
        self.archiflow_dir.mkdir(parents=True)

        # Mock LLM
        self.mock_llm = Mock(spec=LLMProvider)
        self.mock_llm.model = "test-model"
        self.mock_llm.model_config = MockModelConfig()
        self.mock_llm.count_tokens.return_value = 100
        self.mock_llm.count_tools_tokens.return_value = 50

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_full_config_flow_hierarchy_to_agent(self):
        """Test full flow: config hierarchy -> controller -> preprocessor."""
        # Create config file
        settings = {
            "autoRefinement": {
                "enabled": True,
                "threshold": 8.0,
                "minLength": 15
            }
        }
        settings_path = self.archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        # Create agent with working_dir
        agent = SimpleAgent(
            session_id="test",
            llm=self.mock_llm,
            working_dir=self.temp_dir
        )

        # Create controller
        mock_broker = Mock(spec=MessageBroker)
        mock_context = Mock(spec=TopicContext)
        mock_context.client_topic = "client"
        mock_context.agent_topic = "agent"
        mock_context.runtime_topic = "runtime"

        controller = AgentController(
            agent=agent,
            broker=mock_broker,
            context=mock_context,
            working_dir=self.temp_dir
        )

        # Verify full integration
        self.assertEqual(controller.working_dir, self.temp_dir)
        self.assertTrue(controller.prompt_preprocessor.enabled)
        self.assertEqual(controller.prompt_preprocessor.threshold, 8.0)
        self.assertEqual(controller.prompt_preprocessor.min_length, 15)
        self.assertEqual(agent.working_dir, self.temp_dir)

    def test_multiple_hierarchy_levels_override(self):
        """Test that higher hierarchy levels override lower ones."""
        # Create global config (lower priority)
        global_dir = Path.home() / ".archiflow"
        global_dir.mkdir(parents=True, exist_ok=True)
        global_settings_path = global_dir / "settings.json"

        # Only create if doesn't exist to avoid disrupting user's actual config
        created_global = False
        if not global_settings_path.exists():
            global_settings_path.write_text(json.dumps({
                "autoRefinement": {"threshold": 7.0}
            }), encoding="utf-8")
            created_global = True

        try:
            # Create project config (higher priority)
            project_settings = {
                "autoRefinement": {"threshold": 9.0}
            }
            settings_path = self.archiflow_dir / "settings.json"
            settings_path.write_text(json.dumps(project_settings), encoding="utf-8")

            # Create controller
            agent = SimpleAgent(session_id="test", llm=self.mock_llm)
            mock_broker = Mock(spec=MessageBroker)
            mock_context = Mock(spec=TopicContext)

            controller = AgentController(
                agent=agent,
                broker=mock_broker,
                context=mock_context,
                working_dir=self.temp_dir
            )

            # Project config should override global
            self.assertEqual(controller.prompt_preprocessor.threshold, 9.0)

        finally:
            # Clean up global settings if we created it
            if created_global and global_settings_path.exists():
                global_settings_path.unlink()


if __name__ == "__main__":
    unittest.main()
