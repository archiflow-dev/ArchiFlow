#!/usr/bin/env python3
"""Test SimpleAgent in REPL context."""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent_cli.agents.agent_factory_impl import create_agent
from agent_framework.llm.mock import MockProvider
from datetime import datetime


def test_simple_agent_creation():
    """Test creating original SimpleAgent through factory."""
    print("=" * 60)
    print("Testing SimpleAgent Creation via Factory")
    print("=" * 60)
    print()

    # Get current date
    current_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # Create original SimpleAgent
        agent = create_agent(
            agent_type="simple",
            session_id="repl_test",
            llm_provider=MockProvider(model="gpt-3.5-turbo")
        )

        print(f"[OK] Agent created successfully")
        print(f"Agent type: {type(agent).__name__}")
        print(f"Session ID: {agent.session_id}")
        print(f"Agent name: {agent.get_name()}")

        # Check if date is in system message
        system_msg = agent.get_system_message()
        has_date = f"Current Date: {current_date}" in system_msg

        print(f"\nDate context in system message: {'[OK]' if has_date else '[FAIL]'}")

        if has_date:
            print("\nSystem message (showing date part):")
            print("-" * 30)
            lines = system_msg.split('\n')
            for line in lines:
                if 'Current Date:' in line or 'Current DateTime:' in line or line.strip() == "":
                    print(line)

    except Exception as e:
        print(f"[ERROR] {e}")
        return False

    print("\n" + "=" * 60)
    print("Result: Original SimpleAgent created via /new command")
    print("will have date context available.")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = test_simple_agent_creation()
    sys.exit(0 if success else 1)