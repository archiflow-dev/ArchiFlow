"""
Export Comic PDF Tool.

This tool exports comic panels to PDF format, compositing multiple panels
per page and adding optional cover and credits pages.
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from pydantic import Field

from ..tool_base import BaseTool, ToolResult

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Set up logger for this module
logger = logging.getLogger(__name__)


class ExportComicPDFTool(BaseTool):
    """
    Tool for exporting comic panels to PDF format.

    This tool composites individual panel images into comic book pages
    and generates a professional PDF with optional cover and credits pages.
    """

    name: str = "export_comic_pdf"
    description: str = "Export comic panels to PDF with optional cover and credits pages"

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID (finds files in data/sessions/{session_id}/)"
            },
            "title": {
                "type": "string",
                "description": "Comic title (auto-detected from script.md if not provided)"
            },
            "output_path": {
                "type": "string",
                "description": "Output PDF path (optional, auto-generated if not provided)"
            },
            "page_size": {
                "type": "string",
                "enum": ["Letter", "A4"],
                "description": "PDF page size (default: Letter)",
                "default": "Letter"
            },
            "panels_per_page": {
                "type": "integer",
                "description": "Number of panels per page (default: 6)",
                "minimum": 1,
                "maximum": 12,
                "default": 6
            },
            "include_cover": {
                "type": "boolean",
                "description": "Generate cover page (default: true)",
                "default": True
            },
            "include_credits": {
                "type": "boolean",
                "description": "Generate credits page (default: true)",
                "default": True
            },
            "dpi": {
                "type": "integer",
                "description": "PDF resolution in DPI (default: 300)",
                "minimum": 72,
                "maximum": 600,
                "default": 300
            }
        },
        "required": ["session_id"]
    }

    def __init__(self, **data):
        """Initialize the ExportComicPDFTool."""
        super().__init__(**data)

    async def execute(
        self,
        session_id: str,
        title: Optional[str] = None,
        output_path: Optional[str] = None,
        page_size: str = "Letter",
        panels_per_page: int = 6,
        include_cover: bool = True,
        include_credits: bool = True,
        dpi: int = 300,
        **kwargs
    ) -> ToolResult:
        """
        Export comic to PDF.

        Args:
            session_id: Session identifier
            title: Comic title (auto-detected if not provided)
            output_path: Optional output path
            page_size: Letter or A4
            panels_per_page: Number of panels per page (default: 6)
            include_cover: Add cover page
            include_credits: Add credits page
            dpi: Resolution

        Returns:
            ToolResult with PDF path or error
        """
        if not PIL_AVAILABLE:
            return self.fail_response(
                "PIL (Pillow) is not installed. Install with: pip install Pillow"
            )

        try:
            # 1. Setup paths
            session_dir = Path(f"data/sessions/{session_id}")
            if not session_dir.exists():
                return self.fail_response(f"Session directory not found: {session_dir}")

            script_path = session_dir / "script.md"
            panels_dir = session_dir / "panels"
            exports_dir = session_dir / "comic_exports"
            exports_dir.mkdir(exist_ok=True)

            # 2. Extract title if not provided
            if not title:
                if script_path.exists():
                    title = self._extract_title_from_script(script_path)
                else:
                    title = "Untitled Comic"

            # 3. Find all panel images
            panel_files = sorted(panels_dir.glob("page_*_panel_*.png"))
            if not panel_files:
                return self.fail_response(
                    f"No panel images found in {panels_dir}. "
                    "Generate panels first using generate_comic_panel tool."
                )

            logger.info(f"Found {len(panel_files)} panel images")

            # 4. Parse panel files to understand page structure
            page_panels = self._group_panels_by_page(panel_files)
            logger.info(f"Organized into {len(page_panels)} pages")

            # 5. Generate output path if not provided
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).strip()
                safe_title = safe_title.replace(' ', '_')
                output_path = exports_dir / f"{safe_title}_{timestamp}.pdf"
            else:
                output_path = Path(output_path)

            # 6. Create composite page images
            page_images = []

            # Add cover page
            if include_cover:
                cover_img = self._create_cover_page(title, page_size, dpi)
                page_images.append(cover_img)

            # Add story pages
            for page_num, panels in page_panels.items():
                # Load panel images
                panel_imgs = []
                for panel_file in panels:
                    try:
                        img = Image.open(panel_file)
                        panel_imgs.append(img)
                    except Exception as e:
                        logger.warning(f"Failed to load {panel_file}: {e}")

                # Composite page
                if panel_imgs:
                    page_img = self._composite_page(
                        panel_imgs, panels_per_page, page_size, dpi
                    )
                    page_images.append(page_img)

            # Add credits page
            if include_credits:
                credits_img = self._create_credits_page(title, page_size, dpi)
                page_images.append(credits_img)

            # 7. Save as PDF
            if page_images:
                # Convert all images to RGB (PDF doesn't support RGBA)
                rgb_images = []
                for img in page_images:
                    if img.mode == 'RGBA':
                        # Create white background
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3])  # Use alpha as mask
                        rgb_images.append(background)
                    elif img.mode != 'RGB':
                        rgb_images.append(img.convert('RGB'))
                    else:
                        rgb_images.append(img)

                # Save first image and append the rest
                first_img = rgb_images[0]
                other_imgs = rgb_images[1:] if len(rgb_images) > 1 else []

                first_img.save(
                    output_path,
                    "PDF",
                    resolution=dpi,
                    save_all=True,
                    append_images=other_imgs
                )

                logger.info(f"PDF saved to {output_path}")
            else:
                return self.fail_response("No pages to export")

            # 8. Get file size
            file_size = output_path.stat().st_size / (1024 * 1024)  # MB

            # 9. Return success
            result = {
                "success": True,
                "pdf_path": str(output_path),
                "file_size_mb": round(file_size, 2),
                "page_count": len(page_images),
                "panel_count": len(panel_files),
                "title": title
            }

            return self.success_response(result)

        except Exception as e:
            logger.error(f"PDF export failed: {e}", exc_info=True)
            return self.fail_response(f"PDF export failed: {str(e)}")

    def _extract_title_from_script(self, script_path: Path) -> str:
        """Extract title from script.md."""
        try:
            content = script_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            for line in lines:
                if line.startswith('# '):
                    return line[2:].strip()
            return "Untitled Comic"
        except Exception as e:
            logger.warning(f"Failed to extract title: {e}")
            return "Untitled Comic"

    def _group_panels_by_page(self, panel_files: List[Path]) -> Dict[int, List[Path]]:
        """Group panel files by page number."""
        pages = {}
        for panel_file in panel_files:
            # Extract page number from filename like "page_01_panel_03.png"
            try:
                parts = panel_file.stem.split('_')
                if len(parts) >= 4 and parts[0] == 'page' and parts[2] == 'panel':
                    page_num = int(parts[1])
                    if page_num not in pages:
                        pages[page_num] = []
                    pages[page_num].append(panel_file)
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse panel filename {panel_file}: {e}")

        return pages

    def _create_cover_page(self, title: str, page_size: str, dpi: int) -> Image.Image:
        """Create cover page with title."""
        # Get page dimensions
        width, height = self._get_page_dimensions(page_size, dpi)

        # Create blank page
        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Try to use a nice font, fall back to default
        try:
            title_font = ImageFont.truetype("arial.ttf", int(dpi / 3))
            subtitle_font = ImageFont.truetype("arial.ttf", int(dpi / 6))
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()

        # Draw title in center
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]

        title_x = (width - title_width) // 2
        title_y = (height - title_height) // 2

        draw.text((title_x, title_y), title, fill=(0, 0, 0), font=title_font)

        # Draw subtitle
        subtitle = "A Comic Book"
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]

        subtitle_x = (width - subtitle_width) // 2
        subtitle_y = title_y + title_height + int(dpi / 4)

        draw.text((subtitle_x, subtitle_y), subtitle, fill=(100, 100, 100), font=subtitle_font)

        return img

    def _create_credits_page(self, title: str, page_size: str, dpi: int) -> Image.Image:
        """Create credits page."""
        # Get page dimensions
        width, height = self._get_page_dimensions(page_size, dpi)

        # Create blank page
        img = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Try to use a nice font
        try:
            font = ImageFont.truetype("arial.ttf", int(dpi / 8))
        except:
            font = ImageFont.load_default()

        # Credits text
        credits_text = f"{title}\n\nCreated with ArchiFlow Comic Agent\n\nGenerated on {datetime.now().strftime('%Y-%m-%d')}"

        # Draw credits in center
        bbox = draw.textbbox((0, 0), credits_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2

        draw.multiline_text((text_x, text_y), credits_text, fill=(0, 0, 0), font=font, align='center')

        return img

    def _composite_page(
        self,
        panel_images: List[Image.Image],
        panels_per_page: int,
        page_size: str,
        dpi: int
    ) -> Image.Image:
        """Composite panel images into a single page."""
        # Get page dimensions
        page_width, page_height = self._get_page_dimensions(page_size, dpi)

        # Calculate grid layout
        if panels_per_page <= 2:
            cols, rows = 1, panels_per_page
        elif panels_per_page <= 4:
            cols, rows = 2, 2
        elif panels_per_page <= 6:
            cols, rows = 2, 3
        elif panels_per_page <= 9:
            cols, rows = 3, 3
        else:
            cols, rows = 4, 3

        # Calculate panel dimensions with margins
        margin = int(dpi / 10)  # 0.1 inch margin
        panel_width = (page_width - margin * (cols + 1)) // cols
        panel_height = (page_height - margin * (rows + 1)) // rows

        # Create blank page
        page_img = Image.new('RGB', (page_width, page_height), color=(255, 255, 255))

        # Place panels
        for idx, panel in enumerate(panel_images[:panels_per_page]):
            row = idx // cols
            col = idx % cols

            # Resize panel to fit
            panel_resized = panel.copy()
            panel_resized.thumbnail((panel_width, panel_height), Image.Resampling.LANCZOS)

            # Calculate position (centered in cell)
            x = margin + col * (panel_width + margin) + (panel_width - panel_resized.width) // 2
            y = margin + row * (panel_height + margin) + (panel_height - panel_resized.height) // 2

            # Paste panel
            if panel_resized.mode == 'RGBA':
                page_img.paste(panel_resized, (x, y), mask=panel_resized.split()[3])
            else:
                page_img.paste(panel_resized, (x, y))

        return page_img

    def _get_page_dimensions(self, page_size: str, dpi: int) -> tuple:
        """Get page dimensions in pixels."""
        # Page sizes in inches
        page_sizes = {
            'Letter': (8.5, 11),
            'A4': (8.27, 11.69)
        }

        inches = page_sizes.get(page_size, (8.5, 11))
        width = int(inches[0] * dpi)
        height = int(inches[1] * dpi)

        return (width, height)
