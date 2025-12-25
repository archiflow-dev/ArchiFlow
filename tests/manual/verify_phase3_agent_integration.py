"""
Manual Verification Script for Phase 3: Agent Integration

This script demonstrates the integration of ConfigHierarchy with the agent system:
1. PromptPreprocessor uses ConfigHierarchy for configuration
2. AgentController creates ConfigHierarchy and passes it to components
3. BaseAgent accepts working_dir parameter for environment context

Usage:
    python tests/manual/verify_phase3_agent_integration.py
"""
import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent_framework.config.hierarchy import ConfigHierarchy


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def verify_prompt_preprocessor_integration():
    """Verify PromptPreprocessor integrates with ConfigHierarchy."""
    print_header("1. PromptPreprocessor Integration")

    from agent_framework.runtime.prompt_preprocessor import PromptPreprocessor
    from unittest.mock import Mock

    # Create temporary directory with config
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archiflow_dir = tmpdir / ".archiflow"
        archiflow_dir.mkdir(parents=True)

        # Create settings.json with autoRefinement config
        settings = {
            "autoRefinement": {
                "enabled": True,
                "threshold": 8.5,
                "minLength": 20
            }
        }
        settings_path = archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

        print(f"Created: {settings_path}")
        print(json.dumps(settings, indent=2))

        # Load config hierarchy
        hierarchy = ConfigHierarchy(working_dir=tmpdir)
        snapshot = hierarchy.load()

        # Create mock LLM
        mock_llm = Mock()
        mock_llm.model = "test-model"

        # Create preprocessor with config snapshot
        preprocessor = PromptPreprocessor(
            llm=mock_llm,
            config_snapshot=snapshot
        )

        print("\nPromptPreprocessor configuration:")
        print(f"  enabled: {preprocessor.enabled}")
        print(f"  threshold: {preprocessor.threshold}")
        print(f"  min_length: {preprocessor.min_length}")

        # Verify
        assert preprocessor.enabled == True, "enabled should be True"
        assert preprocessor.threshold == 8.5, "threshold should be 8.5"
        assert preprocessor.min_length == 20, "min_length should be 20"

        print("\n[PASS] PromptPreprocessor integration verified!")


def verify_agent_controller_integration():
    """Verify AgentController creates and uses ConfigHierarchy."""
    print_header("2. AgentController Integration")

    from agent_framework.agent_controller import AgentController
    from agent_framework.agents.base import BaseAgent
    from unittest.mock import Mock, MagicMock
    from message_queue.broker import MessageBroker
    from agent_framework.context import TopicContext

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archiflow_dir = tmpdir / ".archiflow"
        archiflow_dir.mkdir(parents=True)

        # Create settings.json
        settings = {
            "autoRefinement": {
                "enabled": True,
                "threshold": 7.5,
                "minLength": 15
            }
        }
        settings_path = archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

        print(f"Created: {settings_path}")
        print(json.dumps(settings, indent=2))

        # Create mock agent
        mock_agent = Mock(spec=BaseAgent)
        mock_agent.llm = Mock()
        mock_agent.llm.model = "test-model"

        # Create mock broker and context
        mock_broker = Mock(spec=MessageBroker)
        mock_context = Mock(spec=TopicContext)
        mock_context.client_topic = "client"
        mock_context.agent_topic = "agent"
        mock_context.runtime_topic = "runtime"

        # Create controller
        controller = AgentController(
            agent=mock_agent,
            broker=mock_broker,
            context=mock_context,
            working_dir=tmpdir
        )

        print("\nAgentController configuration:")
        print(f"  working_dir: {controller.working_dir}")
        print(f"  config_hierarchy type: {type(controller.config_hierarchy).__name__}")
        print(f"  preprocessor.enabled: {controller.prompt_preprocessor.enabled}")
        print(f"  preprocessor.threshold: {controller.prompt_preprocessor.threshold}")
        print(f"  preprocessor.min_length: {controller.prompt_preprocessor.min_length}")

        # Verify
        assert controller.config_hierarchy is not None, "config_hierarchy should exist"
        assert controller.working_dir == tmpdir, "working_dir should match"
        assert controller.prompt_preprocessor.enabled == True, "enabled should be True"
        assert controller.prompt_preprocessor.threshold == 7.5, "threshold should be 7.5"

        print("\n[PASS] AgentController integration verified!")


