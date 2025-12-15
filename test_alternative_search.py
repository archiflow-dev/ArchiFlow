#!/usr/bin/env python3
"""Test the alternative web search tool."""

import sys
import os
import asyncio

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent_framework.tools.web_search_tool_v2 import WebSearchToolV2


async def test_alternative_search():
    """Test the alternative web search tool."""
    print("=" * 60)
    print("Testing Alternative Web Search Tool")
    print("=" * 60)
    print()

    # Create the search tool
    tool = WebSearchToolV2()

    # Test queries
    test_cases = [
        "Python programming",
        "machine learning basics",
        "what is artificial intelligence",
        "test query with no results"
    ]

    for query in test_cases:
        print(f"\n{'-' * 50}")
        print(f"Query: {query}")
        print(f"{'-' * 50}")

        try:
            result = await tool.execute(query=query, num_results=3)

            if result.error:
                print(f"[INFO] Note: {result.error}")

            # Display results
            print("\nResults:")
            print(result.output[:800])  # Limit output

            # Show system info
            print(f"\nSystem Info:")
            print(f"  {result.system}")

        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("Test Summary:")
    print("- The tool tries multiple search providers (Brave, SearX)")
    print("- If all fail, it provides fallback results")
    print("- No API key is required for basic functionality")
    print("- For Brave Search, set BRAVE_SEARCH_API_KEY environment variable")
    print("=" * 60)


if __name__ == "__main__":
    # Check for optional dependencies
    try:
        import httpx
        print("[OK] httpx is installed")
    except ImportError:
        print("[FAIL] httpx is required - run: pip install httpx")
        sys.exit(1)

    # Run the test
    asyncio.run(test_alternative_search())