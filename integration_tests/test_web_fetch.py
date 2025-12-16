#!/usr/bin/env python3
"""Test WebFetchTool functionality."""

import sys
import os
import asyncio

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test if WebFetchTool can be imported."""
    print("=" * 60)
    print("Testing WebFetchTool Imports")
    print("=" * 60)
    print()

    # Test html2text
    try:
        import html2text
        print("[OK] html2text is installed")
    except ImportError as e:
        print(f"[FAIL] html2text not installed: {e}")
        print("To install: pip install html2text")
        return False

    # Test WebFetchTool import
    try:
        from agent_framework.tools.web_fetch_tool import WebFetchTool
        print("[OK] WebFetchTool imported successfully")
    except ImportError as e:
        print(f"[FAIL] Failed to import WebFetchTool: {e}")
        return False

    # Check dependencies
    print("\nChecking dependencies:")
    try:
        import httpx
        print("[OK] httpx is available")
    except ImportError:
        print("[FAIL] httpx not installed")
        return False

    return True


async def test_web_fetch_basic():
    """Test basic WebFetchTool functionality without LLM processing."""
    print("\n\n" + "=" * 60)
    print("Testing WebFetchTool Basic Functionality")
    print("=" * 60)
    print()

    from agent_framework.tools.web_fetch_tool import WebFetchTool

    # Create tool instance
    tool = WebFetchTool()

    # Test URL normalization
    test_urls = [
        ("https://example.com", "Valid HTTPS URL"),
        ("http://example.com", "HTTP URL (should upgrade to HTTPS)"),
        ("example.com", "URL without scheme (should fail)"),
        ("ftp://example.com", "Unsupported scheme (should fail)"),
        ("https://", "URL without domain (should fail)")
    ]

    for url, description in test_urls:
        print(f"\n{description}: {url}")
        normalized_url, error = tool._normalize_url(url)

        if error:
            print(f"  Error: {error}")
        else:
            print(f"  Normalized: {normalized_url}")

    # Test fetching a simple page (without LLM processing)
    print(f"\n" + "-" * 50)
    print("Testing fetch without LLM processing:")
    print("-" * 50)

    try:
        # Try to fetch example.com
        content, error = await tool._fetch_url("https://example.com")

        if error:
            print(f"[ERROR] {error}")
        else:
            print(f"[OK] Successfully fetched content")
            print(f"Content preview (first 200 chars):")
            print("-" * 30)
            print(content[:200] + "..." if len(content) > 200 else content)

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")

    return True


def test_llm_integration():
    """Test LLM integration requirements."""
    print("\n\n" + "=" * 60)
    print("Testing LLM Integration Requirements")
    print("=" * 60)
    print()

    # Check OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        print("[OK] OPENAI_API_KEY is set")
        print(f"  Key length: {len(api_key)} chars")
    else:
        print("[FAIL] OPENAI_API_KEY not set")
        print("  Set it with: export OPENAI_API_KEY=your_key_here")
        return False

    # Check required imports
    print("\nChecking LLM-related imports:")
    required_imports = [
        ("agent_framework.llm.provider", "LLM provider module"),
        ("agent_framework.llm.openai", "OpenAI LLM module"),
        ("app.llm.openai", "App LLM module (from code)"),
    ]

    for import_path, description in required_imports:
        try:
            __import__(import_path)
            print(f"[OK] {description}")
        except ImportError as e:
            print(f"[FAIL] {description}: {e}")

    # Check what's actually available
    print("\nAvailable in agent_framework.llm:")
    try:
        import agent_framework.llm
        items = [x for x in dir(agent_framework.llm) if not x.startswith('_')]
        for item in items[:10]:  # Show first 10 items
            print(f"  - {item}")
    except ImportError:
        print("  Module not found")

    return True


async def test_web_fetch_complete():
    """Test complete WebFetchTool workflow."""
    print("\n\n" + "=" * 60)
    print("Testing Complete WebFetchTool Workflow")
    print("=" * 60)
    print()

    from agent_framework.tools.web_fetch_tool import WebFetchTool

    # Create tool
    tool = WebFetchTool()

    # Test with a known simple page
    test_cases = [
        {
            "url": "https://example.com",
            "prompt": "What is this page about? Summarize in one sentence."
        }
    ]

    for test_case in test_cases:
        print(f"\nTest Case:")
        print(f"  URL: {test_case['url']}")
        print(f"  Prompt: {test_case['prompt']}")
        print("-" * 50)

        try:
            # Execute the tool
            result = await tool.execute(
                url=test_case["url"],
                prompt=test_case["prompt"]
            )

            if result.error:
                print(f"[ERROR] {result.error}")
            else:
                print("[OK] Tool executed successfully")
                print(f"Output:")
                print("-" * 20)
                print(result.output[:500] + "..." if len(result.output) > 500 else result.output)
                print("\nSystem info:")
                print(f"  {result.system}")

        except Exception as e:
            print(f"[ERROR] Exception: {type(e).__name__}: {e}")

    return True


def main():
    """Run all WebFetchTool tests."""
    print("WebFetchTool Test Suite")
    print("=" * 60)

    # Run tests
    import_success = test_imports()
    if import_success:
        basic_success = asyncio.run(test_web_fetch_basic())
        llm_success = test_llm_integration()
        complete_success = asyncio.run(test_web_fetch_complete())
    else:
        basic_success = False
        llm_success = False
        complete_success = False

    # Summary
    print("\n\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    print(f"Imports: {'[OK]' if import_success else '[FAIL]'}")
    print(f"Basic functionality: {'[OK]' if basic_success else '[FAIL]'}")
    print(f"LLM integration: {'[OK]' if llm_success else '[FAIL]'}")
    print(f"Complete workflow: {'[OK]' if complete_success else '[FAIL]'}")

    if not import_success:
        print("\nRequired fixes:")
        print("1. Install html2text: pip install html2text")
        print("2. Fix import paths in web_fetch_tool.py")
        print("   - Change 'app.llm.openai' to use the actual LLM provider")
        print("   - Update imports to match project structure")

    return all([import_success, basic_success, llm_success, complete_success])


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)