def verify_base_agent_integration():
    """Verify BaseAgent accepts working_dir parameter."""
    print_header("3. BaseAgent Integration")

    from agent_framework.agents.base import SimpleAgent
    from unittest.mock import Mock
    from agent_framework.llm.model_config import ModelConfig
    from agent_framework.memory.summarizer import LLMSummarizer

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create mock LLM with proper model_config
        mock_llm = Mock()
        mock_llm.model = "test-model"
        mock_llm.model_config = ModelConfig(
            model_name="test-model",
            context_window=100000,
            max_output_tokens=4000
        )
        mock_llm.count_tokens.return_value = 100
        mock_llm.count_tools_tokens.return_value = 50

        # Create agent with working_dir
        agent = SimpleAgent(
            session_id="test",
            llm=mock_llm,
            working_dir=tmpdir
        )

        print(f"Created SimpleAgent with working_dir: {tmpdir}")
        print(f"\nAgent configuration:")
        print(f"  working_dir: {agent.working_dir}")
        print(f"  session_id: {agent.session_id}")

        # Verify working_dir is set
        assert agent.working_dir == tmpdir, "working_dir should match"

        # Verify system message includes working directory
        system_msg = agent.get_system_message()
        print(f"\nSystem message includes working directory:")
        print(f"  Contains '{tmpdir}': {str(tmpdir) in system_msg}")
        print(f"  Contains 'Working Directory:': {'Working Directory:' in system_msg}")

        assert str(tmpdir) in system_msg, "System message should include working directory"
        assert "Working Directory:" in system_msg, "System message should have label"

        print("\n[PASS] BaseAgent integration verified!")


def verify_end_to_end_flow():
    """Verify end-to-end configuration flow."""
    print_header("4. End-to-End Integration Flow")

    from agent_framework.config.hierarchy import ConfigHierarchy
    from agent_framework.runtime.prompt_preprocessor import PromptPreprocessor
    from agent_framework.agent_controller import AgentController
    from agent_framework.agents.base import SimpleAgent
    from agent_framework.llm.model_config import ModelConfig
    from unittest.mock import Mock
    from message_queue.broker import MessageBroker
    from agent_framework.context import TopicContext

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archiflow_dir = tmpdir / ".archiflow"
        archiflow_dir.mkdir(parents=True)

        # Create project config
        settings = {
            "autoRefinement": {
                "enabled": True,
                "threshold": 8.0,
                "minLength": 15
            },
            "agent": {
                "defaultModel": "claude-sonnet-4-5",
                "maxIterations": 5
            }
        }
        settings_path = archiflow_dir / "settings.json"
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

        print(f"Created project config: {settings_path}")
        print(json.dumps(settings, indent=2))

        # Step 1: Load config hierarchy
        print("\n--- Step 1: Load ConfigHierarchy ---")
        hierarchy = ConfigHierarchy(working_dir=tmpdir)
        snapshot = hierarchy.load()
        print(f"  Sources: {len(snapshot.sources)} file(s)")
        print(f"  Settings keys: {list(snapshot.settings.keys())}")

        # Step 2: Create agent with working_dir
        print("\n--- Step 2: Create Agent ---")
        mock_llm = Mock()
        mock_llm.model = "test-model"
        mock_llm.model_config = ModelConfig(
            model_name="test-model",
            context_window=100000,
            max_output_tokens=4000
        )
        mock_llm.count_tokens.return_value = 100
        mock_llm.count_tools_tokens.return_value = 50

        agent = SimpleAgent(
            session_id="test",
            llm=mock_llm,
            working_dir=tmpdir
        )
        print(f"  Agent working_dir: {agent.working_dir}")

        # Step 3: Create controller
        print("\n--- Step 3: Create AgentController ---")
        mock_broker = Mock(spec=MessageBroker)
        mock_context = Mock(spec=TopicContext)
        mock_context.client_topic = "client"
        mock_context.agent_topic = "agent"
        mock_context.runtime_topic = "runtime"

        controller = AgentController(
            agent=agent,
            broker=mock_broker,
            context=mock_context,
            working_dir=tmpdir
        )
        print(f"  Controller config_hierarchy: {type(controller.config_hierarchy).__name__}")
        print(f"  Preprocessor threshold: {controller.prompt_preprocessor.threshold}")
        print(f"  Preprocessor enabled: {controller.prompt_preprocessor.enabled}")

        # Verify end-to-end
        print("\n--- Verification ---")
        assert agent.working_dir == tmpdir, "Agent working_dir mismatch"
        assert controller.working_dir == tmpdir, "Controller working_dir mismatch"
        assert controller.prompt_preprocessor.threshold == 8.0, "Threshold mismatch"
        assert controller.prompt_preprocessor.enabled == True, "Enabled mismatch"

        print("  [PASS] ConfigHierarchy loaded successfully")
        print("  [PASS] Agent created with working_dir")
        print("  [PASS] Controller created with ConfigHierarchy")
        print("  [PASS] PromptPreprocessor configured from hierarchy")

        print("\n[PASS] End-to-end integration verified!")


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("  PHASE 3: AGENT INTEGRATION - MANUAL VERIFICATION")
    print("=" * 70)

    try:
        verify_prompt_preprocessor_integration()
        verify_agent_controller_integration()
        verify_base_agent_integration()
        verify_end_to_end_flow()

        print("\n" + "=" * 70)
        print("  ALL VERIFICATIONS PASSED!")
        print("=" * 70)
        print("\nPhase 3 Integration Summary:")
        print("  1. PromptPreprocessor - Accepts ConfigSnapshot for configuration")
        print("  2. AgentController - Creates and uses ConfigHierarchy")
        print("  3. BaseAgent - Accepts working_dir parameter")
        print("  4. End-to-End - Full config flow from files to agents")
        print()

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
