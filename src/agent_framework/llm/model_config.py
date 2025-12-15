"""
Model configuration and registry for managing different LLM models.
"""
import logging
from dataclasses import dataclass
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a specific LLM model."""

    model_name: str
    context_window: int  # Total context window in tokens
    max_output_tokens: int  # Maximum tokens for completion
    cost_per_1k_input: float = 0.0  # Cost per 1k input tokens (USD)
    cost_per_1k_output: float = 0.0  # Cost per 1k output tokens (USD)
    supports_tools: bool = True

    def get_available_context(
        self,
        system_prompt_tokens: int = 0,
        tools_tokens: int = 0,
        buffer_tokens: int = 500
    ) -> int:
        """
        Calculate tokens available for conversation history.

        Args:
            system_prompt_tokens: Tokens used by system prompt
            tools_tokens: Tokens used by tool definitions
            buffer_tokens: Safety buffer for token counting errors

        Returns:
            Number of tokens available for conversation history
        """
        reserved = system_prompt_tokens + tools_tokens + self.max_output_tokens + buffer_tokens
        available = self.context_window - reserved

        if available < 0:
            logger.warning(
                f"Model {self.model_name}: reserved tokens ({reserved}) exceeds context window "
                f"({self.context_window}). System prompt or tools may be too large."
            )
            return 0

        return available

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate the cost of a request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1000) * self.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self.cost_per_1k_output
        return input_cost + output_cost


class ModelRegistry:
    """Registry of known model configurations."""

    # Static model configurations
    MODELS: Dict[str, ModelConfig] = {
        # OpenAI Models
        "gpt-4o": ModelConfig(
            model_name="gpt-4o",
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1k_input=2.50,
            cost_per_1k_output=10.00
        ),
        "gpt-4o-mini": ModelConfig(
            model_name="gpt-4o-mini",
            context_window=128_000,
            max_output_tokens=16_384,
            cost_per_1k_input=0.15,
            cost_per_1k_output=0.60
        ),
        "gpt-4-turbo": ModelConfig(
            model_name="gpt-4-turbo",
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1k_input=10.00,
            cost_per_1k_output=30.00
        ),
        "gpt-4": ModelConfig(
            model_name="gpt-4",
            context_window=8_192,
            max_output_tokens=4_096,
            cost_per_1k_input=30.00,
            cost_per_1k_output=60.00
        ),
        "gpt-3.5-turbo": ModelConfig(
            model_name="gpt-3.5-turbo",
            context_window=16_385,
            max_output_tokens=4_096,
            cost_per_1k_input=0.50,
            cost_per_1k_output=1.50
        ),
        "gpt-5": ModelConfig(
            model_name="gpt-5",
            context_window=200_000,
            max_output_tokens=8_192,
            cost_per_1k_input=5.00,
            cost_per_1k_output=15.00
        ),

        # Anthropic Models
        "claude-3-5-sonnet-20241022": ModelConfig(
            model_name="claude-3-5-sonnet-20241022",
            context_window=200_000,
            max_output_tokens=8_192,
            cost_per_1k_input=3.00,
            cost_per_1k_output=15.00
        ),
        "claude-3-opus-20240229": ModelConfig(
            model_name="claude-3-opus-20240229",
            context_window=200_000,
            max_output_tokens=4_096,
            cost_per_1k_input=15.00,
            cost_per_1k_output=75.00
        ),
        "claude-3-sonnet-20240229": ModelConfig(
            model_name="claude-3-sonnet-20240229",
            context_window=200_000,
            max_output_tokens=4_096,
            cost_per_1k_input=3.00,
            cost_per_1k_output=15.00
        ),
        "claude-3-haiku-20240307": ModelConfig(
            model_name="claude-3-haiku-20240307",
            context_window=200_000,
            max_output_tokens=4_096,
            cost_per_1k_input=0.25,
            cost_per_1k_output=1.25
        ),

        # Zhipu GLM Models
        "glm-4.6": ModelConfig(
            model_name="glm-4.6",
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1k_input=0.1,  # Estimated pricing
            cost_per_1k_output=0.1
        ),
        "glm-4": ModelConfig(
            model_name="glm-4",
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1k_input=0.1,  # Estimated pricing
            cost_per_1k_output=0.1
        ),
        "glm-4-plus": ModelConfig(
            model_name="glm-4-plus",
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1k_input=0.12,
            cost_per_1k_output=0.12
        ),
        "glm-4-air": ModelConfig(
            model_name="glm-4-air",
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1k_input=0.01,  # More economical
            cost_per_1k_output=0.01
        ),
        "glm-4-airx": ModelConfig(
            model_name="glm-4-airx",
            context_window=128_000,
            max_output_tokens=8_192,
            cost_per_1k_input=0.015,
            cost_per_1k_output=0.015
        ),
        "glm-4-long": ModelConfig(
            model_name="glm-4-long",
            context_window=1_000_000,  # Large context
            max_output_tokens=8_192,
            cost_per_1k_input=0.05,
            cost_per_1k_output=0.05
        ),
        "glm-4-flash": ModelConfig(
            model_name="glm-4-flash",
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1k_input=0.0001,  # Very cheap
            cost_per_1k_output=0.0001
        ),
        "glm-3-turbo": ModelConfig(
            model_name="glm-3-turbo",
            context_window=128_000,
            max_output_tokens=4_096,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.005
        ),
    }

    @classmethod
    def get(cls, model_name: str) -> ModelConfig:
        """
        Get configuration for a model.

        Args:
            model_name: Name of the model

        Returns:
            ModelConfig for the model (with fallback to defaults)
        """
        # Exact match
        if model_name in cls.MODELS:
            return cls.MODELS[model_name]

        # Try pattern matching for versioned models
        # e.g., "gpt-4o-2024-05-13" matches "gpt-4o"
        for registered_name, config in cls.MODELS.items():
            if model_name.startswith(registered_name):
                logger.info(f"Model '{model_name}' matched to '{registered_name}'")
                return config

        # Try base model name (everything before first dash after removing version)
        # e.g., "gpt-4-turbo-preview" -> "gpt-4-turbo"
        parts = model_name.split('-')
        for i in range(len(parts), 1, -1):
            prefix = '-'.join(parts[:i])
            if prefix in cls.MODELS:
                logger.info(f"Model '{model_name}' matched to '{prefix}'")
                return cls.MODELS[prefix]

        # Fallback: conservative defaults
        logger.warning(
            f"Unknown model '{model_name}', using conservative defaults "
            f"(8k context window)"
        )
        return ModelConfig(
            model_name=model_name,
            context_window=8_192,  # Conservative default
            max_output_tokens=2_048,
            cost_per_1k_input=0.0,  # Unknown cost
            cost_per_1k_output=0.0,
            supports_tools=True
        )

    @classmethod
    def register(cls, model_name: str, config: ModelConfig) -> None:
        """
        Register a custom model configuration.

        Args:
            model_name: Name of the model
            config: ModelConfig for the model
        """
        cls.MODELS[model_name] = config
        logger.info(f"Registered custom model: {model_name}")

    @classmethod
    def list_models(cls) -> list[str]:
        """Get list of all registered model names."""
        return sorted(cls.MODELS.keys())
