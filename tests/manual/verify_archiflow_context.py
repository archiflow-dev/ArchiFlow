"""
Manual Verification Script for ARCHIFLOW.md Context Ingestion

This script demonstrates the new ARCHIFLOW.md context ingestion feature:
1. ProjectContextMessage type
2. BaseAgent context support with include_project_context parameter
3. ProjectAgent auto-enables context (default True)
4. Context is cached at init and can be manually reloaded
5. Context is injected as a separate message before first LLM call

Usage:
    python tests/manual/verify_archiflow_context.py
"""
import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def verify_project_context_message():
    """Verify ProjectContextMessage type exists and works."""
    print_header("1. ProjectContextMessage Type")

    from agent_framework.messages.types import ProjectContextMessage

    msg = ProjectContextMessage(
        session_id="test",
        sequence=1,  # Sequence 1 = position 1, after system prompt (sequence 0)
        context="# Test Context\n\nThis is test content.",
        sources=["./.archiflow/ARCHIFLOW.md", "~/.archiflow/ARCHIFLOW.md"]
    )

    print(f"Created ProjectContextMessage:")
    print(f"  type: {msg.type}")
    print(f"  session_id: {msg.session_id}")
    print(f"  sequence: {msg.sequence}")
    print(f"  context: {msg.context[:50]}...")
    print(f"  sources: {msg.sources}")
    print(f"  source: {msg.source}")

    assert msg.type == "ProjectContextMessage"
    assert msg.source == "archiflow"
    assert len(msg.sources) == 2

    print("\n[PASS] ProjectContextMessage type works!")


def verify_baseagent_context_loading():
    """Verify BaseAgent loads ARCHIFLOW.md context when enabled."""
    print_header("2. BaseAgent Context Loading")

    from agent_framework.agents.base import SimpleAgent
    from agent_framework.llm.provider import LLMProvider, FinishReason, LLMResponse
    from agent_framework.messages.types import UserMessage, ProjectContextMessage, SystemMessage

    # Create mock LLM
    class MockLLM(LLMProvider):
        def __init__(self):
            super().__init__("mock")
            self.call_count = 0
        def generate(self, messages, tools=None, **kwargs):
            self.call_count += 1
            return LLMResponse(content="Response", finish_reason=FinishReason.STOP, usage={})
        def stream(self, messages, tools=None, **kwargs):
            raise NotImplementedError()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archiflow_dir = tmpdir / ".archiflow"
        archiflow_dir.mkdir(parents=True)

        # Create ARCHIFLOW.md
        context_content = """# Project Configuration

## Coding Standards
- Use PEP 8
- Max line length: 100

## Commands
- Run tests: pytest
"""
        (archiflow_dir / "ARCHIFLOW.md").write_text(context_content)

        print(f"Created: {archiflow_dir / 'ARCHIFLOW.md'}")
        print(f"Content:\n{context_content}")

        # Create agent WITH context
        llm = MockLLM()
        agent = SimpleAgent(
            session_id="test",
            llm=llm,
            include_project_context=True,
            working_dir=tmpdir
        )

        print(f"\nAgent created with include_project_context=True")
        print(f"  _project_context_msg: {agent._project_context_msg is not None}")
        print(f"  _context_injected: {agent._context_injected}")
        print(f"  Context length: {len(agent._project_context_msg.context) if agent._project_context_msg else 0}")

        if agent._project_context_msg:
            print(f"  Context sources: {agent._project_context_msg.sources}")

        # Send first message to trigger context injection
        user_msg = UserMessage(session_id="test", sequence=1, content="Hello")
        agent.step(user_msg)

        print(f"\nAfter first step():")
        print(f"  _context_injected: {agent._context_injected}")

        # Check if context is in history
        has_context = any(isinstance(m, ProjectContextMessage) for m in agent.history.get_messages())
        print(f"  ProjectContextMessage in history: {has_context}")

        # Verify position: context should be at index 1 (after system prompt at index 0)
        messages = agent.history.get_messages()
        print(f"  Message order:")
        for i, msg in enumerate(messages):
            print(f"    [{i}] {msg.type}")

        # Position verification
        assert len(messages) >= 2, "Should have at least system message and context"
        assert isinstance(messages[0], SystemMessage), "First message should be SystemMessage"
        assert isinstance(messages[1], ProjectContextMessage), "Second message should be ProjectContextMessage"
        assert isinstance(messages[2], UserMessage), "Third message should be UserMessage"

        assert agent._project_context_msg is not None, "Context should be loaded"
        assert agent._context_injected, "Context should be injected"
        assert has_context, "Context message should be in history"

        print("\n[PASS] BaseAgent context loading works!")


