"""
Terminal configuration for ArchiFlow CLI.

Manages terminal appearance preferences including font configuration.
Uses hierarchical loading: .archiflow/config/ -> ~/.archiflow/config/ -> defaults
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class TerminalConfig:
    """Terminal appearance configuration."""

    # Font preferences
    preferred_font: str = "Cascadia Code"
    fallback_fonts: list[str] = field(default_factory=lambda: [
        "Fira Code",
        "JetBrains Mono",
        "Consolas",
        "monospace"
    ])
    font_size: int = 14
    enable_ligatures: bool = True
    line_height: float = 1.2

    # Terminal behavior
    cursor_blinking: bool = True
    cursor_style: str = "line"  # line, block, underline

    # Rich text support
    enable_images: bool = True
    gpu_acceleration: str = "on"  # on, off, auto

    @property
    def font_family(self) -> str:
        """Get the full font family string for VS Code."""
        fonts = [self.preferred_font] + self.fallback_fonts
        return ", ".join(fonts)

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "terminal": {
                "preferred_font": self.preferred_font,
                "fallback_fonts": self.fallback_fonts,
                "font_size": self.font_size,
                "enable_ligatures": self.enable_ligatures,
                "line_height": self.line_height,
                "cursor_blinking": self.cursor_blinking,
                "cursor_style": self.cursor_style,
                "enable_images": self.enable_images,
                "gpu_acceleration": self.gpu_acceleration,
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TerminalConfig":
        """Create TerminalConfig from dictionary."""
        terminal_data = data.get("terminal", {})
        return cls(
            preferred_font=terminal_data.get("preferred_font", "Cascadia Code"),
            fallback_fonts=terminal_data.get("fallback_fonts", [
                "Fira Code", "JetBrains Mono", "Consolas", "monospace"
            ]),
            font_size=terminal_data.get("font_size", 14),
            enable_ligatures=terminal_data.get("enable_ligatures", True),
            line_height=terminal_data.get("line_height", 1.2),
            cursor_blinking=terminal_data.get("cursor_blinking", True),
            cursor_style=terminal_data.get("cursor_style", "line"),
            enable_images=terminal_data.get("enable_images", True),
            gpu_acceleration=terminal_data.get("gpu_acceleration", "on"),
        )

    def to_vscode_settings(self) -> dict:
        """
        Convert to VS Code settings.json format.

        Returns:
            Dictionary with VS Code terminal settings
        """
        return {
            "terminal.integrated.fontFamily": self.font_family,
            "terminal.integrated.fontSize": self.font_size,
            "terminal.integrated.fontWeight": "normal",
            "terminal.integrated.lineHeight": self.line_height,
            "terminal.integrated.fontLigatures": self.enable_ligatures,
            "terminal.integrated.cursorBlinking": self.cursor_blinking,
            "terminal.integrated.cursorStyle": self.cursor_style,
            "terminal.integrated.enableImages": self.enable_images,
            "terminal.integrated.gpuAcceleration": self.gpu_acceleration,
        }


def load_terminal_config(working_dir: Optional[Path] = None) -> TerminalConfig:
    """
    Load terminal configuration with hierarchical override system.

    Priority (highest to lowest):
    1. Project-specific: ./.archiflow/config/terminal.yaml
    2. User-global: ~/.archiflow/config/terminal.yaml
    3. Framework default: embedded defaults

    Args:
        working_dir: Project working directory (for project-specific config)

    Returns:
        TerminalConfig instance
    """
    # Try project-specific config
    if working_dir:
        project_config = Path(working_dir) / ".archiflow" / "config" / "terminal.yaml"
        if project_config.exists():
            try:
                with open(project_config, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return TerminalConfig.from_dict(data)
            except Exception:
                pass  # Fall through to next level

    # Try user-global config
    user_config = Path.home() / ".archiflow" / "config" / "terminal.yaml"
    if user_config.exists():
        try:
            with open(user_config, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return TerminalConfig.from_dict(data)
        except Exception:
            pass  # Fall through to defaults

    # Return defaults
    return TerminalConfig()


def save_terminal_config(config: TerminalConfig, global_config: bool = True) -> Path:
    """
    Save terminal configuration to file.

    Args:
        config: TerminalConfig to save
        global_config: If True, save to ~/.archiflow/config/terminal.yaml
                      If False, save to ./.archiflow/config/terminal.yaml

    Returns:
        Path where config was saved
    """
    if global_config:
        config_path = Path.home() / ".archiflow" / "config" / "terminal.yaml"
    else:
        config_path = Path.cwd() / ".archiflow" / "config" / "terminal.yaml"

    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)

    return config_path
