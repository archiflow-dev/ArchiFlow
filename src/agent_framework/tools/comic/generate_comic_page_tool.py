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
            # Visual Style Enhancement Parameters
            "art_style": {
                "type": "string",
                "description": "Overall art style description (visual aesthetic, influences, technique)"
            },
            "global_color_palette": {
                "type": "object",
                "description": "Global color palette organized by category with hex codes",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "global_lighting": {
                "type": "string",
                "description": "Global lighting philosophy (religious, natural, high contrast, bioluminescent, digital)"
            },
            "character_specs": {
                "type": "array",
                "description": "Detailed character specifications with visual details",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "colors": {"type": "object"},
                        "special_effects": {"type": "array", "items": {"type": "string"}},
                        "expression_evolution": {"type": "object"}
                    }
                }
            },
            "per_panel_visuals": {
                "type": "array",
                "description": "Per-panel visual specifications (color, lighting, effects, composition)",
                "items": {
                    "type": "object",
                    "properties": {
                        "panel_number": {"type": "integer"},
                        "color_palette": {"type": "object"},
                        "lighting": {"type": "array", "items": {"type": "string"}},
                        "special_effects": {"type": "array", "items": {"type": "string"}},
                        "composition": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            # Advanced layout parameters
            "transition_type": {
                "type": "string",
                "enum": ["moment-to-moment", "action-to-action", "subject-to-subject", "scene-to-scene", "aspect-to-aspect", "non-sequitur"],
                "description": "McCloud's panel transition type for pacing and flow control"
            },
            "gutter_type": {
                "type": "string",
                "enum": ["standard", "wide", "none", "variable"],
                "description": "Gutter type affecting pacing (standard=normal, wide=time pause, none=continuous, variable=custom)"
            },
            "layout_system": {
                "type": "string",
                "enum": ["row-based", "column-based", "diagonal", "z-path", "combination", "splash"],
                "description": "Layout system for panel arrangement and reading flow"
            },
            "special_techniques": {
                "type": "string",
                "description": "Special panel techniques (e.g., 'inset', 'overlapping', 'broken_frame', 'borderless', 'widescreen')"
            },
            "emphasis_panels": {
                "type": "string",
                "description": "Comma-separated panel numbers that are emphasized (e.g., '1,3' for panels 1 and 3)"
            },
            # Existing parameters
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
        page_number: int,
        # Visual style enhancement parameters
        art_style: Optional[str] = None,
        global_color_palette: Optional[Dict[str, List[str]]] = None,
        global_lighting: Optional[str] = None,
        character_specs: Optional[List[Dict[str, Any]]] = None,
        per_panel_visuals: Optional[List[Dict[str, Any]]] = None,
        # Advanced layout parameters
        transition_type: Optional[str] = None,
        gutter_type: Optional[str] = None,
        layout_system: Optional[str] = None,
        special_techniques: Optional[str] = None,
        emphasis_panels: Optional[str] = None
    ) -> str:
        """
        Build a comprehensive prompt for direct page generation.

        Args:
            panels: List of panel specifications
            layout: Layout pattern (e.g., "2x3")
            page_number: Page number
            art_style: Overall art style description
            global_color_palette: Global color palette with hex codes
            global_lighting: Global lighting philosophy
            character_specs: Character visual specifications
            per_panel_visuals: Per-panel visual specifications
            transition_type: McCloud's panel transition type
            gutter_type: Gutter type for pacing control
            layout_system: Layout system for panel arrangement
            special_techniques: Special panel techniques
            emphasis_panels: Comma-separated panel numbers that are emphasized

        Returns:
            Combined prompt for the entire page
        """
        cols, rows = self._parse_layout(layout)

        prompt_parts = []

        # ===== OVERALL ART STYLE =====
        if art_style:
            prompt_parts.append("=== OVERALL ART STYLE ===")
            prompt_parts.append(art_style)
            prompt_parts.append("")

        # ===== GLOBAL COLOR PALETTE =====
        if global_color_palette:
            prompt_parts.append("=== GLOBAL COLOR PALETTE ===")
            for category, colors in global_color_palette.items():
                color_list = colors if isinstance(colors, list) else [colors]
                prompt_parts.append(f"- {category}: {', '.join(color_list)}")
            prompt_parts.append("")

        # ===== GLOBAL LIGHTING PHILOSOPHY =====
        if global_lighting:
            prompt_parts.append("=== GLOBAL LIGHTING PHILOSOPHY ===")
            prompt_parts.append(global_lighting)
            prompt_parts.append("")

        # ===== CHARACTER SPECIFICATIONS =====
        if character_specs:
            prompt_parts.append("=== CHARACTER SPECIFICATIONS ===")
            for char_spec in character_specs:
                name = char_spec.get('name', 'Unknown')
                prompt_parts.append(f"\nCharacter: {name}")

                # Handle both 'description' and 'appearance' fields
                if 'description' in char_spec:
                    prompt_parts.append(f"Form/Description: {char_spec['description']}")
                elif 'appearance' in char_spec:
                    prompt_parts.append(f"Form/Appearance: {char_spec['appearance']}")

                if 'colors' in char_spec:
                    colors_data = char_spec['colors']
                    color_parts = []
                    # Handle both dict format and list format
                    if isinstance(colors_data, dict):
                        for color_category, color_values in colors_data.items():
                            if isinstance(color_values, list):
                                color_parts.append(f"{color_values[0]}")
                            else:
                                color_parts.append(str(color_values))
                    elif isinstance(colors_data, list):
                        # Simple list of colors
                        color_parts = colors_data
                    if color_parts:
                        prompt_parts.append(f"Colors: {', '.join(color_parts)}")

                if 'special_effects' in char_spec and char_spec['special_effects']:
                    # Handle both string and list formats
                    effects = char_spec['special_effects']
                    if isinstance(effects, list):
                        prompt_parts.append(f"Special Effects: {', '.join(effects)}")
                    else:
                        prompt_parts.append(f"Special Effects: {effects}")

                if 'expression_evolution' in char_spec:
                    evo = char_spec['expression_evolution']
                    if isinstance(evo, dict):
                        evo_parts = []
                        for page_range, expression in evo.items():
                            evo_parts.append(f"{page_range}: {expression}")
                        if evo_parts:
                            prompt_parts.append(f"Expression Evolution: {'; '.join(evo_parts)}")
            prompt_parts.append("")

        # ===== PAGE LAYOUT =====
        prompt_parts.append(f"=== PAGE {page_number} ===")
        prompt_parts.append(f"Layout: {layout}")
        if transition_type:
            prompt_parts.append(f"Transition: {transition_type}")
        if gutter_type:
            prompt_parts.append(f"Gutter: {gutter_type}")
        if layout_system:
            prompt_parts.append(f"Layout System: {layout_system}")
        if special_techniques:
            prompt_parts.append(f"Special Techniques: {special_techniques}")
        prompt_parts.append("")

        # ===== PANELS =====
        prompt_parts.extend([
            f"Create a comic book page {page_number} with {len(panels)} panels arranged in a {cols}x{rows} grid layout ({cols} columns, {rows} rows).",
            "",
            "CRITICAL REQUIREMENTS:",
            "- Comic book style with clear panel borders/gutters between each panel",
            "- Professional comic book layout with consistent spacing",
            "- Each panel should be clearly separated and distinct",
            f"- Total of {len(panels)} panels in a grid arrangement",
            "",
            "PANELS (in reading order, left to right, top to bottom):",
            ""
        ])

        # Parse emphasis panels if provided
        emphasis_set = set()
        if emphasis_panels:
            emphasis_set = set(int(p.strip()) for p in emphasis_panels.split(',') if p.strip().isdigit())

        # Build a lookup for per-panel visuals
        panel_visuals_lookup = {}
        if per_panel_visuals:
            for pv in per_panel_visuals:
                panel_visuals_lookup[pv['panel_number']] = pv

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

            # Mark if emphasized
            emphasis_marker = " [EMPHASIS - LARGER]" if panel_num in emphasis_set else ""

            prompt_parts.append(f"Panel {panel_num} (Row {row + 1}, Column {col + 1}){emphasis_marker} - {panel_type.upper()}:")

            # ===== PANEL NOTE (Special Layout Instructions) =====
            # Check for panel_note first - this should come BEFORE everything else
            panel_note = panel_spec.get('panel_note')
            if panel_note:
                prompt_parts.append(f"  **SPECIAL LAYOUT: {panel_note}**")

            prompt_parts.append(f"  Scene: {prompt}")

            if characters:
                prompt_parts.append(f"  Characters: {', '.join(characters)}")

            if dialogue:
                prompt_parts.append(f"  Dialogue: {dialogue}")

            if visual_details:
                prompt_parts.append(f"  Visual: {visual_details}")

            # ===== PER-PANEL VISUAL DETAILS =====
            panel_visual = panel_visuals_lookup.get(panel_num)
            if panel_visual:
                # Color Palette
                if 'color_palette' in panel_visual:
                    cp = panel_visual['color_palette']
                    if isinstance(cp, dict):
                        prompt_parts.append("  COLOR PALETTE:")
                        for category, colors in cp.items():
                            color_list = colors if isinstance(colors, list) else [colors]
                            prompt_parts.append(f"    - {category}: {', '.join(color_list)}")

                # Lighting
                if 'lighting' in panel_visual and panel_visual['lighting']:
                    prompt_parts.append("  LIGHTING:")
                    for lighting in panel_visual['lighting']:
                        prompt_parts.append(f"    - {lighting}")

                # Special Effects
                if 'special_effects' in panel_visual and panel_visual['special_effects']:
                    prompt_parts.append("  SPECIAL EFFECTS:")
                    for effect in panel_visual['special_effects']:
                        prompt_parts.append(f"    - {effect}")

                # Composition
                if 'composition' in panel_visual and panel_visual['composition']:
                    prompt_parts.append("  COMPOSITION:")
                    for comp in panel_visual['composition']:
                        prompt_parts.append(f"    - {comp}")

            prompt_parts.append("")

        # ===== ADVANCED LAYOUT INFORMATION =====
        layout_guidance = []

        # Transition type guidance
        if transition_type:
            transition_desc = {
                "moment-to-moment": "Small changes between moments. Use for subtle character development or detailed action breakdown.",
                "action-to-action": "Dynamic action progression. Clear cause-and-effect between actions. Fast pacing.",
                "subject-to-subject": "Shift focus between subjects/characters while staying in same scene.",
                "scene-to-scene": "Significant transitions between different scenes or locations. Time/space jump.",
                "aspect-to-aspect": "Explore different aspects of same place/idea/mood. Atmospheric and contemplative.",
                "non-sequitur": "No logical relationship - for artistic effect, dream sequences, or juxtaposition."
            }
            if transition_type in transition_desc:
                layout_guidance.append(f"TRANSITION TYPE: {transition_type.upper()}")
                layout_guidance.append(f"  {transition_desc[transition_type]}")

        # Gutter type guidance
        if gutter_type:
            gutter_desc = {
                "standard": "Standard gutters for normal reading pace.",
                "wide": "WIDE gutters between panels to indicate time pause, reflection, or significant scene change.",
                "none": "NO visible gutters - panels flow continuously indicating simultaneous events or fast action.",
                "variable": "Variable gutter widths - use strategically to control pacing and emphasis."
            }
            if gutter_type in gutter_desc:
                layout_guidance.append(f"GUTTERS: {gutter_desc[gutter_type]}")

        # Layout system guidance
        if layout_system:
            layout_sys_desc = {
                "row-based": "Row-based layout - panels arranged in horizontal rows for traditional flow.",
                "column-based": "Column-based layout - panels arranged in vertical columns.",
                "diagonal": "DIAGONAL layout - panels arranged diagonally for dynamic action flow and energy.",
                "z-path": "Z-PATH layout - panels follow natural Z-shaped reading pattern (top-left → top-right → bottom-left → bottom-right).",
                "combination": "Combination layout - creative mix of grid and dynamic arrangements.",
                "splash": "SPLASH page layout - one or more dominant panels taking significant space."
            }
            if layout_system in layout_sys_desc:
                layout_guidance.append(f"LAYOUT SYSTEM: {layout_sys_desc[layout_system]}")

        # Special techniques
        if special_techniques:
            technique_desc = {
                "inset": "Inset panels - smaller panels within larger panels for details or flashbacks.",
                "overlapping": "OVERLAPPING panels - panels overlap each other for layered storytelling.",
                "broken_frame": "BROKEN frames - panel borders are irregular/broken for dramatic impact.",
                "borderless": "BORDERLESS panels - no visible borders, panels bleed into each other.",
                "widescreen": "WIDESCREEN panels - extra-wide horizontal panels for cinematic scope."
            }
            for tech in special_techniques.lower().replace(" ", "").split(","):
                if tech in technique_desc:
                    layout_guidance.append(f"TECHNIQUE: {technique_desc[tech]}")

        # Add layout guidance section
        if layout_guidance:
            prompt_parts.append("LAYOUT & PACING:")
            prompt_parts.extend(layout_guidance)
            prompt_parts.append("")

        # Default style (if no art_style provided)
        if not art_style:
            prompt_parts.extend([
                "STYLE:",
                "- Professional comic book art with bold lines and clear panel composition",
                "- Dynamic angles and engaging visual storytelling",
                "- Consistent art style across all panels",
                "- Clear visual flow from panel to panel",
                "",
            ])

        prompt_parts.extend([
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
        # Visual style enhancement parameters
        art_style: Optional[str] = None,
        global_color_palette: Optional[Dict[str, List[str]]] = None,
        global_lighting: Optional[str] = None,
        character_specs: Optional[List[Dict[str, Any]]] = None,
        per_panel_visuals: Optional[List[Dict[str, Any]]] = None,
        # Advanced layout parameters
        transition_type: Optional[str] = None,
        gutter_type: Optional[str] = None,
        layout_system: Optional[str] = None,
        special_techniques: Optional[str] = None,
        emphasis_panels: Optional[str] = None,
        # Existing parameters
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
            art_style: Overall art style description
            global_color_palette: Global color palette with hex codes
            global_lighting: Global lighting philosophy
            character_specs: Character visual specifications
            per_panel_visuals: Per-panel visual specifications
            transition_type: McCloud's panel transition type
            gutter_type: Gutter type for pacing control
            layout_system: Layout system for panel arrangement
            special_techniques: Special panel techniques
            emphasis_panels: Comma-separated panel numbers that are emphasized
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

                combined_prompt = self._build_direct_page_prompt(
                    panels, layout, page_number,
                    art_style=art_style,
                    global_color_palette=global_color_palette,
                    global_lighting=global_lighting,
                    character_specs=character_specs,
                    per_panel_visuals=per_panel_visuals,
                    transition_type=transition_type,
                    gutter_type=gutter_type,
                    layout_system=layout_system,
                    special_techniques=special_techniques,
                    emphasis_panels=emphasis_panels
                )
                aspect_ratio = self._get_closest_aspect_ratio(page_width, page_height)

                # Collect character references
                ref_images = []
                unique_chars = set()
                for panel in panels:
                    if 'characters' in panel and panel['characters']:
                        for char in panel['characters']:
                            unique_chars.add(char)

                if unique_chars:
                    logger.info(f"Collecting references for characters: {unique_chars}")
                    # Try to find reference images
                    # Default location
                    if self.execution_context and self.execution_context.working_directory:
                        base_dir = self.execution_context.working_directory
                    else:
                        base_dir = os.path.join("data", "sessions", session_id)

                    ref_dir = os.path.join(base_dir, "character_refs")

                    for char_name in unique_chars:
                        # Try case variations
                        names_to_check = [
                            char_name.upper(),
                            char_name.lower(),
                            char_name.title(),
                            char_name
                        ]

                        found = False
                        for name in names_to_check:
                            path = os.path.join(ref_dir, f"{name}.png")
                            if os.path.exists(path):
                                try:
                                    img = Image.open(path)
                                    ref_images.append(img)
                                    logger.info(f"Loaded reference for {char_name}")
                                    found = True
                                    break
                                except Exception as e:
                                    logger.warning(f"Failed to load ref for {char_name}: {e}")

                        if not found:
                            logger.info(f"No reference image found for {char_name}")

                # Enhance prompt with reference instructions
                if ref_images:
                    combined_prompt += "\n\nCRITICAL INSTRUCTION: references provided. " \
                                     "The attached images are character reference sheets for the characters in this page. " \
                                     "You MUST maintain strict visual consistency with these references " \
                                     "for all panels. Match their facial features, clothing, and style exactly " \
                                     "wherever they appear on the page."

                logger.info(f"Generating complete page {page_number} directly with aspect ratio {aspect_ratio} and {len(ref_images)} refs")
                logger.debug(f"Combined prompt: {combined_prompt[:200]}...")

                # Generate the full page image with logging
                image = self.image_provider.generate_image(
                    prompt=combined_prompt,
                    aspect_ratio=aspect_ratio,
                    resolution="2K",
                    ref_images=ref_images if ref_images else None,
                    session_id=session_id,
                    output_dir=pages_dir
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
