"""
Export PDF Tool for PPT Agent MVP.

This tool converts generated slide images into PDF format.
It uses PIL to create high-quality PDF files from slide images.
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, ClassVar
from pathlib import Path

from ..tool_base import BaseTool, ToolResult
from PIL import Image

# Set up logger for this module
logger = logging.getLogger(__name__)


class ExportPDFTool(BaseTool):
    """
    Tool for exporting slide images to PDF format.

    This tool converts slide images into a PDF document,
    maintaining image quality and proper formatting.
    """

    name: str = "export_pdf"
    description: str = "Export slide images to a PDF document."

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title for the PDF document"
            },
            "input_dir": {
                "type": "string",
                "description": "Input directory containing slide images (default: data/images/{session_id})"
            },
            "session_id": {
                "type": "string",
                "description": "Session ID for organizing files (default: 'default')"
            },
            "output_dir": {
                "type": "string",
                "description": "Output directory for the PDF file (default: data/ppt_exports)",
                "default": "data/ppt_exports"
            },
            "slide_pattern": {
                "type": "string",
                "description": "Pattern to match slide files (default: slide_*.png)",
                "default": "slide_*.png"
            },
            "page_size": {
                "type": "string",
                "description": "PDF page size (default: 'A4')",
                "enum": ["A4", "Letter", "Legal", "A3", "A5"],
                "default": "A4"
            },
            "orientation": {
                "type": "string",
                "description": "Page orientation (default: 'landscape')",
                "enum": ["portrait", "landscape"],
                "default": "landscape"
            },
            "quality": {
                "type": "integer",
                "description": "JPEG quality for images (1-100, default: 95)",
                "minimum": 1,
                "maximum": 100,
                "default": 95
            }
        },
        "required": ["title"]
    }

    # Page size definitions in pixels at 300 DPI
    PAGE_SIZES: ClassVar[Dict[str, tuple]] = {
        'A4': (2480, 3508),      # 8.27 x 11.69 inches at 300 DPI
        'Letter': (2550, 3300),  # 8.5 x 11 inches at 300 DPI
        'Legal': (2550, 4200),    # 8.5 x 14 inches at 300 DPI
        'A3': (3508, 4961),      # 11.69 x 16.53 inches at 300 DPI
        'A5': (1748, 2480),      # 5.83 x 8.27 inches at 300 DPI
    }

    def __init__(self, **data):
        """Initialize the ExportPDFTool."""
        super().__init__(**data)

    async def execute(
        self,
        title: str,
        input_dir: Optional[str] = None,
        session_id: str = "default",
        output_dir: str = "data/ppt_exports",
        slide_pattern: str = "slide_*.png",
        page_size: str = "A4",
        orientation: str = "landscape",
        quality: int = 95,
        **kwargs
    ) -> ToolResult:
        """
        Export slide images to a PDF document.

        Args:
            title: Title for the PDF document
            input_dir: Input directory containing slide images (default: data/images/{session_id})
            session_id: Session ID for organizing files
            output_dir: Output directory for the PDF file
            slide_pattern: Pattern to match slide files
            page_size: PDF page size
            orientation: Page orientation
            quality: JPEG quality for images (1-100)

        Returns:
            ToolResult containing the file path and page count or error message
        """
        try:
            logger.info(f"Starting PDF export for presentation: {title}")

            # Determine input directory
            if input_dir is None:
                # Default to data/images/{session_id}
                input_dir = os.path.join("data", "images", session_id)

            # Validate input directory
            input_path = Path(input_dir)
            if not input_path.exists():
                return self.fail_response(
                    f"Input directory does not exist: {input_dir}"
                )

            if not input_path.is_dir():
                return self.fail_response(
                    f"Input path is not a directory: {input_dir}"
                )

            # Find all slide files
            slide_files = self._find_slide_files(slide_pattern, input_path)
            if not slide_files:
                return self.fail_response(
                    f"No slide files found matching pattern '{slide_pattern}' in directory: {input_dir}"
                )

            logger.info(f"Found {len(slide_files)} slide files")

            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Output directory: {output_path.absolute()}")

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Sanitize title for filename
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')
            filename = f"{safe_title}_{timestamp}.pdf"
            filepath = output_path / filename

            # Get page dimensions
            page_width, page_height = self.PAGE_SIZES[page_size]
            if orientation == "portrait":
                page_width, page_height = page_height, page_width

            # Convert images and create PDF
            pdf_images = []
            for slide_file in slide_files:
                try:
                    img_path = Path(slide_file)
                    if not img_path.exists():
                        logger.warning(f"Slide file not found: {slide_file}")
                        continue

                    # Open and convert image
                    with Image.open(img_path) as img:
                        # Convert to RGB if necessary (PDF requires RGB)
                        if img.mode not in ('RGB', 'L'):
                            if img.mode == 'RGBA':
                                # Create white background for transparency
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                background.paste(img, mask=img.split()[-1])
                                img = background
                            elif img.mode == 'LA':
                                background = Image.new('RGB', img.size, (255, 255, 255))
                                background.paste(img, mask=img.split()[-1])
                                img = background
                            elif img.mode == 'P':
                                img = img.convert('RGB')
                            else:
                                img = img.convert('RGB')

                        # Calculate scaling to fit page
                        img_width, img_height = img.size
                        page_aspect = page_width / page_height
                        img_aspect = img_width / img_height

                        if img_aspect > page_aspect:
                            # Image is wider than page - scale to width
                            new_width = int(page_width * 0.9)  # 90% of page width
                            new_height = int(new_width / img_aspect)
                        else:
                            # Image is taller than page - scale to height
                            new_height = int(page_height * 0.9)  # 90% of page height
                            new_width = int(new_height * img_aspect)

                        # Resize image while maintaining aspect ratio
                        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        pdf_images.append(img_resized)

                except Exception as e:
                    logger.error(f"Error processing slide {slide_file}: {e}")
                    continue

            if not pdf_images:
                return self.fail_response("No valid images could be processed for PDF creation")

            # Save images as PDF
            if pdf_images[0].mode != 'RGB':
                pdf_images[0] = pdf_images[0].convert('RGB')

            # Save first image as PDF with additional images
            pdf_images[0].save(
                str(filepath),
                "PDF",
                resolution=300.0,
                quality=quality,
                save_all=True,
                append_images=pdf_images[1:]
            )

            logger.info(f"PDF saved to: {filepath}")

            # Return success with file information
            result = {
                "success": True,
                "file_path": str(filepath.absolute()),
                "filename": filename,
                "title": title,
                "session_id": session_id,
                "page_count": len(pdf_images),
                "input_dir": str(input_path.absolute()),
                "output_dir": str(output_path.absolute()),
                "page_size": page_size,
                "orientation": orientation,
                "quality": quality
            }

            return self.success_response(result)

        except Exception as e:
            error_msg = f"Error exporting to PDF: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return self.fail_response(error_msg)

    def _find_slide_files(self, pattern: str, input_dir: Path = None) -> List[str]:
        """
        Find slide files matching the pattern.

        Args:
            pattern: Glob pattern for slide files
            input_dir: Directory to search in

        Returns:
            Sorted list of slide file paths
        """
        if input_dir is None:
            input_dir = Path(".")

        # Use glob to find matching files in the input directory
        search_pattern = str(input_dir / pattern)
        import glob
        files = glob.glob(search_pattern)

        # Sort numerically (slide_001.png, slide_002.png, etc.)
        def extract_number(f):
            import re
            match = re.search(r'slide_(\d+)', f)
            return int(match.group(1)) if match else 0

        files.sort(key=extract_number)
        return files

    def get_slide_count(self, pattern: str = "slide_*.png", input_dir: str = None, session_id: str = "default") -> int:
        """
        Get the count of slide files without creating a PDF.

        Args:
            pattern: Pattern to match slide files
            input_dir: Directory to search in (if None, uses data/images/{session_id})
            session_id: Session ID for organizing files

        Returns:
            Number of slide files found
        """
        if input_dir is None:
            input_dir = os.path.join("data", "images", session_id)
        return len(self._find_slide_files(pattern, Path(input_dir)))

    def __repr__(self):
        """String representation of the tool."""
        return f"ExportPDFTool()"