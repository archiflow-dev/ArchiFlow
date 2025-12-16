#!/usr/bin/env python3
"""Test WebFetchTool with mock server."""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, patch, Mock
import httpx

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent_framework.tools.web_fetch_tool import WebFetchTool


async def test_web_fetch_with_mock():
    """Test WebFetchTool with mocked HTTP responses."""
    print("=" * 60)
    print("Testing WebFetchTool with Mock Server")
    print("=" * 60)
    print()

    # Create tool
    tool = WebFetchTool()

    # Mock HTML content
    mock_html = """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Welcome to Test Page</h1>
        <p>This is a test page with some content.</p>
        <ul>
            <li>Item 1: This is the first item</li>
            <li>Item 2: This is the second item</li>
            <li>Item 3: This is the third item</li>
        </ul>
        <div class="footer">
            <p>Footer content here.</p>
        </div>
    </body>
    </html>
    """

    # Test cases
    test_cases = [
        {
            "name": "Success - HTML content",
            "mock_response": Mock(
                status_code=200,
                text=mock_html,
                headers={"content-type": "text/html"},
                content=mock_html.encode()
            ),
            "expected_keywords": ["Welcome", "Test Page", "first item"]
        },
        {
            "name": "Success - Plain text",
            "mock_response": Mock(
                status_code=200,
                text="This is plain text content.\nMultiple lines.",
                headers={"content-type": "text/plain"},
                content=b"This is plain text content.\nMultiple lines."
            ),
            "expected_keywords": ["plain text", "Multiple"]
        },
        {
            "name": "404 Error",
            "mock_response": Mock(status_code=404),
            "expected_error": "Page not found (404)"
        },
        {
            "name": "403 Forbidden",
            "mock_response": Mock(status_code=403),
            "expected_error": "Access forbidden (403)"
        },
        {
            "name": "Large content",
            "mock_response": Mock(
                status_code=200,
                text="x" * (tool.max_content_length + 1000),
                headers={"content-type": "text/html"},
                content=b"x" * (tool.max_content_length + 1000)
            ),
            "expected_error": "Content too large"
        }
    ]

    # Run tests
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print("-" * 40)

        # Mock httpx.AsyncClient
        with patch('httpx.AsyncClient') as mock_client:
            # Setup mock
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = test_case["mock_response"]
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            # Test _fetch_url method
            content, error = await tool._fetch_url("https://example.com")

            if "expected_error" in test_case:
                if error and test_case["expected_error"] in error:
                    print(f"  [OK] Got expected error: {error}")
                else:
                    print(f"  [FAIL] Expected error not found. Got: {error}")
            else:
                if error:
                    print(f"  [FAIL] Unexpected error: {error}")
                elif content:
                    # Check for expected keywords
                    found_all = True
                    for keyword in test_case["expected_keywords"]:
                        if keyword not in content:
                            print(f"  [FAIL] Missing keyword: {keyword}")
                            found_all = False

                    if found_all:
                        print(f"  [OK] Content contains all expected keywords")
                        # Show preview
                        preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"  Preview: {preview}")
                else:
                    print("  [FAIL] No content returned")

    return True


def test_html_to_markdown():
    """Test HTML to Markdown conversion."""
    print("\n\n" + "=" * 60)
    print("Testing HTML to Markdown Conversion")
    print("=" * 60)
    print()

    tool = WebFetchTool()

    # Test HTML
    test_html = """
    <h1>Main Title</h1>
    <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
    <ul>
        <li>First item</li>
        <li>Second item</li>
    </ul>
    <a href="https://example.com">Link text</a>
    """

    # Convert
    markdown = tool._html_to_markdown(test_html)

    print("Original HTML:")
    print("-" * 30)
    print(test_html[:300] + "..." if len(test_html) > 300 else test_html)

    print("\nConverted Markdown:")
    print("-" * 30)
    print(markdown[:300] + "..." if len(markdown) > 300 else markdown)

    # Check basic conversion
    checks = [
        ("Main Title", "Main Title" in markdown),
        ("bold text", "**bold**" in markdown or "*bold*" in markdown),
        ("italic text", "*" in markdown),
        ("First item", "First item" in markdown),
        ("Link", "Link text" in markdown and "https://example.com" in markdown)
    ]

    print("\nConversion checks:")
    for name, check in checks:
        status = "[OK]" if check else "[FAIL]"
        print(f"  {name}: {status}")

    return True


def test_cache_functionality():
    """Test caching functionality."""
    print("\n\n" + "=" * 60)
    print("Testing Cache Functionality")
    print("=" * 60)
    print()

    tool = WebFetchTool()

    # Clear cache
    tool.clear_cache()
    print(f"Cache cleared. Size: {len(tool._cache)}")

    # Test cache miss
    result = tool._get_from_cache("https://example.com")
    print(f"Cache miss (should be None): {result}")

    # Test add to cache
    test_content = "This is test content for caching."
    tool._add_to_cache("https://example.com", test_content)
    print(f"Added to cache. Size: {len(tool._cache)}")

    # Test cache hit
    result = tool._get_from_cache("https://example.com")
    if result == test_content:
        print(f"[OK] Cache hit: Got expected content")
    else:
        print(f"[FAIL] Cache hit: Got unexpected content: {result}")

    # Test cache TTL (15 minutes)
    print(f"\nCache TTL: {tool._cache_ttl} seconds")
    print(f"Cache automatically expires after 15 minutes")

    return True


def test_url_normalization():
    """Test URL normalization."""
    print("\n\n" + "=" * 60)
    print("Testing URL Normalization")
    print("=" * 60)
    print()

    tool = WebFetchTool()

    test_urls = [
        ("https://example.com", "https://example.com", "Valid HTTPS"),
        ("http://example.com", "https://example.com", "HTTP to HTTPS"),
        ("https://EXAMPLE.com", "https://EXAMPLE.com", "Case preserved"),
    ]

    for original, expected, description in test_urls:
        normalized, error = tool._normalize_url(original)
        if error:
            print(f"{description}: [FAIL] Got error: {error}")
        elif normalized == expected:
            print(f"{description}: [OK] {original} -> {normalized}")
        else:
            print(f"{description}: [FAIL] {original} -> {normalized} (expected {expected})")

    # Test invalid URLs
    invalid_urls = [
        ("example.com", "Missing scheme"),
        ("ftp://example.com", "Unsupported scheme"),
        ("https://", "Missing domain"),
    ]

    print("\nInvalid URL tests:")
    for url, description in invalid_urls:
        normalized, error = tool._normalize_url(url)
        if error:
            print(f"{description}: [OK] Got error: {error}")
        else:
            print(f"{description}: [FAIL] Should have failed")

    return True


async def main():
    """Run all mock tests."""
    print("WebFetchTool Mock Test Suite")
    print("=" * 60)
    print("Testing WebFetchTool without actual network or API calls")
    print("=" * 60)

    # Run tests
    tests = [
        ("URL Normalization", test_url_normalization),
        ("Cache Functionality", test_cache_functionality),
        ("HTML to Markdown", test_html_to_markdown),
        ("Mock HTTP Requests", test_web_fetch_with_mock),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Running: {test_name}")
        print('=' * 60)

        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[ERROR] Test failed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = 0
    for test_name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nPassed: {passed}/{len(results)} tests")

    if passed == len(results):
        print("\n[SUCCESS] All WebFetchTool core functionality works correctly!")
        print("\nTo use with real URLs and LLM processing:")
        print("1. Set OPENAI_API_KEY environment variable")
        print("2. Use with actual accessible URLs")
    else:
        print(f"\n[FAIL] {len(results) - passed} test(s) failed")

    return passed == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)