def verify_baseagent_context_disabled():
    """Verify BaseAgent doesn't load context when disabled."""
    print_header("3. BaseAgent Context Disabled (default)")

    from agent_framework.agents.base import SimpleAgent
    from agent_framework.llm.provider import LLMProvider, FinishReason, LLMResponse
    from agent_framework.messages.types import ProjectContextMessage

    # Create mock LLM
    class MockLLM(LLMProvider):
        def __init__(self):
            super().__init__("mock")
            self.call_count = 0
        def generate(self, messages, tools=None, **kwargs):
            self.call_count += 1
            return LLMResponse(content="Response", finish_reason=FinishReason.STOP, usage={})
        def stream(self, messages, tools=None, **kwargs):
            raise NotImplementedError()

    # Create agent WITHOUT context (default)
    llm = MockLLM()
    agent = SimpleAgent(session_id="test", llm=llm)

    print(f"Agent created with default include_project_context=False")
    print(f"  include_project_context: {agent.include_project_context}")
    print(f"  _project_context_msg: {agent._project_context_msg}")

    assert not agent.include_project_context
    assert agent._project_context_msg is None

    print("\n[PASS] BaseAgent context disabled by default!")


def verify_reload_project_context():
    """Verify reload_project_context() method works."""
    print_header("4. Reload Project Context")

    from agent_framework.agents.base import SimpleAgent
    from agent_framework.llm.provider import LLMProvider, FinishReason, LLMResponse
    from agent_framework.messages.types import UserMessage

    # Create mock LLM
    class MockLLM(LLMProvider):
        def __init__(self):
            super().__init__("mock")
            self.call_count = 0
        def generate(self, messages, tools=None, **kwargs):
            self.call_count += 1
            return LLMResponse(content="Response", finish_reason=FinishReason.STOP, usage={})
        def stream(self, messages, tools=None, **kwargs):
            raise NotImplementedError()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archiflow_dir = tmpdir / ".archiflow"
        archiflow_dir.mkdir(parents=True)

        # Create initial ARCHIFLOW.md
        (archiflow_dir / "ARCHIFLOW.md").write_text("# Initial Context")

        # Create agent with context
        llm = MockLLM()
        agent = SimpleAgent(
            session_id="test",
            llm=llm,
            include_project_context=True,
            working_dir=tmpdir
        )

        initial_context = agent._project_context_msg.context
        print(f"Initial context: {initial_context[:50]}...")

        # Update ARCHIFLOW.md
        (archiflow_dir / "ARCHIFLOW.md").write_text("# Updated Context\n\nThis is new content.")

        # Reload
        agent.reload_project_context()

        updated_context = agent._project_context_msg.context
        print(f"Updated context: {updated_context[:50]}...")

        assert initial_context != updated_context
        assert "Updated Context" in updated_context

        print("\n[PASS] reload_project_context() works!")


def verify_projectagent_auto_enable():
    """Verify ProjectAgent auto-enables context."""
    print_header("5. ProjectAgent Auto-Enable")

    from agent_framework.agents.coding_agent import CodingAgent
    from agent_framework.llm.provider import LLMProvider, FinishReason, LLMResponse

    # Create mock LLM
    class MockLLM(LLMProvider):
        def __init__(self):
            super().__init__("mock")
            self.call_count = 0
        def generate(self, messages, tools=None, **kwargs):
            self.call_count += 1
            return LLMResponse(content="Response", finish_reason=FinishReason.STOP, usage={})
        def stream(self, messages, tools=None, **kwargs):
            raise NotImplementedError()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archiflow_dir = tmpdir / ".archiflow"
        archiflow_dir.mkdir(parents=True)

        # Create ARCHIFLOW.md
        (archiflow_dir / "ARCHIFLOW.md").write_text("# Project Standards\n\n- PEP 8\n- Type hints required")

        # Create ProjectAgent (CodingAgent)
        llm = MockLLM()
        agent = CodingAgent(
            session_id="test",
            llm=llm,
            project_directory=str(tmpdir)
        )

        print(f"CodingAgent created")
        print(f"  include_project_context: {agent.include_project_context}")
        print(f"  _project_context_msg: {agent._project_context_msg is not None}")

        assert agent.include_project_context, "ProjectAgent should auto-enable context"

        print("\n[PASS] ProjectAgent auto-enables context!")


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("  ARCHIFLOW.md CONTEXT INGESTION - MANUAL VERIFICATION")
    print("=" * 70)

    try:
        verify_project_context_message()
        verify_baseagent_context_loading()
        verify_baseagent_context_disabled()
        verify_reload_project_context()
        verify_projectagent_auto_enable()

        print("\n" + "=" * 70)
        print("  ALL VERIFICATIONS PASSED!")
        print("=" * 70)
        print("\nFeature Summary:")
        print("  1. ProjectContextMessage - New message type for ARCHIFLOW.md context")
        print("  2. BaseAgent - Optional include_project_context parameter (default False)")
        print("  3. ProjectAgent - Auto-enables context (default True)")
        print("  4. Context - Cached at init, can be manually reloaded")
        print("  5. Injection - Separate message before first LLM call")
        print()

    except Exception as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
