"""
Tests for ModelConfig and ModelRegistry.
"""
import unittest

from src.agent_framework.llm.model_config import ModelConfig, ModelRegistry


class TestModelConfig(unittest.TestCase):
    """Test ModelConfig class."""

    def test_model_config_creation(self):
        """Test creating a ModelConfig."""
        config = ModelConfig(
            model_name="test-model",
            context_window=100_000,
            max_output_tokens=4_096,
            cost_per_1k_input=1.50,
            cost_per_1k_output=5.00
        )

        self.assertEqual(config.model_name, "test-model")
        self.assertEqual(config.context_window, 100_000)
        self.assertEqual(config.max_output_tokens, 4_096)
        self.assertEqual(config.cost_per_1k_input, 1.50)
        self.assertEqual(config.cost_per_1k_output, 5.00)
        self.assertTrue(config.supports_tools)

    def test_get_available_context(self):
        """Test calculating available context tokens."""
        config = ModelConfig(
            model_name="test-model",
            context_window=128_000,
            max_output_tokens=4_096
        )

        # With no system prompt or tools
        available = config.get_available_context()
        # 128,000 - 4,096 (output) - 500 (buffer) = 123,404
        self.assertEqual(available, 123_404)

        # With system prompt and tools
        available = config.get_available_context(
            system_prompt_tokens=1000,
            tools_tokens=2000,
            buffer_tokens=500
        )
        # 128,000 - 1,000 - 2,000 - 4,096 - 500 = 120,404
        self.assertEqual(available, 120_404)

    def test_get_available_context_exceeds_window(self):
        """Test when reserved tokens exceed context window."""
        config = ModelConfig(
            model_name="tiny-model",
            context_window=8_192,
            max_output_tokens=4_096
        )

        # Reserved tokens exceed context window
        available = config.get_available_context(
            system_prompt_tokens=5_000,
            tools_tokens=3_000
        )
        # Should return 0, not negative
        self.assertEqual(available, 0)

    def test_calculate_cost(self):
        """Test cost calculation."""
        config = ModelConfig(
            model_name="test-model",
            context_window=100_000,
            max_output_tokens=4_096,
            cost_per_1k_input=2.50,
            cost_per_1k_output=10.00
        )

        # 1000 input, 500 output
        cost = config.calculate_cost(input_tokens=1000, output_tokens=500)
        # (1000/1000 * 2.50) + (500/1000 * 10.00) = 2.50 + 5.00 = 7.50
        self.assertEqual(cost, 7.50)

        # 2500 input, 1200 output
        cost = config.calculate_cost(input_tokens=2500, output_tokens=1200)
        # (2500/1000 * 2.50) + (1200/1000 * 10.00) = 6.25 + 12.00 = 18.25
        self.assertEqual(cost, 18.25)


class TestModelRegistry(unittest.TestCase):
    """Test ModelRegistry class."""

    def test_get_known_model(self):
        """Test getting a known model."""
        config = ModelRegistry.get("gpt-4o")

        self.assertEqual(config.model_name, "gpt-4o")
        self.assertEqual(config.context_window, 128_000)
        self.assertEqual(config.max_output_tokens, 4_096)

    def test_get_versioned_model(self):
        """Test getting a versioned model (pattern matching)."""
        # Should match to gpt-4o
        config = ModelRegistry.get("gpt-4o-2024-05-13")

        self.assertEqual(config.model_name, "gpt-4o")
        self.assertEqual(config.context_window, 128_000)

    def test_get_unknown_model(self):
        """Test getting an unknown model (returns conservative defaults)."""
        config = ModelRegistry.get("unknown-model-xyz")

        self.assertEqual(config.model_name, "unknown-model-xyz")
        self.assertEqual(config.context_window, 8_192)  # Conservative default
        self.assertEqual(config.max_output_tokens, 2_048)
        self.assertEqual(config.cost_per_1k_input, 0.0)  # Unknown cost

    def test_register_custom_model(self):
        """Test registering a custom model."""
        custom_config = ModelConfig(
            model_name="my-custom-model",
            context_window=200_000,
            max_output_tokens=8_192,
            cost_per_1k_input=1.00,
            cost_per_1k_output=3.00
        )

        ModelRegistry.register("my-custom-model", custom_config)

        # Retrieve it
        config = ModelRegistry.get("my-custom-model")
        self.assertEqual(config.model_name, "my-custom-model")
        self.assertEqual(config.context_window, 200_000)
        self.assertEqual(config.max_output_tokens, 8_192)

    def test_list_models(self):
        """Test listing all registered models."""
        models = ModelRegistry.list_models()

        self.assertIn("gpt-4o", models)
        self.assertIn("gpt-4-turbo", models)
        self.assertIn("claude-3-5-sonnet-20241022", models)
        self.assertIsInstance(models, list)

    def test_all_predefined_models(self):
        """Test that all predefined models can be retrieved."""
        models_to_test = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229"
        ]

        for model_name in models_to_test:
            config = ModelRegistry.get(model_name)
            self.assertEqual(config.model_name, model_name)
            self.assertGreater(config.context_window, 0)
            self.assertGreater(config.max_output_tokens, 0)


if __name__ == "__main__":
    unittest.main()
