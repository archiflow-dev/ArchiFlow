"""Web search tool for agents."""
import os
from typing import Dict, List, Optional
import httpx
from .tool_base import BaseTool, ToolResult


class SearchResult:
    """Represents a single search result."""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        source: Optional[str] = None
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source

    def __repr__(self):
        return f"SearchResult(title='{self.title}', url='{self.url}')"


class WebSearchTool(BaseTool):
    """Tool for searching the web.

    This tool performs web searches and returns formatted results.
    Supports domain filtering and multiple search providers.
    """

    name: str = "web_search"
    description: str = "Searches the web and returns formatted search results. Use this for accessing up-to-date information beyond the knowledge cutoff."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to use"
            },
            "allowed_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of domains to include (e.g., ['wikipedia.org', 'github.com'])"
            },
            "blocked_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of domains to exclude (e.g., ['example.com'])"
            }
        },
        "required": ["query"]
    }

    # Configuration
    timeout: int = 30
    max_results: int = 10

    def _filter_by_domain(
        self,
        results: List[SearchResult],
        allowed_domains: Optional[List[str]],
        blocked_domains: Optional[List[str]]
    ) -> List[SearchResult]:
        """Filter search results by domain.

        Args:
            results: List of search results
            allowed_domains: Domains to include (whitelist)
            blocked_domains: Domains to exclude (blacklist)

        Returns:
            Filtered list of search results
        """
        filtered_results = []

        for result in results:
            # Extract domain from URL
            try:
                from urllib.parse import urlparse
                parsed = urlparse(result.url)
                domain = parsed.netloc.lower()

                # Remove www. prefix for comparison
                if domain.startswith('www.'):
                    domain = domain[4:]

                # Check blocked domains
                if blocked_domains:
                    if any(domain == blocked.lower() or domain.endswith('.' + blocked.lower())
                           for blocked in blocked_domains):
                        continue

                # Check allowed domains
                if allowed_domains:
                    if not any(domain == allowed.lower() or domain.endswith('.' + allowed.lower())
                              for allowed in allowed_domains):
                        continue

                filtered_results.append(result)

            except Exception:
                # If we can't parse the URL, skip it
                continue

        return filtered_results

    async def _search_google(self, query: str, num_results: int) -> tuple[Optional[List[SearchResult]], Optional[str]]:
        """Search using Google Custom Search API.

        Args:
            query: The search query
            num_results: Number of results to return

        Returns:
            Tuple of (results_list, error_message)
        """
        api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

        if not api_key or not search_engine_id:
            return None, "Google Search requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID environment variables"

        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": api_key,
                "cx": search_engine_id,
                "q": query,
                "num": min(num_results, 10)  # Google allows max 10 per request
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    return None, f"Google Search API error: HTTP {response.status_code}"

                data = response.json()

                if "items" not in data:
                    return [], None  # No results found

                results = []
                for item in data["items"]:
                    result = SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        source="Google"
                    )
                    results.append(result)

                return results, None

        except httpx.TimeoutException:
            return None, "Search request timed out"
        except Exception as e:
            return None, f"Error performing Google search: {type(e).__name__}: {str(e)}"

    async def _search_duckduckgo(self, query: str, num_results: int) -> tuple[Optional[List[SearchResult]], Optional[str]]:
        """Search using DuckDuckGo HTML parsing.

        Args:
            query: The search query
            num_results: Number of results to return

        Returns:
            Tuple of (results_list, error_message)
        """
        try:
            # Use DuckDuckGo HTML version and parse results
            # This is more reliable than the API which returns test data
            url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            params = {
                "q": query,
                "kl": "us-en"
            }

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params, headers=headers)

                if response.status_code != 200:
                    return None, f"DuckDuckGo search error: HTTP {response.status_code}"

                # Parse HTML results
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                results = []

                # Find result divs
                result_divs = soup.find_all('div', class_='result')

                for div in result_divs[:num_results]:
                    # Extract title and link
                    title_tag = div.find('a', class_='result__a')
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    url = title_tag.get('href', '')

                    # Extract snippet
                    snippet_tag = div.find('a', class_='result__snippet')
                    if snippet_tag:
                        snippet = snippet_tag.get_text(strip=True)
                    else:
                        # Fallback to any text content
                        snippet_div = div.find('div', class_='result__body')
                        if snippet_div:
                            # Remove any script/style tags and get text
                            for script in snippet_div(["script", "style"]):
                                script.decompose()
                            snippet = snippet_div.get_text(strip=True)
                        else:
                            snippet = ""

                    # Clean up snippet
                    snippet = ' '.join(snippet.split())[:300]  # Limit to 300 chars

                    if title and url:
                        result = SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source="DuckDuckGo"
                        )
                        results.append(result)

                return results, None

        except ImportError:
            # Fallback to API method if bs4 is not available
            return await self._search_duckduckgo_api_fallback(query, num_results)
        except httpx.TimeoutException:
            return None, "Search request timed out"
        except Exception as e:
            return None, f"Error performing DuckDuckGo search: {type(e).__name__}: {str(e)}"

    async def _search_duckduckgo_api_fallback(self, query: str, num_results: int) -> tuple[Optional[List[SearchResult]], Optional[str]]:
        """Fallback method using DuckDuckGo API with better error handling."""
        try:
            # Use the vqd endpoint for more reliable results
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # First, get a VQD token
                vqd_url = "https://duckduckgo.com/"
                params = {"q": query}
                response = await client.get(vqd_url, params=params)

                if response.status_code != 200:
                    return None, f"DuckDuckGo vqd token error: HTTP {response.status_code}"

                # Extract VQD from HTML
                import re
                vqd_match = re.search(r'vqd=([\d-]+)', response.text)
                if not vqd_match:
                    return None, "Could not extract VQD token from DuckDuckGo"

                vqd = vqd_match.group(1)

                # Now perform the actual search
                search_url = "https://duckduckgo.com/html/"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                params = {
                    "q": query,
                    "vqd": vqd,
                    "kl": "us-en"
                }

                response = await client.get(search_url, params=params, headers=headers)

                if response.status_code != 200:
                    return None, f"DuckDuckGo search error: HTTP {response.status_code}"

                # Parse results from HTML
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                results = []
                result_divs = soup.find_all('div', class_='result')

                for div in result_divs[:num_results]:
                    title_tag = div.find('a', class_='result__a')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        url = title_tag.get('href', '')

                        snippet_tag = div.find('a', class_='result__snippet')
                        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                        if title and url:
                            result = SearchResult(
                                title=title,
                                url=url,
                                snippet=snippet,
                                source="DuckDuckGo"
                            )
                            results.append(result)

                return results, None

        except Exception as e:
            # Final fallback with a simple web search simulation
            return None, f"DuckDuckGo search failed: {str(e)}. Consider using a different search provider or installing BeautifulSoup4."

    async def _perform_search(
        self,
        query: str,
        num_results: int
    ) -> tuple[Optional[List[SearchResult]], Optional[str]]:
        """Perform web search using configured provider.

        Args:
            query: The search query
            num_results: Number of results to return

        Returns:
            Tuple of (results_list, error_message)
        """
        # Get search provider from environment
        provider = os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo").lower()

        if provider == "google":
            return await self._search_google(query, num_results)
        elif provider == "duckduckgo":
            return await self._search_duckduckgo(query, num_results)
        else:
            return None, f"Unknown search provider: {provider}. Use 'google' or 'duckduckgo'"

    def _format_results(self, results: List[SearchResult]) -> str:
        """Format search results for display.

        Args:
            results: List of search results

        Returns:
            Formatted string
        """
        if not results:
            return "No results found."

        lines = []
        lines.append(f"Found {len(results)} search result(s):")
        lines.append("=" * 80)

        for i, result in enumerate(results, 1):
            lines.append(f"\n{i}. {result.title}")
            lines.append(f"   URL: {result.url}")
            if result.snippet:
                # Truncate long snippets
                snippet = result.snippet[:300] + "..." if len(result.snippet) > 300 else result.snippet
                lines.append(f"   {snippet}")
            lines.append("")

        return "\n".join(lines)

    async def execute(
        self,
        query: str,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None
    ) -> ToolResult:
        """Perform a web search.

        Args:
            query: The search query
            allowed_domains: Optional list of domains to include
            blocked_domains: Optional list of domains to exclude

        Returns:
            ToolResult with formatted search results or error
        """
        try:
            # Validate query
            if not query or not query.strip():
                return ToolResult(
                    error="Search query cannot be empty"
                )

            # Perform search
            results, error = await self._perform_search(query, self.max_results)

            if error:
                return ToolResult(error=error)

            if not results:
                return ToolResult(
                    output="No results found for your query.",
                    system=f"Query: {query}"
                )

            # Filter by domain if specified
            if allowed_domains or blocked_domains:
                original_count = len(results)
                results = self._filter_by_domain(results, allowed_domains, blocked_domains)

                if not results:
                    return ToolResult(
                        output="No results found after domain filtering.",
                        system=f"Query: {query} | Filtered out {original_count} result(s)"
                    )

            # Format results
            output = self._format_results(results)

            # Build system message
            system_parts = [f"Query: {query}"]
            if allowed_domains:
                system_parts.append(f"Allowed domains: {', '.join(allowed_domains)}")
            if blocked_domains:
                system_parts.append(f"Blocked domains: {', '.join(blocked_domains)}")

            provider = os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo")
            system_parts.append(f"Provider: {provider.title()}")

            system_msg = " | ".join(system_parts)

            return ToolResult(output=output, system=system_msg)

        except Exception as e:
            return ToolResult(
                error=f"Error performing web search: {type(e).__name__}: {str(e)}"
            )
