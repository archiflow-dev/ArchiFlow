"""Web fetching tool for agents."""
import os
import time
from typing import Dict, Optional, ClassVar
from urllib.parse import urlparse, urlunparse
import httpx
import html2text
from .tool_base import BaseTool, ToolResult
from ..config.env_loader import load_env


class WebFetchTool(BaseTool):
    """Tool for fetching and processing web content.

    This tool fetches content from URLs, converts HTML to markdown,
    and processes it using an AI model with a custom prompt.
    Includes a 15-minute cache for efficiency.
    """

    name: str = "web_fetch"
    description: str = "Fetches content from a URL, converts HTML to markdown, and processes it with an AI model using your prompt. Returns the AI model's response about the content."

    parameters: Dict = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch content from (must be a fully-formed valid URL)"
            },
            "prompt": {
                "type": "string",
                "description": "The prompt describing what information you want to extract from the page"
            }
        },
        "required": ["url", "prompt"]
    }

    # Class-level cache: {url: (content, timestamp)}
    _cache: ClassVar[Dict[str, tuple[str, float]]] = {}
    _cache_ttl: ClassVar[int] = 900  # 15 minutes in seconds

    # HTTP client settings
    timeout: int = 30
    max_content_length: int = 5_000_000  # 5MB
    follow_redirects: bool = True
    user_agent: str = "GPT-Agent-Framework/1.0 (WebFetch Tool)"

    @classmethod
    def _clean_cache(cls) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            url for url, (_, timestamp) in cls._cache.items()
            if current_time - timestamp > cls._cache_ttl
        ]

        for key in expired_keys:
            del cls._cache[key]

        return len(expired_keys)

    @classmethod
    def _get_from_cache(cls, url: str) -> Optional[str]:
        """Get content from cache if not expired.

        Args:
            url: The URL to look up

        Returns:
            Cached content if available and not expired, None otherwise
        """
        # Clean expired entries
        cls._clean_cache()

        if url in cls._cache:
            content, timestamp = cls._cache[url]
            if time.time() - timestamp <= cls._cache_ttl:
                return content

        return None

    @classmethod
    def _add_to_cache(cls, url: str, content: str) -> None:
        """Add content to cache.

        Args:
            url: The URL to cache
            content: The content to cache
        """
        cls._cache[url] = (content, time.time())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached content."""
        cls._cache.clear()

    def _normalize_url(self, url: str) -> tuple[str, Optional[str]]:
        """Normalize and validate URL.

        Args:
            url: The URL to normalize

        Returns:
            Tuple of (normalized_url, error_message)
        """
        try:
            # Parse URL
            parsed = urlparse(url)

            # Check if scheme is present
            if not parsed.scheme:
                return "", "URL must include scheme (http:// or https://)"

            # Upgrade HTTP to HTTPS
            if parsed.scheme == "http":
                parsed = parsed._replace(scheme="https")

            # Validate scheme
            if parsed.scheme not in ["https"]:
                return "", f"Unsupported URL scheme: {parsed.scheme}. Only HTTPS is supported."

            # Check if netloc (domain) is present
            if not parsed.netloc:
                return "", "URL must include a domain name"

            # Reconstruct URL
            normalized = urlunparse(parsed)
            return normalized, None

        except Exception as e:
            return "", f"Invalid URL format: {str(e)}"

    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML to markdown.

        Args:
            html_content: HTML content to convert

        Returns:
            Markdown formatted text
        """
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = False
        converter.ignore_emphasis = False
        converter.body_width = 0  # Don't wrap lines
        converter.unicode_snob = True
        converter.skip_internal_links = True

        try:
            markdown = converter.handle(html_content)
            return markdown.strip()
        except Exception as e:
            # If conversion fails, return plain text
            return f"(HTML conversion failed: {str(e)})\n\n{html_content[:1000]}"

    async def _fetch_url(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Fetch content from URL.

        Args:
            url: The URL to fetch

        Returns:
            Tuple of (content, error_message)
        """
        try:
            async with httpx.AsyncClient(
                follow_redirects=self.follow_redirects,
                timeout=self.timeout
            ) as client:
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }

                response = await client.get(url, headers=headers)

                # Check response status
                if response.status_code == 404:
                    return None, "Page not found (404)"
                elif response.status_code == 403:
                    return None, "Access forbidden (403)"
                elif response.status_code == 401:
                    return None, "Authentication required (401)"
                elif response.status_code >= 400:
                    return None, f"HTTP error {response.status_code}"

                # Check content length
                content_length = len(response.content)
                if content_length > self.max_content_length:
                    return None, f"Content too large: {content_length} bytes (max: {self.max_content_length})"

                # Get content type
                content_type = response.headers.get("content-type", "").lower()

                # Check if content is HTML
                if "text/html" in content_type or "application/xhtml" in content_type:
                    html_content = response.text
                    markdown_content = self._html_to_markdown(html_content)
                    return markdown_content, None
                elif "text/plain" in content_type:
                    return response.text, None
                elif "application/json" in content_type:
                    return response.text, None
                else:
                    return None, f"Unsupported content type: {content_type}"

        except httpx.TimeoutException:
            return None, f"Request timed out after {self.timeout} seconds"
        except httpx.ConnectError:
            return None, "Could not connect to server"
        except httpx.TooManyRedirects:
            return None, "Too many redirects"
        except Exception as e:
            return None, f"Error fetching URL: {type(e).__name__}: {str(e)}"

    async def _process_with_llm(self, content: str, prompt: str) -> tuple[Optional[str], Optional[str]]:
        """Process content with LLM.

        Args:
            content: The content to process
            prompt: The user's prompt

        Returns:
            Tuple of (llm_response, error_message)
        """
        try:
            # Load environment variables
            load_env()

            # Import LLM factory to use configured provider
            from agent_cli.agents.llm_provider_factory import create_llm_provider
            from agent_framework.messages.types import SystemMessage, UserMessage

            # Use the default LLM provider from environment
            # Allow override with WEBFETCH_PROVIDER if needed
            provider_name = os.getenv("WEBFETCH_PROVIDER", os.getenv("DEFAULT_LLM_PROVIDER", "mock"))

            # Get default model from environment, allow override with WEBFETCH_MODEL
            # First try WEBFETCH_MODEL, then provider-specific default model, then None
            model_name = os.getenv("WEBFETCH_MODEL")
            if not model_name:
                # Try provider-specific default model
                if provider_name.lower() == "openai":
                    model_name = os.getenv("OPENAI_MODEL", os.getenv("DEFAULT_OPENAI_MODEL"))
                elif provider_name.lower() == "anthropic":
                    model_name = os.getenv("ANTHROPIC_MODEL", os.getenv("DEFAULT_ANTHROPIC_MODEL"))
                elif provider_name.lower() == "glm":
                    model_name = os.getenv("GLM_MODEL", os.getenv("DEFAULT_ZHIPU_MODEL"))
                # If still None, let factory use provider's default

            # Create LLM provider using factory
            try:
                llm = create_llm_provider(provider=provider_name, model=model_name)
            except Exception as e:
                # If provider creation fails, try with mock provider as fallback
                try:
                    llm = create_llm_provider(provider="mock", model="mock")
                except Exception as e2:
                    return None, f"Failed to create LLM provider ({provider_name}): {str(e)}. Mock fallback also failed: {str(e2)}"

            # Truncate content if too long (keep first part)
            max_content_length = 100000  # ~25k tokens
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n\n[Content truncated...]"

            # Create messages
            system_msg = SystemMessage(
                session_id="web_fetch",
                sequence=1,
                content="You are a helpful assistant that extracts and summarizes information from web content. "
                       "The content has been converted from HTML to markdown format. "
                       "Provide clear, factual responses based on the content provided."
            )
            user_msg = UserMessage(
                session_id="web_fetch",
                sequence=2,
                content=f"Here is the web page content:\n\n{content}\n\n"
                       f"User request: {prompt}\n\n"
                       f"Please provide a clear and concise response based on the content."
            )

            # Convert messages to LLM format
            messages = [
                {"role": "system", "content": system_msg.content},
                {"role": "user", "content": user_msg.content}
            ]

            # Generate response
            response = llm.generate(messages)

            if response and response.content:
                return response.content, None
            else:
                return None, "LLM returned empty response"

        except ImportError as e:
            return None, f"LLM components not available: {str(e)}"
        except Exception as e:
            return None, f"Error processing with LLM: {type(e).__name__}: {str(e)}"

    async def execute(
        self,
        url: str,
        prompt: str
    ) -> ToolResult:
        """Fetch URL content and process with LLM.

        Args:
            url: The URL to fetch
            prompt: The prompt for processing the content

        Returns:
            ToolResult with LLM response or error
        """
        try:
            # Normalize URL
            normalized_url, error = self._normalize_url(url)
            if error:
                return ToolResult(error=error)

            # Check cache first
            cached_content = self._get_from_cache(normalized_url)
            if cached_content:
                # Process cached content with LLM
                response, error = await self._process_with_llm(cached_content, prompt)
                if error:
                    return ToolResult(error=error)

                return ToolResult(
                    output=response,
                    system="Content retrieved from cache (less than 15 minutes old)"
                )

            # Fetch content
            content, error = await self._fetch_url(normalized_url)
            if error:
                return ToolResult(error=error)

            # Add to cache
            self._add_to_cache(normalized_url, content)

            # Process with LLM
            response, error = await self._process_with_llm(content, prompt)
            if error:
                return ToolResult(error=error)

            return ToolResult(
                output=response,
                system=f"Fetched from: {normalized_url}"
            )

        except Exception as e:
            return ToolResult(
                error=f"Error in web fetch: {type(e).__name__}: {str(e)}"
            )
