#!/usr/bin/env python3
"""
Test script to verify SimpleAgent v2 integration.
"""

import sys
import os

# Add the src directory to the path (test is now in integration_tests/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_framework.agents.simple_agent_v2 import SimpleAgent
from agent_framework.llm.mock import MockProvider
from agent_cli.agents.agent_factory_impl import create_agent
from agent_cli.agents.factory import AgentType


def test_simplev2_creation():
    """Test creating SimpleAgent v2 through the factory."""
    print("Testing SimpleAgent v2 creation through factory...")

    # Create a mock LLM provider
    llm = MockProvider(model="gpt-3.5-turbo")

    # Test with default profile
    agent = create_agent(
        agent_type="simplev2",
        session_id="test_session_1",
        llm_provider=llm
    )

    print(f"[OK] Created agent with type: {type(agent).__name__}")
    print(f"[OK] Profile: {agent.profile_name}")
    print(f"[OK] Session ID: {agent.session_id}")
    print(f"[OK] Tools: {len(agent.tools.list_tools())}")
    print()

    # Test with custom profile
    agent2 = create_agent(
        agent_type="simplev2",
        session_id="test_session_2",
        llm_provider=llm,
        profile="analyst"
    )

    print(f"[OK] Created analyst agent with profile: {agent2.profile_name}")
    print(f"[OK] Capabilities: {', '.join(agent2.get_capabilities())}")
    print()

    # Test with custom prompt
    custom_prompt = "You are a creative writing assistant."
    agent3 = create_agent(
        agent_type="simplev2",
        session_id="test_session_3",
        llm_provider=llm,
        profile="custom",
        custom_prompt=custom_prompt
    )

    print(f"[OK] Created custom agent with prompt: {agent3.system_prompt[:50]}...")
    print()

    return True


def test_profile_list():
    """Test listing available profiles."""
    print("Testing profile listing...")

    from agent_framework.agents.profiles import list_profiles, get_profile

    profiles = list_profiles()
    print(f"[OK] Available profiles: {', '.join(profiles)}")

    # Test getting profile details
    for profile_name in profiles[:3]:  # Test first 3 profiles
        profile = get_profile(profile_name)
        print(f"[OK] Profile '{profile_name}': {profile.description}")
        print(f"  - Capabilities: {', '.join(profile.capabilities)}")

    print()
    return True


def test_message_handling():
    """Test that SimpleAgent v2 can handle messages."""
    print("Testing message handling...")

    from agent_framework.messages.types import UserMessage

    llm = MockProvider(model="gpt-3.5-turbo")

    # Create an agent
    agent = create_agent(
        agent_type="simplev2",
        session_id="test_msg",
        llm_provider=llm,
        profile="general"
    )

    # Send a message
    message = UserMessage(
        session_id="test_msg",
        sequence=1,
        content="Hello, SimpleAgent v2!"
    )

    response = agent.step(message)

    if response:
        print(f"[OK] Agent responded: {response.content[:50]}...")
        return True
    else:
        print("[FAIL] No response from agent")
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("SimpleAgent v2 Integration Tests")
    print("=" * 60)
    print()

    tests = [
        ("Profile Listing", test_profile_list),
        ("Agent Creation", test_simplev2_creation),
        ("Message Handling", test_message_handling),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            print(f"Running {test_name}...")
            result = test_func()
            results.append((test_name, result))
            print(f"{'[PASS]' if result else '[FAIL]'} {test_name}: {'PASSED' if result else 'FAILED'}")
            print("-" * 40)
        except Exception as e:
            print(f"[FAIL] {test_name}: FAILED with error: {e}")
            results.append((test_name, False))
            print("-" * 40)

    # Summary
    print("\nTest Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! SimpleAgent v2 is ready for use.")
        print("\nUsage examples:")
        print("  /new simplev2 --profile general")
        print("  /new simplev2 --profile analyst")
        print("  /new simplev2 --profile custom --prompt 'You are a creative writer'")
        print("  /profiles  # List all available profiles")
    else:
        print("\n[ERROR] Some tests failed. Please check the errors above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)