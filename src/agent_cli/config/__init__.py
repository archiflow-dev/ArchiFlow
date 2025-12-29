"""
Configuration management for agent-cli.
"""

from .terminal_config import TerminalConfig, load_terminal_config, save_terminal_config

__all__ = ["TerminalConfig", "load_terminal_config", "save_terminal_config"]
