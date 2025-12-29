"""
Font detection and validation utilities.

Cross-platform font availability checking for terminal configuration.
"""

import platform
import subprocess
from pathlib import Path
from typing import Optional


class FontDetector:
    """Detect and validate font installation across platforms."""

    @staticmethod
    def is_font_installed(font_name: str) -> bool:
        """
        Check if a font is installed on the system.

        Args:
            font_name: Name of the font (e.g., "Cascadia Code")

        Returns:
            True if font is installed, False otherwise
        """
        system = platform.system()

        try:
            if system == "Windows":
                return FontDetector._check_windows_font(font_name)
            elif system == "Darwin":  # macOS
                return FontDetector._check_macos_font(font_name)
            elif system == "Linux":
                return FontDetector._check_linux_font(font_name)
            else:
                return False
        except Exception:
            return False

    @staticmethod
    def _check_windows_font(font_name: str) -> bool:
        """Check font installation on Windows."""
        # Check Windows Fonts directory
        fonts_dir = Path(r"C:\Windows\Fonts")
        if not fonts_dir.exists():
            return False

        # Normalize font name for file matching
        normalized = font_name.lower().replace(" ", "")

        # Check for common font file extensions
        for ext in [".ttf", ".otf", ".ttc"]:
            for font_file in fonts_dir.glob(f"*{ext}"):
                file_normalized = font_file.stem.lower().replace(" ", "").replace("-", "")
                if normalized in file_normalized or file_normalized in normalized:
                    return True

        # Also check user fonts directory
        user_fonts = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
        if user_fonts.exists():
            for ext in [".ttf", ".otf", ".ttc"]:
                for font_file in user_fonts.glob(f"*{ext}"):
                    file_normalized = font_file.stem.lower().replace(" ", "").replace("-", "")
                    if normalized in file_normalized or file_normalized in normalized:
                        return True

        return False

    @staticmethod
    def _check_macos_font(font_name: str) -> bool:
        """Check font installation on macOS."""
        try:
            # Use fc-list if available (from fontconfig)
            result = subprocess.run(
                ["fc-list", ":", "family"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                fonts = result.stdout.lower()
                return font_name.lower() in fonts
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback: Check common macOS font directories
        font_dirs = [
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
        ]

        normalized = font_name.lower().replace(" ", "")
        for font_dir in font_dirs:
            if not font_dir.exists():
                continue
            for ext in [".ttf", ".otf", ".ttc", ".dfont"]:
                for font_file in font_dir.glob(f"*{ext}"):
                    file_normalized = font_file.stem.lower().replace(" ", "").replace("-", "")
                    if normalized in file_normalized or file_normalized in normalized:
                        return True

        return False

    @staticmethod
    def _check_linux_font(font_name: str) -> bool:
        """Check font installation on Linux."""
        try:
            # Use fc-list (fontconfig is standard on Linux)
            result = subprocess.run(
                ["fc-list", ":", "family"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                fonts = result.stdout.lower()
                return font_name.lower() in fonts
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return False

    @staticmethod
    def get_installed_fonts() -> list[str]:
        """
        Get list of installed fonts on the system.

        Returns:
            List of font family names
        """
        system = platform.system()

        try:
            if system in ["Darwin", "Linux"]:
                # Use fc-list for macOS and Linux
                result = subprocess.run(
                    ["fc-list", ":", "family"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    # Parse output (format: "Font Name,Alternative Name:...")
                    fonts = set()
                    for line in result.stdout.splitlines():
                        # Split by comma to get all names
                        names = line.split(",")
                        for name in names:
                            # Remove style info (after colon)
                            name = name.split(":")[0].strip()
                            if name:
                                fonts.add(name)
                    return sorted(fonts)
            elif system == "Windows":
                # For Windows, list font files
                fonts = set()
                fonts_dir = Path(r"C:\Windows\Fonts")
                if fonts_dir.exists():
                    for font_file in fonts_dir.glob("*.[to]t[fc]"):  # .ttf, .otf, .ttc
                        # Extract font name from filename (rough approximation)
                        name = font_file.stem.replace("-", " ").replace("_", " ")
                        fonts.add(name)

                # Also check user fonts
                user_fonts = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
                if user_fonts.exists():
                    for font_file in user_fonts.glob("*.[to]t[fc]"):
                        name = font_file.stem.replace("-", " ").replace("_", " ")
                        fonts.add(name)

                return sorted(fonts)
        except Exception:
            pass

        return []

    @staticmethod
    def get_font_info(font_name: str) -> Optional[dict]:
        """
        Get detailed information about a font.

        Args:
            font_name: Font family name

        Returns:
            Dictionary with font info or None if not found
        """
        if not FontDetector.is_font_installed(font_name):
            return None

        return {
            "name": font_name,
            "installed": True,
            "platform": platform.system(),
        }

    @staticmethod
    def get_recommended_fonts() -> dict[str, dict]:
        """
        Get information about recommended developer fonts.

        Returns:
            Dictionary mapping font names to their info
        """
        recommended = {
            "Cascadia Code": {
                "description": "Microsoft's developer font, designed for VS Code",
                "ligatures": True,
                "download": "https://github.com/microsoft/cascadia-code/releases",
                "license": "SIL Open Font License",
            },
            "Fira Code": {
                "description": "Popular programming font with extensive ligatures",
                "ligatures": True,
                "download": "https://github.com/tonsky/FiraCode/releases",
                "license": "SIL Open Font License",
            },
            "JetBrains Mono": {
                "description": "Font designed by JetBrains for developers",
                "ligatures": True,
                "download": "https://www.jetbrains.com/lp/mono/",
                "license": "SIL Open Font License",
            },
            "Consolas": {
                "description": "Microsoft's classic monospaced font (Windows built-in)",
                "ligatures": False,
                "download": "Pre-installed on Windows",
                "license": "Microsoft",
            },
        }

        # Check which ones are installed
        for font_name in recommended:
            recommended[font_name]["installed"] = FontDetector.is_font_installed(font_name)

        return recommended
