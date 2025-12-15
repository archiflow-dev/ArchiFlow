"""Tests for configuration management."""
import unittest
import tempfile
import os
from pathlib import Path
from src.agent_framework.config.manager import (
    ConfigManager, AgentFrameworkConfig,
    LLMConfig, LLMProviderConfig, AgentConfig
)


class TestConfigModels(unittest.TestCase):
    """Test Pydantic config models."""
    
    def test_llm_provider_config(self):
        """Test LLMProviderConfig."""
        config = LLMProviderConfig(
            model="gpt-4o",
            api_key="test_key",
            temperature=0.8,
            max_tokens=1000
        )
        
        self.assertEqual(config.model, "gpt-4o")
        self.assertEqual(config.temperature, 0.8)
    
    def test_llm_provider_defaults(self):
        """Test LLMProviderConfig with defaults."""
        config = LLMProviderConfig(model="test")
        
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_tokens, 2000)
        self.assertIsNone(config.api_key)
    
    def test_temperature_validation(self):
        """Test temperature bounds validation."""
        # Valid
        LLMProviderConfig(model="test", temperature=0.0)
        LLMProviderConfig(model="test", temperature=2.0)
        
        # Invalid
        with self.assertRaises(Exception):
            LLMProviderConfig(model="test", temperature=-0.1)
        
        with self.assertRaises(Exception):
            LLMProviderConfig(model="test", temperature=2.1)
    
    def test_env_var_resolution(self):
        """Test environment variable resolution in API key."""
        os.environ['TEST_API_KEY'] = 'secret_key_123'
        
        config = LLMProviderConfig(
            model="test",
            api_key="${TEST_API_KEY}"
        )
        
        self.assertEqual(config.api_key, 'secret_key_123')
    
    def test_agent_config(self):
        """Test AgentConfig."""
        config = AgentConfig(
            llm_provider="openai",
            tools=["read_file", "write_file"],
            max_iterations=100
        )
        
        self.assertEqual(config.llm_provider, "openai")
        self.assertEqual(len(config.tools), 2)
        self.assertEqual(config.max_iterations, 100)


class TestConfigManager(unittest.TestCase):
    """Test ConfigManager."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.yaml")
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_and_load(self):
        """Test saving and loading config."""
        manager = ConfigManager(self.config_path)
        
        # Create config
        config = AgentFrameworkConfig(
            llm=LLMConfig(
                default_provider="test",
                providers={
                    "test": LLMProviderConfig(model="test-model")
                }
            )
        )
        
        # Save
        manager.save(config)
        self.assertTrue(os.path.exists(self.config_path))
        
        # Load
        loaded_config = manager.load()
        self.assertEqual(loaded_config.llm.default_provider, "test")
        self.assertIn("test", loaded_config.llm.providers)
    
    def test_load_nonexistent_file(self):
        """Test loading non-existent file raises error."""
        manager = ConfigManager("nonexistent.yaml")
        
        with self.assertRaises(FileNotFoundError):
            manager.load()
    
    def test_load_or_default(self):
        """Test load_or_default returns default if file missing."""
        manager = ConfigManager("nonexistent.yaml")
        
        config = manager.load_or_default()
        self.assertIsInstance(config, AgentFrameworkConfig)
        self.assertEqual(config.llm.default_provider, "mock")
    
    def test_get_default_config(self):
        """Test default config generation."""
        config = ConfigManager.get_default_config()
        
        self.assertIsInstance(config, AgentFrameworkConfig)
        self.assertEqual(config.llm.default_provider, "mock")
        self.assertIn("mock", config.llm.providers)
        self.assertIn("default", config.agents)
        self.assertIn("read_file", config.tools.enabled_tools)
    
    def test_agent_config_in_framework(self):
        """Test agents dict in framework config."""
        config = AgentFrameworkConfig(
            llm=LLMConfig(
                default_provider="test",
                providers={"test": LLMProviderConfig(model="test")}
            ),
            agents={
                "coder": AgentConfig(
                    llm_provider="test",
                    tools=["read_file"]
                )
            }
        )
        
        self.assertIn("coder", config.agents)
        self.assertEqual(config.agents["coder"].llm_provider, "test")


class TestConfigValidation(unittest.TestCase):
    """Test config validation."""
    
    def test_max_iterations_must_be_positive(self):
        """Test max_iterations validation."""
        with self.assertRaises(Exception):
            AgentConfig(
                llm_provider="test",
                max_iterations=0  # Invalid
            )
        
        with self.assertRaises(Exception):
            AgentConfig(
                llm_provider="test",
                max_iterations=-1  # Invalid
            )
    
    def test_timeout_must_be_positive(self):
        """Test timeout validation."""
        from src.agent_framework.config.manager import ToolConfig
        
        with self.assertRaises(Exception):
            ToolConfig(timeout=0)
        
        with self.assertRaises(Exception):
            ToolConfig(timeout=-5)


if __name__ == '__main__':
    unittest.main()
