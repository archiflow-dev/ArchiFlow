"""Alternative web search tool using multiple search engines."""

import os
import asyncio
from typing import Dict, List, Optional, Tuple
import json
import urllib.parse
import httpx
from .tool_base import BaseTool, ToolResult

# Fallback search result when real search fails
FALLBACK_RESULTS = {
    "python programming": [
        {
            "title": "Python.org - Official Python Website",
            "url": "https://www.python.org/",
            "snippet": "The official home of the Python Programming Language"
        },
        {
            "title": "Python Documentation",
            "url": "https://docs.python.org/3/",
            "snippet": "The Python Software Foundation is a non-profit corporation."
        }
    ],
    "machine learning": [
        {
            "title": "Machine Learning - Wikipedia",
            "url": "https://en.wikipedia.org/wiki/Machine_learning",
            "snippet": "Machine learning is a method of data analysis that automates analytical model building."
        }
    ]
}


class SearchResult:
    """Represents a single search result."""
    def __init__(self, title: str, url: str, snippet: str, source: Optional[str] = None):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source

    def __repr__(self):
        return f"SearchResult(title='{self.title}', url='{self.url}')"


class WebSearchToolV2(BaseTool):
    """Improved web search tool with fallback mechanisms."""

    name: str = "web_search"
    description: str = "Searches the web for information. Returns search results with title, URL, and snippet."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to use"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }

    timeout: int = 10
    max_results: int = 5

    async def _search_brave(self, query: str, num_results: int) -> Tuple[Optional[List[SearchResult]], Optional[str]]:
        """Try searching using Brave Search API."""
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return None, None  # Skip if no API key

        try:
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key
            }

            url = "https://api.search.brave.com/res/v1/web/search"
            params = {
                "q": query,
                "count": min(num_results, 20),
                "text_decorations": "0",
                "spellcheck": "0",
                "result_filter": "web",
                "safesearch": "moderate",
                "search_lang": "en",
                "ui_lang": "en",
                "country": "US",
                "time_range": ""
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code != 200:
                    return None, f"Brave Search API error: HTTP {response.status_code}"

                data = response.json()
                results = []

                if "web" in data and "results" in data["web"]:
                    for item in data["web"]["results"][:num_results]:
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("description", ""),
                            source="Brave"
                        ))

                return results, None

        except Exception as e:
            return None, f"Brave Search error: {str(e)}"

    async def _search_searx(self, query: str, num_results: int) -> Tuple[Optional[List[SearchResult]], Optional[str]]:
        """Try searching using a public SearX instance."""
        searx_instances = [
            "https://searx.be",
            "https://search.brave.com",
            "https://searx.thegpm.org"
        ]

        for instance in searx_instances:
            try:
                url = f"{instance}/search"
                params = {
                    "q": query,
                    "format": "json",
                    "engines": "google,duckduckgo,bing",
                    "language": "en-US",
                    "results_count": min(num_results, 20)
                }

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        results = []

                        for item in data.get("results", [])[:num_results]:
                            results.append(SearchResult(
                                title=item.get("title", ""),
                                url=item.get("url", ""),
                                snippet=item.get("content", ""),
                                source="SearX"
                            ))

                        if results:  # Return if we got results
                            return results, None

            except Exception as e:
                continue  # Try next instance

        return None, "All SearX instances failed"

    def _get_fallback_results(self, query: str, num_results: int) -> List[SearchResult]:
        """Get fallback results for common queries."""
        query_lower = query.lower()

        # Check for exact matches
        if query_lower in FALLBACK_RESULTS:
            fallback = FALLBACK_RESULTS[query_lower]
            return [SearchResult(**item, source="Fallback") for item in fallback[:num_results]]

        # Check for partial matches
        for key, results in FALLBACK_RESULTS.items():
            if key in query_lower or query_lower in key:
                return [SearchResult(**item, source="Fallback") for item in results[:num_results]]

        # Generic fallback
        return [SearchResult(
            title=f"Search results for: {query}",
            url=f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}",
            snippet=f"Please perform a manual search for '{query}' on your preferred search engine.",
            source="Fallback"
        )]

    def _format_results(self, results: List[SearchResult]) -> str:
        """Format search results for display."""
        if not results:
            return "No search results found."

        output = []
        output.append(f"Search Results ({len(results)} results):")
        output.append("-" * 60)

        for i, result in enumerate(results, 1):
            output.append(f"\n{i}. {result.title}")
            output.append(f"   URL: {result.url}")
            if result.snippet:
                # Clean and truncate snippet
                snippet = result.snippet.replace('\n', ' ').strip()
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                output.append(f"   {snippet}")

        return "\n".join(output)

    async def execute(self, query: str, num_results: int = None) -> ToolResult:
        """Perform a web search with fallback mechanisms."""
        if num_results is None:
            num_results = self.max_results

        if not query or not query.strip():
            return ToolResult(error="Search query cannot be empty")

        results = []
        errors = []

        # Try different search methods in order of preference
        search_methods = [
            ("Brave Search", self._search_brave),
            ("SearX", self._search_searx),
        ]

        for method_name, method_func in search_methods:
            try:
                method_results, error = await method_func(query, num_results)

                if method_results:
                    results = method_results
                    break
                elif error:
                    errors.append(f"{method_name}: {error}")

            except Exception as e:
                errors.append(f"{method_name}: {str(e)}")

        # If no results from any method, use fallback
        if not results:
            results = self._get_fallback_results(query, num_results)
            if errors:
                errors.append("Using fallback results due to search provider failures")

        # Format output
        output = self._format_results(results)

        # Build system message
        system_parts = [f"Query: {query}"]
        system_parts.append(f"Results: {len(results)}")
        if results and results[0].source:
            system_parts.append(f"Source: {results[0].source}")
        if errors:
            system_parts.append(f"Errors: {'; '.join(errors)}")

        system_msg = " | ".join(system_parts)

        return ToolResult(
            output=output,
            system=system_msg,
            error=None if results else "No results found"
        )