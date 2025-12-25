"""Clipboard tool for copying text to system clipboard."""
import logging
from typing import Dict, Optional, Any

from pydantic import Field

from .tool_base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ClipboardTool(BaseTool):
    """Tool for copying text to the system clipboard (cross-platform).

    Uses pyperclip library for cross-platform clipboard support.
    Gracefully degrades if pyperclip is not installed.
    """

    name: str = "copy_to_clipboard"
    description: str = (
        "Copy text to the system clipboard for easy pasting. "
        "Works across Windows, macOS, and Linux. "
        "Use this to make refined prompts easily accessible to users. "
        "Returns success message if copied successfully."
    )

    parameters: Dict = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to copy to clipboard"
            },
            "description": {
                "type": "string",
                "description": "Optional description of what's being copied (for user confirmation)",
                "default": ""
            }
        },
        "required": ["text"]
    }

    async def execute(self, text: str, description: str = "") -> ToolResult:
        """Copy text to system clipboard.

        Args:
            text: Text to copy to clipboard
            description: Optional description for user feedback

        Returns:
            ToolResult with success message or error
        """
        try:
            # Import here to make it an optional dependency
            import pyperclip

            # Copy to clipboard
            pyperclip.copy(text)

            # Verify copy worked by reading back
            copied = pyperclip.paste()
            if copied == text:
                msg = "✓ Copied to clipboard successfully"
                if description:
                    msg += f": {description}"

                logger.info(f"Copied to clipboard: {len(text)} characters")
                return self.success_response(msg)
            else:
                logger.warning("Clipboard copy verification failed")
                return self.fail_response(
                    "Clipboard copy verification failed. Text may not be copied correctly."
                )

        except ImportError:
            logger.warning("pyperclip library not installed - clipboard copy disabled")
            return self.fail_response(
                "Clipboard feature not available. Install pyperclip: pip install pyperclip"
            )
        except Exception as e:
            logger.error(f"Clipboard copy failed: {e}", exc_info=True)
            return self.fail_response(f"Failed to copy to clipboard: {str(e)}")
