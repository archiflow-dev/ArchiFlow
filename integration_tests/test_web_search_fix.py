#!/usr/bin/env python3
"""Test script to verify the web search tool fix."""

import asyncio
import sys
import os

# Add the src directory to the path (test is in integration_tests/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent_framework.tools.web_search_tool import WebSearchTool


async def test_web_search():
    """Test the web search tool with various queries."""
    print("=" * 60)
    print("Testing Web Search Tool Fix")
    print("=" * 60)
    print()

    # Create the web search tool
    tool = WebSearchTool()

    # Test queries
    test_queries = [
        "Python programming",
        "machine learning",
        "latest AI developments"
    ]

    for query in test_queries:
        print(f"\n{'-' * 40}")
        print(f"Searching for: {query}")
        print(f"{'-' * 40}")

        try:
            result = await tool.execute(query=query)

            if result.error:
                print(f"[ERROR] {result.error}")
            else:
                print(f"[SUCCESS] Search completed successfully")
                print(f"Provider: DuckDuckGo")
                print("\nResults:")
                print(result.output[:1000])  # Limit output to first 1000 chars

        except Exception as e:
            print(f"[FAIL] Unexpected error: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)


async def test_domain_filtering():
    """Test domain filtering functionality."""
    print("\n\nTesting Domain Filtering")
    print("-" * 40)

    tool = WebSearchTool()

    try:
        # Test with allowed domains
        print("\n1. Testing with allowed domains (wikipedia.org):")
        result = await tool.execute(
            query="artificial intelligence",
            allowed_domains=["wikipedia.org"]
        )
        if result.error:
            print(f"[ERROR] {result.error}")
        else:
            print(f"[SUCCESS] Found {result.output.count('URL:')} results")

        # Test with blocked domains
        print("\n2. Testing with blocked domains (example.com):")
        result = await tool.execute(
            query="test search",
            blocked_domains=["example.com"]
        )
        if result.error:
            print(f"[ERROR] {result.error}")
        else:
            print(f"[SUCCESS] Filtered search completed")

    except Exception as e:
        print(f"[FAIL] Domain filtering test failed: {e}")


async def test_empty_query():
    """Test error handling for empty queries."""
    print("\n\nTesting Empty Query Handling")
    print("-" * 40)

    tool = WebSearchTool()

    try:
        result = await tool.execute(query="")
        if result.error:
            print(f"[SUCCESS] Correctly handled empty query: {result.error}")
        else:
            print(f"[FAIL] Should have returned an error for empty query")
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")


async def main():
    """Run all web search tests."""
    await test_web_search()
    await test_domain_filtering()
    await test_empty_query()

    print("\n\nSummary:")
    print("- The web search tool now uses DuckDuckGo HTML parsing instead of the unreliable API")
    print("- BeautifulSoup4 is required for HTML parsing (will fall back gracefully if not installed)")
    print("- The tool includes proper error handling and domain filtering")
    print("\nTo install BeautifulSoup4: pip install beautifulsoup4")


if __name__ == "__main__":
    # Check if BeautifulSoup4 is available
    try:
        import bs4
        print("BeautifulSoup4 is available - full HTML parsing enabled")
    except ImportError:
        print("WARNING: BeautifulSoup4 not installed - falling back to limited functionality")
        print("To install: pip install beautifulsoup4")
        print()

    # Run the tests
    asyncio.run(main())