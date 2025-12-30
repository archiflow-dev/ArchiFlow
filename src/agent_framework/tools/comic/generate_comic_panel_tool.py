"""
Generate Comic Panel Tool for Comic Agent.

This tool generates images for comic book panels using the configured
image provider (Google Image Provider by default). It handles panel numbering,
character references, and establishes consistent character appearance across panels.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from PIL import Image
from pydantic import Field

from ..tool_base import BaseTool, ToolResult
from ...llm.image_provider_base import ImageProvider
from ...llm.google_image_provider import GoogleImageProvider

# Set up logger for this module
logger = logging.getLogger(__name__)


class GenerateComicPanelTool(BaseTool):
    """
    Tool for generating comic book panel images.

    This tool uses an image provider to generate images for comic panels.
    It supports character reference images for consistent character appearance
    across all panels in the comic.
    """

    name: str = "generate_comic_panel"
    description: str = "Generate an image for a comic book panel or character reference sheet."

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the panel or character to generate"
            },
            "panel_type": {
                "type": "string",
                "enum": ["character_reference", "establishing_shot", "action", "dialogue", "close_up", "transition"],
                "description": "Type of panel: character_reference (for character sheets), establishing_shot, action, dialogue, close_up, or transition"
            },
            "page_number": {
                "type": "integer",
                "description": "Page number (1-based, not needed for character references)",
                "minimum": 1
            },
            "panel_number": {
                "type": "integer",
                "description": "Panel number within the page (1-based, not needed for character references)",
                "minimum": 1
            },
            "character_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of characters appearing in this panel"
            },
            "dialogue": {
                "type": "string",
                "description": "Dialogue or text to be shown in the panel"
            },
            "action": {
                "type": "string",
                "description": "Action happening in the panel"
            },
            "visual_details": {
                "type": "string",
                "description": "Detailed visual description (composition, lighting, mood, camera angle)"
            },
            "character_reference": {
                "type": "string",
                "description": "Character name to use as reference (loads from character_refs/ directory). Supports variant syntax: 'CHARACTER_variant' (e.g., 'ARIA_planetary')"
            },
            "variant": {
                "type": "string",
                "description": "Optional variant identifier for character references. Use for alternate forms (e.g., 'planetary', 'datastream') or costumes (e.g., 'casual', 'formal'). Creates distinct filenames like 'ARIA_planetary.png'. Omit for primary/default form."
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
            "emphasis_panel": {
                "type": "boolean",
                "description": "Whether this panel is emphasized (larger or more prominent)"
            },
            # Visual style enhancement parameters
            "art_style": {
                "type": "string",
                "description": "Overall art style description (visual aesthetic, influences, technique)"
            },
            "color_palette": {
                "type": "object",
                "description": "Color palette for this panel with hex codes",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "lighting": {
                "type": "array",
                "description": "Lighting descriptions for this panel",
                "items": {"type": "string"}
            },
            "special_effects": {
                "type": "array",
                "description": "Special effects for this panel (glitch, particles, etc.)",
                "items": {"type": "string"}
            },
            "composition": {
                "type": "array",
                "description": "Composition notes (angles, framing, focus)",
                "items": {"type": "string"}
            },
            # Existing parameters
            "session_id": {
                "type": "string",
                "description": "Session ID for organizing images"
            },
            "output_dir": {
                "type": "string",
                "description": "Output directory (default: data/sessions/{session_id}/panels or character_refs)"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Image aspect ratio",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                "default": "4:3"
            },
            "resolution": {
                "type": "string",
                "description": "Image resolution",
                "enum": ["1K", "2K", "4K"],
                "default": "2K"
            }
        },
        "required": ["prompt", "panel_type", "session_id"]
    }

    image_provider: Optional[ImageProvider] = Field(default=None, exclude=True)
    character_references: Dict[str, Image.Image] = Field(default_factory=dict, exclude=True)

    def __init__(self, image_provider: Optional[ImageProvider] = None, **data):
        """
        Initialize the GenerateComicPanelTool.

        Args:
            image_provider: Image provider to use for generation. If None, creates Google provider.
        """
        # Set image_provider in the data before calling super().__init__
        if image_provider is not None:
            data['image_provider'] = image_provider
        elif 'image_provider' not in data:
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                logger.warning("GOOGLE_API_KEY not found in environment. Image generation may fail.")
            try:
                data['image_provider'] = GoogleImageProvider(api_key=google_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google Image Provider: {e}")
                data['image_provider'] = None

        # Initialize character references dict
        if 'character_references' not in data:
            data['character_references'] = {}

        super().__init__(**data)

    def _build_comic_prompt(
        self,
        prompt: str,
        panel_type: str,
        character_names: Optional[List[str]] = None,
        dialogue: Optional[str] = None,
        action: Optional[str] = None,
        visual_details: Optional[str] = None,
        page_number: Optional[int] = None,
        panel_number: Optional[int] = None,
        transition_type: Optional[str] = None,
        gutter_type: Optional[str] = None,
        layout_system: Optional[str] = None,
        special_techniques: Optional[str] = None,
        emphasis_panel: Optional[bool] = None,
        # Visual style enhancement parameters
        art_style: Optional[str] = None,
        color_palette: Optional[Dict[str, List[str]]] = None,
        lighting: Optional[List[str]] = None,
        special_effects: Optional[List[str]] = None,
        composition: Optional[List[str]] = None
    ) -> str:
        """
        Build an enhanced prompt for comic panel generation.

        Args:
            prompt: Basic description
            panel_type: Type of panel
            character_names: Characters in the panel
            dialogue: Dialogue text
            action: Action description
            visual_details: Visual composition details
            page_number: Page number
            panel_number: Panel number
            transition_type: McCloud's panel transition type
            gutter_type: Gutter type for pacing control
            layout_system: Layout system for panel arrangement
            special_techniques: Special panel techniques
            emphasis_panel: Whether this panel is emphasized
            art_style: Overall art style description
            color_palette: Color palette with hex codes
            lighting: Lighting descriptions
            special_effects: Special effects (glitch, particles, etc.)
            composition: Composition notes (angles, framing, focus)

        Returns:
            Enhanced prompt for image generation
        """
        parts = []

        # ===== OVERALL ART STYLE =====
        if art_style:
            parts.append("=== ART STYLE ===")
            parts.append(art_style)
            parts.append("")

        # ===== COLOR PALETTE =====
        if color_palette:
            parts.append("=== COLOR PALETTE ===")
            for category, colors in color_palette.items():
                color_list = colors if isinstance(colors, list) else [colors]
                parts.append(f"- {category}: {', '.join(color_list)}")
            parts.append("")

        # Add panel type context
        if panel_type == "character_reference":
            parts.append("Character Reference Sheet: Full-body character design with consistent features.")
        else:
            parts.append(f"Comic Book Panel - {panel_type.replace('_', ' ').title()}")

        # Add main prompt
        parts.append(f"Scene: {prompt}")

        # Add character information
        if character_names and len(character_names) > 0:
            chars = ", ".join(character_names)
            parts.append(f"Characters: {chars}")

        # Add action if provided
        if action:
            parts.append(f"Action: {action}")

        # Add dialogue context (not rendered, just for composition)
        if dialogue:
            parts.append(f"Dialogue (for composition): {dialogue}")

        # Add visual details
        if visual_details:
            parts.append(f"Visual Details: {visual_details}")

        # Add panel context
        if page_number and panel_number:
            parts.append(f"Context: Page {page_number}, Panel {panel_number} of a comic book")

        # ===== PER-PANEL VISUAL DETAILS =====
        has_visual_details = False

        # Lighting
        if lighting:
            if not has_visual_details:
                parts.append("VISUAL DETAILS:")
                has_visual_details = True
            parts.append("Lighting:")
            for light in lighting:
                parts.append(f"  - {light}")

        # Special Effects
        if special_effects:
            if not has_visual_details:
                parts.append("VISUAL DETAILS:")
                has_visual_details = True
            parts.append("Special Effects:")
            for effect in special_effects:
                parts.append(f"  - {effect}")

        # Composition
        if composition:
            if not has_visual_details:
                parts.append("VISUAL DETAILS:")
                has_visual_details = True
            parts.append("Composition:")
            for comp in composition:
                parts.append(f"  - {comp}")

        # ===== ADVANCED LAYOUT INFORMATION =====
        layout_parts = []

        # Transition type guidance (McCloud's framework)
        if transition_type:
            transition_guidance = {
                "moment-to-moment": "Small change in time/action. Focus on subtle differences between moments. Use narrow gutters for continuity.",
                "action-to-action": "Focus on dynamic action progression. Clear cause-and-effect between actions. Use narrow gutters for fast pacing.",
                "subject-to-subject": "Shift focus between subjects/characters while staying in same scene/idea. Maintain visual continuity.",
                "scene-to-scene": "Transition between different scenes or locations. Use wide gutters to indicate significant time/space change.",
                "aspect-to-aspect": "Explore different aspects of same place/idea/mood. Focus on mood, atmosphere, and setting details.",
                "non-sequitur": "No logical relationship between panels. Use for artistic effect, dream sequences, or juxtaposition."
            }
            if transition_type in transition_guidance:
                layout_parts.append(f"TRANSITION TYPE: {transition_type.upper()}")
                layout_parts.append(f"  {transition_guidance[transition_type]}")

        # Gutter type guidance
        if gutter_type:
            gutter_guidance = {
                "standard": "Standard gutters for normal reading pace.",
                "wide": "WIDE gutters to indicate time pause, reflection, or scene change.",
                "none": "NO gutters between panels - continuous flow indicating simultaneous events or fast action.",
                "variable": "Variable gutter widths - use strategically to control pacing and emphasis."
            }
            if gutter_type in gutter_guidance:
                layout_parts.append(f"GUTTER: {gutter_guidance[gutter_type]}")

        # Layout system guidance
        if layout_system:
            layout_sys_guidance = {
                "row-based": "Row-based layout - panels arranged in horizontal rows for traditional flow.",
                "column-based": "Column-based layout - panels arranged in vertical columns.",
                "diagonal": "DIAGONAL layout - panels arranged diagonally for dynamic action and energy flow.",
                "z-path": "Z-PATH layout - panels follow natural Z-shaped reading pattern (top-left → top-right → bottom-left → bottom-right).",
                "combination": "Combination layout - mix of grid and dynamic arrangements.",
                "splash": "SPLASH page - single large panel taking full page for dramatic impact."
            }
            if layout_system in layout_sys_guidance:
                layout_parts.append(f"LAYOUT SYSTEM: {layout_sys_guidance[layout_system]}")

        # Special techniques
        if special_techniques:
            technique_guidance = {
                "inset": "Inset panel - smaller panel within larger panel for detail or flashback.",
                "overlapping": "OVERLAPPING panels - panels overlap each other for layered storytelling effect.",
                "broken_frame": "BROKEN frame - panel borders are irregular/broken for dramatic impact.",
                "borderless": "BORDERLESS panel - no visible border, bleeds into page for emphasis.",
                "widescreen": "WIDESCREEN panel - extra-wide horizontal panel for cinematic scope."
            }
            # Handle comma-separated techniques
            for tech in special_techniques.lower().replace(" ", "").split(","):
                if tech in technique_guidance:
                    layout_parts.append(f"TECHNIQUE: {technique_guidance[tech]}")

        # Emphasis panel
        if emphasis_panel:
            layout_parts.append("EMPHASIS PANEL: This panel should be LARGER or MORE PROMINENT than surrounding panels for dramatic impact.")

        # Add layout section if any layout info present
        if layout_parts:
            parts.append("LAYOUT & COMPOSITION:")
            parts.extend(layout_parts)

        # Add panel type-specific guidance
        panel_guidance = {
            "establishing_shot": "Wide shot establishing the scene and setting. Show full environment.",
            "action": "Dynamic composition showing movement and energy. Clear action lines.",
            "dialogue": "Character-focused composition. Characters positioned for speech bubbles.",
            "close_up": "Tight framing on character face or important detail. Emotional emphasis.",
            "transition": "Bridge between scenes. May show passage of time or location change."
        }

        if panel_type in panel_guidance:
            parts.append(f"Composition: {panel_guidance[panel_type]}")

        # Add comic book style guidance
        parts.append("Style: Comic book art with clear lines, bold colors, and dramatic composition.")

        return "\n\n".join(parts)

    async def execute(
        self,
        prompt: str,
        panel_type: str,
        session_id: str,
        page_number: Optional[int] = None,
        panel_number: Optional[int] = None,
        character_names: Optional[List[str]] = None,
        dialogue: Optional[str] = None,
        action: Optional[str] = None,
        visual_details: Optional[str] = None,
        character_reference: Optional[str] = None,
        variant: Optional[str] = None,
        # Advanced layout parameters
        transition_type: Optional[str] = None,
        gutter_type: Optional[str] = None,
        layout_system: Optional[str] = None,
        special_techniques: Optional[str] = None,
        emphasis_panel: Optional[bool] = None,
        # Visual style enhancement parameters
        art_style: Optional[str] = None,
        color_palette: Optional[Dict[str, List[str]]] = None,
        lighting: Optional[List[str]] = None,
        special_effects: Optional[List[str]] = None,
        composition: Optional[List[str]] = None,
        # Existing parameters
        output_dir: Optional[str] = None,
        aspect_ratio: str = "4:3",
        resolution: str = "2K",
        **kwargs
    ) -> ToolResult:
        """
        Generate an image for a comic panel or character reference.

        Args:
            prompt: Text description of the panel or character to generate
            panel_type: Type of panel (character_reference, establishing_shot, action, dialogue, close_up, transition)
            session_id: Session ID for organizing images
            page_number: Page number (1-based, not needed for character references)
            panel_number: Panel number within the page (1-based, not needed for character references)
            character_names: Names of characters appearing in this panel
            dialogue: Dialogue or text to be shown in the panel
            action: Action happening in the panel
            visual_details: Detailed visual description (composition, lighting, mood, camera angle)
            character_reference: Character name to use as reference (supports variant syntax: 'ARIA_planetary')
            variant: Optional variant identifier for character refs (e.g., 'planetary', 'casual')
            transition_type: McCloud's panel transition type (moment-to-moment, action-to-action, etc.)
            gutter_type: Gutter type for pacing (standard, wide, none, variable)
            layout_system: Layout system (row-based, column-based, diagonal, z-path, etc.)
            special_techniques: Special panel techniques (inset, overlapping, broken_frame, etc.)
            emphasis_panel: Whether this panel is emphasized
            art_style: Overall art style description
            color_palette: Color palette with hex codes
            lighting: Lighting descriptions
            special_effects: Special effects (glitch, particles, etc.)
            composition: Composition notes (angles, framing, focus)
            output_dir: Output directory (default: auto-determined)
            aspect_ratio: Image aspect ratio (default: "4:3")
            resolution: Image resolution (default: "2K")

        Returns:
            ToolResult containing the image path or error message
        """
        if not self.image_provider:
            return self.fail_response(
                "No image provider available. Please configure GOOGLE_API_KEY."
            )

        # Build enhanced prompt with layout information
        enhanced_prompt = self._build_comic_prompt(
            prompt=prompt,
            panel_type=panel_type,
            character_names=character_names,
            dialogue=dialogue,
            action=action,
            visual_details=visual_details,
            page_number=page_number,
            panel_number=panel_number,
            transition_type=transition_type,
            gutter_type=gutter_type,
            layout_system=layout_system,
            special_techniques=special_techniques,
            emphasis_panel=emphasis_panel,
            # Visual style enhancement parameters
            art_style=art_style,
            color_palette=color_palette,
            lighting=lighting,
            special_effects=special_effects,
            composition=composition
        )

        try:
            logger.info(f"Generating {panel_type} image")
            logger.debug(f"Enhanced prompt length: {len(enhanced_prompt)} characters")

            # Load character reference if specified
            ref_images = []
            
            # Logic to find reference images
            # 1. Check if specific reference requested
            if character_reference:
                # Check in-memory first
                if character_reference in self.character_references:
                    ref_images.append(self.character_references[character_reference])
                    logger.info(f"Using in-memory character reference: {character_reference}")
                else:
                    # Check on disk
                    ref_path = self._find_reference_on_disk(session_id, character_reference)
                    if ref_path:
                        try:
                            img = Image.open(ref_path)
                            ref_images.append(img)
                            # Cache it
                            self.character_references[character_reference] = img
                            logger.info(f"Loaded character reference from disk: {character_reference}")
                        except Exception as e:
                            logger.warning(f"Failed to load reference image for {character_reference}: {e}")

            # 2. Check if any characters in 'character_names' have references
            if not ref_images and character_names:
                for char_name in character_names:
                    # Check in-memory
                    if char_name in self.character_references:
                        ref_images.append(self.character_references[char_name])
                        logger.info(f"Using auto-detected in-memory reference: {char_name}")
                        continue
                        
                    # Check on disk
                    ref_path = self._find_reference_on_disk(session_id, char_name)
                    if ref_path:
                        try:
                            img = Image.open(ref_path)
                            ref_images.append(img)
                            # Cache it
                            self.character_references[char_name] = img
                            logger.info(f"Loaded auto-detected reference from disk: {char_name}")
                        except Exception as e:
                            logger.warning(f"Failed to load reference image for {char_name}: {e}")

                            logger.warning(f"Failed to load reference image for {char_name}: {e}")

            # Enhance prompt with reference instructions if we have references
            if ref_images:
                enhanced_prompt += "\n\nCRITICAL INSTRUCTION: references provided. " \
                                 "The attached images are character reference sheets. " \
                                 "You MUST maintain strict visual consistency with these references " \
                                 "for the characters involved. Match their facial features, " \
                                 "clothing, and style exactly."
                logger.debug("Added reference instructions to prompt")

            # Determine output directory BEFORE generating image (for logging)
            if output_dir is None:
                # Always use session folder for organizing comic files
                # working_directory should NOT be used as it's typically the project root
                base_dir = os.path.join("data", "sessions", session_id)

                if panel_type == "character_reference":
                    output_dir = os.path.join(base_dir, "character_refs")
                else:
                    output_dir = os.path.join(base_dir, "panels")

            # Create output directory
            os.makedirs(output_dir, exist_ok=True)

            # Generate image with session_id and output_dir for logging
            image = self.image_provider.generate_image(
                prompt=enhanced_prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                ref_images=ref_images if ref_images else None,
                session_id=session_id,
                output_dir=output_dir
            )

            if not image:
                return self.fail_response("Failed to generate image")

            # Generate filename
            if panel_type == "character_reference":
                # Use character name from prompt or default
                char_name = character_names[0] if character_names else "character"
                filename = self._generate_reference_filename(char_name, variant, output_dir)
            else:
                # Panel file naming
                if not page_number or not panel_number:
                    return self.fail_response(
                        "page_number and panel_number are required for non-character_reference panels"
                    )
                filename = f"page_{page_number:02d}_panel_{panel_number:02d}.png"

            filepath = os.path.join(output_dir, filename)

            # Handle different image types
            if hasattr(image, '_pil_image'):
                pil_image = image._pil_image
            elif hasattr(image, 'mode'):
                pil_image = image
            else:
                return self.fail_response(f"Unsupported image type: {type(image)}")

            # Convert to RGB if necessary
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                rgb_image.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None)
                pil_image = rgb_image

            # Save the image
            pil_image.save(filepath, 'PNG')
            logger.info(f"Image saved to: {filepath}")

            # Store character reference if it's a reference sheet
            if panel_type == "character_reference" and character_names:
                # Use variant-aware key for in-memory cache
                cache_key = character_names[0]
                if variant:
                    cache_key = f"{character_names[0]}_{variant}"
                self.character_references[cache_key] = pil_image
                logger.info(f"Stored character reference: {cache_key}")

            # Return success
            result = {
                "success": True,
                "file_path": filepath,
                "filename": filename,
                "panel_type": panel_type,
                "session_id": session_id,
                "output_dir": output_dir,
                "image_size": pil_image.size
            }

            if panel_type == "character_reference":
                char_desc = character_names[0] if character_names else 'unknown'
                if variant:
                    char_desc = f"{char_desc} ({variant})"
                result["message"] = f"Character reference generated: {char_desc}"
                if variant:
                    result["variant"] = variant
            else:
                result["message"] = f"Panel generated: Page {page_number}, Panel {panel_number}"
                result["page_number"] = page_number
                result["panel_number"] = panel_number

            return self.success_response(result)

        except Exception as e:
            error_msg = f"Error generating comic panel: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return self.fail_response(error_msg)

    def _generate_reference_filename(
        self,
        char_name: str,
        variant: Optional[str],
        output_dir: str
    ) -> str:
        """
        Generate unique filename for character reference.

        Supports variant naming and collision prevention.

        Args:
            char_name: Character name
            variant: Optional variant identifier (e.g., 'planetary', 'casual')
            output_dir: Directory where file will be saved

        Returns:
            Unique filename (without path)
        """
        import re

        # Sanitize character name for filesystem (remove special chars, replace spaces)
        safe_name = re.sub(r'[^\w\s-]', '', char_name.upper()).strip().replace(' ', '_')

        # Build base filename
        if variant:
            safe_variant = re.sub(r'[^\w\s-]', '', variant.lower()).strip().replace(' ', '_')
            base_filename = f"{safe_name}_{safe_variant}"
        else:
            base_filename = safe_name

        # Check for collision and increment if needed
        filename = f"{base_filename}.png"
        filepath = os.path.join(output_dir, filename)

        counter = 2
        while os.path.exists(filepath):
            filename = f"{base_filename}_{counter}.png"
            filepath = os.path.join(output_dir, filename)
            counter += 1

            # Safety limit to prevent infinite loops
            if counter > 100:
                logger.warning(f"Too many variants for {char_name}, using counter {counter}")
                break

        logger.info(f"Generated reference filename: {filename}")
        return filename

    def get_character_reference(self, character_name: str) -> Optional[Image.Image]:
        """
        Get stored character reference image.

        Args:
            character_name: Name of the character

        Returns:
            Character reference image if exists, None otherwise
        """
        return self.character_references.get(character_name)

    def _find_reference_on_disk(self, session_id: str, character_name: str) -> Optional[str]:
        """
        Look for character reference file on disk.

        Supports variant syntax: 'CHARACTER_variant' (e.g., 'ARIA_planetary').
        If variant specified but not found, falls back to base character.

        Args:
            session_id: The session ID
            character_name: Name of the character (can include variant suffix)

        Returns:
            Path to file if found, None otherwise
        """
        import re

        if not session_id or not character_name:
            return None

        try:
            # Determine base directory
            if self.execution_context and self.execution_context.working_directory:
                base_dir = self.execution_context.working_directory
            else:
                base_dir = os.path.join("data", "sessions", session_id)

            ref_dir = os.path.join(base_dir, "character_refs")

            if not os.path.exists(ref_dir):
                return None

            # Sanitize input for filesystem matching
            safe_name = re.sub(r'[^\w\s_-]', '', character_name).strip().replace(' ', '_')

            # Try exact match first (with any variant suffix)
            names_to_check = [
                safe_name.upper(),
                safe_name.lower(),
                safe_name.title(),
                safe_name,
                character_name.upper().replace(' ', '_'),
                character_name.upper().replace(' ', ''),
            ]

            for name in names_to_check:
                for ext in ['.png', '.jpg', '.jpeg']:
                    path = os.path.join(ref_dir, f"{name}{ext}")
                    if os.path.exists(path):
                        logger.debug(f"Found reference on disk: {path}")
                        return path

            # If name contains underscore, try to find base character as fallback
            # e.g., 'ARIA_planetary' -> try 'ARIA' if planetary not found
            if '_' in safe_name:
                # Split and try base name (everything before last underscore)
                parts = safe_name.rsplit('_', 1)
                base_name = parts[0]

                base_names_to_check = [
                    base_name.upper(),
                    base_name.lower(),
                    base_name.title(),
                    base_name,
                ]

                for name in base_names_to_check:
                    for ext in ['.png', '.jpg', '.jpeg']:
                        path = os.path.join(ref_dir, f"{name}{ext}")
                        if os.path.exists(path):
                            logger.info(f"Variant not found, falling back to base character: {path}")
                            return path

            return None

        except Exception as e:
            logger.warning(f"Error checking disk for reference {character_name}: {e}")
            return None

    def clear_references(self):
        """Clear all stored character references."""
        self.character_references.clear()
        logger.info("Character references cleared")

    def __repr__(self):
        """String representation of the tool."""
        return f"GenerateComicPanelTool(provider={self.image_provider.__class__.__name__ if self.image_provider else None})"
