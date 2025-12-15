#!/usr/bin/env python3
"""Simple test for web search functionality."""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# First, let's check if we can import everything
try:
    import asyncio
    from agent_framework.tools.web_search_tool import WebSearchTool
    print("[OK] All imports successful")
except ImportError as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)

# Simple test function
async def simple_search_test():
    """Perform a simple search test."""
    tool = WebSearchTool()

    print("\nTesting simple search: 'Python programming'")
    print("-" * 50)

    try:
        result = await tool.execute(query="Python programming")

        if result.error:
            print(f"Error: {result.error}")
            return False
        else:
            # Show first 500 characters of output
            output_preview = result.output[:500] + "..." if len(result.output) > 500 else result.output
            print(f"Success! Results preview:")
            print(output_preview)
            return True

    except Exception as e:
        print(f"Exception occurred: {e}")
        return False

# Run the test
if __name__ == "__main__":
    print("Web Search Tool Simple Test")
    print("=" * 50)

    # Check for BeautifulSoup4
    try:
        import bs4
        print("BeautifulSoup4 is installed [OK]")
    except ImportError:
        print("WARNING: BeautifulSoup4 not installed - installing recommended")
        print("Run: pip install beautifulsoup4")
        print()

    # Run the test
    success = asyncio.run(simple_search_test())

    print("\n" + "=" * 50)
    if success:
        print("Test PASSED [OK]")
    else:
        print("Test FAILED [FAIL]")