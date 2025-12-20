"""
Configuration Management System.

Uses Pydantic for validation and YAML for storage.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import yaml
import os
from pathlib import Path


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""
    model: str
    api_key: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, gt=0)
    
    @field_validator('api_key')
    @classmethod
    def resolve_env_var(cls, v: Optional[str]) -> Optional[str]:
        """Resolve environment variable placeholders like ${VAR_NAME}."""
        if v and v.startswith('${') and v.endswith('}'):
            env_var = v[2:-1]
            return os.getenv(env_var, v)
        return v


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    default_provider: str
    providers: Dict[str, LLMProviderConfig]


class ToolConfig(BaseModel):
    """Configuration for tools."""
    enabled_tools: List[str] = Field(default_factory=list)
    timeout: int = Field(default=30, gt=0)
    max_output_size: int = Field(default=1048576, gt=0)  # 1MB default


class AgentConfig(BaseModel):
    """Configuration for a specific agent type."""
    name: str = "DefaultAgent"
    version: str = "1.0.0"
    llm_provider: str = "mock"
    tools: List[str] = Field(default_factory=list)
    max_iterations: int = Field(default=50, gt=0)
    max_tokens_history: int = Field(default=8000, gt=0)


class SessionConfig(BaseModel):
    """Configuration for session management."""
    persistence_dir: str = "sessions"
    auto_restore: bool = True


class OutputConfig(BaseModel):
    """Configuration for output rendering."""
    tool_result_line_limit: int = Field(default=10, gt=0, description="Maximum number of lines to display for tool results")
    show_tool_thoughts: bool = Field(default=True, description="Whether to show agent tool thoughts/reasoning")
    verbose_errors: bool = Field(default=False, description="Whether to show verbose error messages")


class AgentFrameworkConfig(BaseModel):
    """Root configuration for the agent framework."""
    llm: LLMConfig
    tools: ToolConfig = Field(default_factory=ToolConfig)
    agents: Dict[str, AgentConfig] = Field(default_factory=dict)
    session: SessionConfig = Field(default_factory=SessionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


class ConfigManager:
    """Manages configuration loading and validation."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self.config: Optional[AgentFrameworkConfig] = None
    
    def load(self) -> AgentFrameworkConfig:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        self.config = AgentFrameworkConfig(**data)
        return self.config
    
    def load_or_default(self) -> AgentFrameworkConfig:
        """Load config or return default if file doesn't exist."""
        try:
            return self.load()
        except FileNotFoundError:
            return self.get_default_config()
    
    def save(self, config: AgentFrameworkConfig, path: Optional[str] = None) -> None:
        """Save configuration to YAML file."""
        save_path = path or self.config_path
        
        # Convert to dict
        data = config.model_dump()
        
        with open(save_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
    
    @staticmethod
    def get_default_config() -> AgentFrameworkConfig:
        """Get default configuration."""
        return AgentFrameworkConfig(
            llm=LLMConfig(
                default_provider="mock",
                providers={
                    "mock": LLMProviderConfig(model="mock-model")
                }
            ),
            tools=ToolConfig(
                enabled_tools=["read_file", "write_file", "list_files"]
            ),
            agents={
                "default": AgentConfig(
                    llm_provider="mock",
                    tools=["read_file", "write_file"]
                )
            }
        )
