"""
LLM Provider Factory using the Factory Method pattern.

This module provides a cleaner, more extensible way to create LLM providers
without relying on multiple if-elif statements.
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, Type, Optional

from agent_framework.llm.openai_provider import OpenAIProvider
from agent_framework.llm.provider import LLMProvider
from agent_framework.llm.anthropic_provider import AnthropicProvider
from agent_framework.llm.mock import MockLLMProvider

# Import will be done lazily to avoid circular imports
GLMProvider = None


class ProviderConfig:
    """Configuration class for LLM providers."""

    def __init__(
        self,
        provider_class: Type[LLMProvider],
        default_model: str,
        api_key_env: str,
        api_key_name: str,
        base_url_env: Optional[str] = None
    ):
        self.provider_class = provider_class
        self.default_model = default_model
        self.api_key_env = api_key_env
        self.api_key_name = api_key_name
        self.base_url_env = base_url_env


class LLMProviderFactory:
    """
    Factory for creating LLM providers using the Factory Method pattern.

    This class maintains a registry of provider configurations and creates
    providers based on the requested type.
    """

    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._register_providers()

    def _register_providers(self):
        """Register all available LLM providers."""
        # Register OpenAI provider
        self.register_provider(
            name="openai",
            provider_class=OpenAIProvider,
            default_model="gpt-5",
            api_key_env="OPENAI_API_KEY",
            api_key_name="OpenAI",
            base_url_env="OPENAI_BASE_URL"
        )

        # Register Anthropic provider
        self.register_provider(
            name="anthropic",
            provider_class=AnthropicProvider,
            default_model="claude-3-5-sonnet-20241022",
            api_key_env="ANTHROPIC_API_KEY",
            api_key_name="Anthropic",
            base_url_env="ANTHROPIC_BASE_URL"
        )

        # Register Mock provider
        self.register_provider(
            name="mock",
            provider_class=MockLLMProvider,
            default_model="mock-model",
            api_key_env=None,  # Mock doesn't need API key
            api_key_name="Mock"
        )

        # Register GLM provider (lazy loading to avoid circular imports)
        self.register_provider(
            name="glm",
            provider_class=self._get_glm_provider_class,
            default_model="glm-4.6",
            api_key_env="ZAI_API_KEY",
            api_key_name="Z.ai",
            base_url_env="GLM_BASE_URL"
        )

    def _get_glm_provider_class(self):
        """Lazy import of GLMProvider to avoid circular imports."""
        global GLMProvider
        if GLMProvider is None:
            from agent_framework.llm.glm_provider import GLMProvider as _GLMProvider
            GLMProvider = _GLMProvider
        return GLMProvider

    def register_provider(
        self,
        name: str,
        provider_class: Type[LLMProvider],
        default_model: str,
        api_key_env: Optional[str],
        api_key_name: str,
        base_url_env: Optional[str] = None
    ):
        """
        Register a new LLM provider.

        Args:
            name: Provider name (e.g., "openai", "anthropic")
            provider_class: The provider class or callable that returns the class
            default_model: Default model for this provider
            api_key_env: Environment variable name for API key
            api_key_name: Human-readable name for the provider
            base_url_env: Optional environment variable for custom base URL
        """
        self._providers[name] = ProviderConfig(
            provider_class=provider_class,
            default_model=default_model,
            api_key_env=api_key_env,
            api_key_name=api_key_name,
            base_url_env=base_url_env
        )

    def create_provider(
        self,
        provider: str = None,
        model: str = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> LLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider: Provider name ("openai", "anthropic", "glm", "mock")
                      If None, uses DEFAULT_LLM_PROVIDER from environment
            model: Model name. If None, uses provider's default model
            api_key: API key (uses provider-specific env var if not provided)
            base_url: Custom base URL (optional)

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider is not supported
            RuntimeError: If API key is missing
        """
        # Get default provider from environment if not specified
        if provider is None:
            provider = os.getenv("DEFAULT_LLM_PROVIDER", "openai")

        # Validate provider exists
        if provider not in self._providers:
            supported = ", ".join(self._providers.keys())
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {supported}"
            )

        config = self._providers[provider]

        # Get default model for the provider if not specified
        if model is None:
            default_model_key = f"DEFAULT_{provider.upper()}_MODEL"
            model = os.getenv(default_model_key, config.default_model)

        # Handle lazy loading for provider classes
        if callable(config.provider_class) and not isinstance(config.provider_class, type):
            provider_class = config.provider_class()
        else:
            provider_class = config.provider_class

        # For mock provider, no API key needed
        if provider == "mock":
            return provider_class(model=model)

        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.getenv(config.api_key_env) if config.api_key_env else None

        if not api_key:
            raise RuntimeError(
                f"{config.api_key_name} API key not found. "
                f"Set {config.api_key_env} environment variable "
                f"or pass api_key parameter."
            )

        # Get custom base URL if specified
        if base_url is None and config.base_url_env:
            base_url = os.getenv(config.base_url_env)

        # Create and return the provider instance
        return provider_class(
            model=model,
            api_key=api_key,
            base_url=base_url
        )

    def get_supported_providers(self) -> list[str]:
        """Get list of supported provider names."""
        return list(self._providers.keys())

    def get_provider_info(self, provider_name: str) -> Dict[str, str]:
        """
        Get information about a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Dictionary with provider information
        """
        if provider_name not in self._providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        config = self._providers[provider_name]
        return {
            "name": provider_name,
            "default_model": config.default_model,
            "api_key_env": config.api_key_env,
            "api_key_name": config.apikey_name if hasattr(config, 'apikey_name') else config.api_key_name,
        }


# Global factory instance
_llm_factory = LLMProviderFactory()


def create_llm_provider(
    provider: str = None,
    model: str = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMProvider:
    """
    Create an LLM provider instance.

    This is a convenience function that delegates to the global factory.

    Args:
        provider: Provider name ("openai", "anthropic", "glm", "mock")
                  If None, uses DEFAULT_LLM_PROVIDER from environment
        model: Model name. If None, uses provider's default model
        api_key: API key (uses provider-specific env var if not provided)
        base_url: Custom base URL (optional)

    Returns:
        LLMProvider instance
    """
    return _llm_factory.create_provider(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url
    )


def get_supported_providers() -> list[str]:
    """Get list of supported LLM provider names."""
    return _llm_factory.get_supported_providers()