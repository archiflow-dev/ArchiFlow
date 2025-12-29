"""
Generate Comic Page Tool.

This tool generates a complete comic page with multiple panels
stitched together according to the layout specified in the spec.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import Field

from ..tool_base import BaseTool, ToolResult

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

# Environment variable to control page generation mode
# Options: "direct" (single image generation) or "stitched" (individual panels)
DEFAULT_PAGE_MODE = os.getenv("COMIC_PAGE_GENERATION_MODE", "direct").lower()


class GenerateComicPageTool(BaseTool):
    """
    Tool for generating a complete comic page.

    Generates a full page with multiple panels stitched together
    according to the specified layout.
    """

    name: str = "generate_comic_page"
    description: str = "Generate a complete comic page with multiple panels in specified layout"

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID for organizing images"
            },
            "page_number": {
                "type": "integer",
                "description": "Page number (1-based)"
            },
            "panels": {
                "type": "array",
                "description": "List of panel specifications",
                "items": {
                    "type": "object",
                    "properties": {
                        "panel_number": {"type": "integer"},
                        "prompt": {"type": "string"},
                        "panel_type": {"type": "string"},
                        "characters": {"type": "array", "items": {"type": "string"}},
                        "dialogue": {"type": "string"},
                        "visual_details": {"type": "string"}
                    },
                    "required": ["panel_number", "prompt", "panel_type"]
                }
            },
            "layout": {
                "type": "string",
                "description": "Layout pattern: '2x3' (2 columns, 3 rows), '3x2', etc.",
                "default": "2x3"
            },
            "page_size": {
                "type": "string",
                "description": "Page size in pixels: '2048x2730' (standard comic book)",
                "default": "2048x2730"
            },
            "margin": {
                "type": "integer",
                "description": "Margin between panels in pixels",
                "default": 20
            },
            "generation_mode": {
                "type": "string",
                "description": "Generation mode: 'direct' (single image) or 'stitched' (individual panels)",
                "enum": ["direct", "stitched"],
                "default": "direct"
            }
        },
        "required": ["session_id", "page_number", "panels"]
    }

    image_provider: Optional[Any] = Field(default=None, exclude=True)

    def __init__(self, image_provider: Optional[Any] = None, **data):
        """Initialize the GenerateComicPageTool."""
        if image_provider is not None:
            data['image_provider'] = image_provider
        elif 'image_provider' not in data:
            # Try to get from environment
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if google_api_key:
                try:
                    from agent_framework.llm.google_image_provider import GoogleImageProvider
                    data['image_provider'] = GoogleImageProvider(api_key=google_api_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize image provider: {e}")
                    data['image_provider'] = None

        super().__init__(**data)

    def _parse_layout(self, layout: str) -> tuple:
        """Parse layout string like '2x3' to (cols, rows)."""
        parts = layout.lower().split('x')
        if len(parts) != 2:
            return (2, 3)  # Default
        try:
            cols = int(parts[0])
            rows = int(parts[1])
            return (cols, rows)
        except ValueError:
            return (2, 3)  # Default

    def _parse_page_size(self, page_size: str) -> tuple:
        """Parse page size string like '2048x2730' to (width, height)."""
        parts = page_size.lower().split('x')
        if len(parts) != 2:
            return (2048, 2730)  # Default comic book size
        try:
            width = int(parts[0])
            height = int(parts[1])
            return (width, height)
        except ValueError:
            return (2048, 2730)

    def _get_closest_aspect_ratio(self, width: int, height: int) -> str:
        """
        Get the closest valid aspect ratio for Google's API.

        Valid ratios: '1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'
        """
        # Calculate target ratio
        target_ratio = width / height

        # Valid aspect ratios and their numeric values
        valid_ratios = {
            "1:1": 1.0,
            "2:3": 2/3,
            "3:2": 3/2,
            "3:4": 3/4,
            "4:3": 4/3,
            "4:5": 4/5,
            "5:4": 5/4,
            "9:16": 9/16,
            "16:9": 16/9,
            "21:9": 21/9
        }

        # Find closest ratio
        closest_ratio = min(valid_ratios.items(), key=lambda x: abs(x[1] - target_ratio))
        return closest_ratio[0]

    def _build_direct_page_prompt(
        self,
        panels: List[Dict[str, Any]],
        layout: str,
        page_number: int
    ) -> str:
        """
        Build a comprehensive prompt for direct page generation.

        Args:
            panels: List of panel specifications
            layout: Layout pattern (e.g., "2x3")
            page_number: Page number

        Returns:
            Combined prompt for the entire page
        """
        cols, rows = self._parse_layout(layout)

        prompt_parts = [
            f"Create a complete comic book page {page_number} with {len(panels)} panels arranged in a {cols}x{rows} grid layout ({cols} columns, {rows} rows).",
            "",
            "CRITICAL REQUIREMENTS:",
            "- Comic book style with clear panel borders/gutters between each panel",
            "- Professional comic book layout with consistent spacing",
            "- Each panel should be clearly separated and distinct",
            f"- Total of {len(panels)} panels in a grid arrangement",
            "",
            "PANELS (in reading order, left to right, top to bottom):",
            ""
        ]

        # Add each panel description
        for i, panel_spec in enumerate(panels):
            panel_num = panel_spec.get('panel_number', i + 1)
            panel_type = panel_spec.get('panel_type', 'scene')
            prompt = panel_spec.get('prompt', '')
            characters = panel_spec.get('characters', [])
            dialogue = panel_spec.get('dialogue', '')
            visual_details = panel_spec.get('visual_details', '')

            # Calculate grid position
            row = i // cols
            col = i % cols

            prompt_parts.append(f"Panel {panel_num} (Row {row + 1}, Column {col + 1}) - {panel_type.upper()}:")
            prompt_parts.append(f"  Scene: {prompt}")

            if characters:
                prompt_parts.append(f"  Characters: {', '.join(characters)}")

            if dialogue:
                prompt_parts.append(f"  Dialogue: {dialogue}")

            if visual_details:
                prompt_parts.append(f"  Visual: {visual_details}")

            prompt_parts.append("")

        prompt_parts.extend([
            "STYLE:",
            "- Professional comic book art with bold lines and clear panel composition",
            "- Dynamic angles and engaging visual storytelling",
            "- Consistent art style across all panels",
            "- Clear visual flow from panel to panel",
            "",
            "LAYOUT:",
            f"- Arranged in {cols} columns and {rows} rows",
            "- Clear gutters (white space) between panels",
            "- Professional comic book page composition"
        ])

        return "\n".join(prompt_parts)

    async def execute(
        self,
        session_id: str,
        page_number: int,
        panels: List[Dict[str, Any]],
        layout: str = "2x3",
        page_size: str = "2048x2730",
        margin: int = 20,
        generation_mode: str = None,
        **kwargs
    ) -> ToolResult:
        """
        Generate a complete comic page.

        Args:
            session_id: Session identifier
            page_number: Page number (1-based)
            panels: List of panel specifications
            layout: Layout pattern (e.g., '2x3' for 2 columns, 3 rows)
            page_size: Page size in pixels
            margin: Margin between panels in pixels
            generation_mode: Generation mode ('direct' or 'stitched').
                           Defaults to COMIC_PAGE_GENERATION_MODE env var or 'direct'.
                           - 'direct': Generate entire page as single image (faster, better composition)
                           - 'stitched': Generate individual panels and stitch together

        Returns:
            ToolResult with page image path or error
        """
        if not PIL_AVAILABLE:
            return self.fail_response(
                "PIL (Pillow) is not installed. Install with: pip install Pillow"
            )

        if not self.image_provider:
            return self.fail_response(
                "No image provider available. Please configure GOOGLE_API_KEY."
            )

        try:
            # Parse layout and page size
            cols, rows = self._parse_layout(layout)
            page_width, page_height = self._parse_page_size(page_size)

            # Determine generation mode
            mode = generation_mode or DEFAULT_PAGE_MODE
            logger.info(f"Generating page {page_number} with {len(panels)} panels in {layout} layout using {mode} mode")

            # Calculate base directory for output
            base_dir = None
            if self.execution_context and self.execution_context.working_directory:
                base_dir = self.execution_context.working_directory
            else:
                base_dir = os.path.join("data", "sessions", session_id)

            pages_dir = os.path.join(base_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)

            page_filename = f"page_{page_number:02d}.png"
            page_path = os.path.join(pages_dir, page_filename)

            if mode == "direct":
                # Direct mode - generate entire page as single image
                logger.info(f"Using DIRECT generation mode - creating complete page in one image")

                combined_prompt = self._build_direct_page_prompt(panels, layout, page_number)
                aspect_ratio = self._get_closest_aspect_ratio(page_width, page_height)

                logger.info(f"Generating complete page {page_number} directly with aspect ratio {aspect_ratio}")
                logger.debug(f"Combined prompt: {combined_prompt[:200]}...")

                # Generate the full page image
                image = self.image_provider.generate_image(
                    prompt=combined_prompt,
                    aspect_ratio=aspect_ratio,
                    resolution="2K"
                )

                # Handle PIL image
                if hasattr(image, '_pil_image'):
                    pil_image = image._pil_image
                else:
                    pil_image = image

                # Resize to exact page dimensions if needed
                if pil_image.size != (page_width, page_height):
                    pil_image = pil_image.resize((page_width, page_height), Image.Resampling.LANCZOS)

                pil_image.save(page_path, 'PNG', optimize=True)

                logger.info(f"Complete page saved to: {page_path}")

                # Get file size
                file_size = os.path.getsize(page_path) / (1024 * 1024)  # MB

                return self.success_response({
                    "success": True,
                    "page_path": page_path,
                    "page_number": page_number,
                    "panel_count": len(panels),
                    "layout": layout,
                    "generation_mode": "direct",
                    "file_size_mb": round(file_size, 2)
                })

            elif mode == "stitched":
                # Stitched mode - generate individual panels and stitch together
                logger.info(f"Using STITCHED generation mode - creating panels individually and stitching")

                # Calculate panel dimensions
                panel_width = (page_width - margin * (cols + 1)) // cols
                panel_height = (page_height - margin * (rows + 1)) // rows

                logger.info(f"Page: {page_width}x{page_height}, Panels: {panel_width}x{panel_height}")

                # Create blank page
                page_image = Image.new('RGB', (page_width, page_height), color=(255, 255, 255))

                # Generate and place each panel
                from agent_framework.tools.comic.generate_comic_panel_tool import GenerateComicPanelTool
                panel_tool = GenerateComicPanelTool(image_provider=self.image_provider)

                # Copy execution context
                if hasattr(self, 'execution_context'):
                    panel_tool.execution_context = self.execution_context

                for i, panel_spec in enumerate(panels):
                    # Calculate position in grid
                    row = i // cols
                    col = i % cols

                    # Skip if we've exceeded grid capacity
                    if row >= rows:
                        logger.warning(f"Panel {i+1} exceeds layout capacity, skipping")
                        continue

                    logger.info(f"Generating panel {panel_spec['panel_number']} (position {row},{col})")

                    # Get closest valid aspect ratio for the panel dimensions
                    aspect_ratio = self._get_closest_aspect_ratio(panel_width, panel_height)
                    logger.info(f"Using aspect ratio {aspect_ratio} for panel ({panel_width}x{panel_height})")

                    # Generate individual panel
                    result = await panel_tool.execute(
                        prompt=panel_spec['prompt'],
                        panel_type=panel_spec['panel_type'],
                        session_id=session_id,
                        page_number=page_number,
                        panel_number=panel_spec['panel_number'],
                        character_names=panel_spec.get('characters', []),
                        dialogue=panel_spec.get('dialogue'),
                        visual_details=panel_spec.get('visual_details'),
                        aspect_ratio=aspect_ratio,
                    )

                    if result.error:
                        logger.error(f"Failed to generate panel {panel_spec['panel_number']}: {result.error}")
                        continue

                    # Load generated panel
                    panel_data = json.loads(result.output)
                    panel_path = panel_data['file_path']  # GenerateComicPanelTool returns 'file_path'

                    panel_img = Image.open(panel_path)

                    # Resize to exact panel dimensions
                    panel_img = panel_img.resize((panel_width, panel_height), Image.Resampling.LANCZOS)

                    # Calculate position on page
                    x = margin + col * (panel_width + margin)
                    y = margin + row * (panel_height + margin)

                    # Paste panel onto page
                    page_image.paste(panel_img, (x, y))

                    logger.info(f"  ✓ Panel {panel_spec['panel_number']} placed at ({x}, {y})")

                # Save complete page
                page_image.save(page_path, 'PNG', optimize=True)

                logger.info(f"Complete page saved to: {page_path}")

                # Get file size
                file_size = os.path.getsize(page_path) / (1024 * 1024)  # MB

                return self.success_response({
                    "success": True,
                    "page_path": page_path,
                    "page_number": page_number,
                    "panel_count": len(panels),
                    "layout": layout,
                    "generation_mode": "stitched",
                    "file_size_mb": round(file_size, 2)
                })
            else:
                return self.fail_response(f"Invalid generation mode: {mode}. Must be 'direct' or 'stitched'.")

        except Exception as e:
            logger.error(f"Page generation failed: {e}", exc_info=True)
            return self.fail_response(f"Page generation failed: {str(e)}")
