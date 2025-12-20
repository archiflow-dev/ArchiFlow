"""
Unit tests for ExportPDFTool.
"""

import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, patch
from pathlib import Path
from PIL import Image

from agent_framework.tools.ppt.export_pdf_tool import ExportPDFTool


class TestExportPDFTool:
    """Test cases for ExportPDFTool."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def export_tool(self):
        """Create an ExportPDFTool instance."""
        return ExportPDFTool()

    @pytest.fixture
    def sample_slides(self, temp_dir):
        """Create sample slide images for testing."""
        slide_files = []
        for i in range(3):
            filename = f"slide_{i+1:03d}.png"
            filepath = os.path.join(temp_dir, filename)
            # Create test image with specific size for PDF
            img = Image.new('RGB', (1920, 1080), color=(100 + i*50, 150, 200))
            img.save(filepath)
            slide_files.append(filepath)
        return slide_files

    def test_tool_initialization(self, export_tool):
        """Test tool initialization."""
        assert export_tool.name == "export_pdf"
        assert "title" in export_tool.parameters["required"]
        assert export_tool.parameters["properties"]["output_dir"]["default"] == "data/ppt_exports"
        assert export_tool.parameters["properties"]["page_size"]["default"] == "A4"
        assert export_tool.parameters["properties"]["orientation"]["default"] == "landscape"
        assert export_tool.parameters["properties"]["quality"]["default"] == 95

    def test_page_sizes(self, export_tool):
        """Test page size definitions."""
        assert 'A4' in export_tool.PAGE_SIZES
        assert 'Letter' in export_tool.PAGE_SIZES
        assert 'Legal' in export_tool.PAGE_SIZES
        assert 'A3' in export_tool.PAGE_SIZES
        assert 'A5' in export_tool.PAGE_SIZES

        # Verify A4 dimensions
        width, height = export_tool.PAGE_SIZES['A4']
        assert width == 2480  # 8.27 inches at 300 DPI
        assert height == 3508  # 11.69 inches at 300 DPI

    def test_find_slide_files(self, export_tool, temp_dir, sample_slides):
        """Test finding slide files."""
        from pathlib import Path

        # Test with input directory
        files = export_tool._find_slide_files("slide_*.png", Path(temp_dir))
        assert len(files) == 3
        assert "slide_001.png" in files[0]
        assert "slide_002.png" in files[1]
        assert "slide_003.png" in files[2]

        # Test with default (current directory)
        os.chdir(temp_dir)
        files = export_tool._find_slide_files("slide_*.png")
        assert len(files) == 3

        # Test with non-matching pattern
        files = export_tool._find_slide_files("missing_*.png", Path(temp_dir))
        assert len(files) == 0

    def test_find_slide_files_sorting(self, export_tool, temp_dir):
        """Test that slide files are sorted numerically."""
        # Create files out of order
        file_order = ["slide_010.png", "slide_002.png", "slide_001.png"]
        for filename in file_order:
            filepath = os.path.join(temp_dir, filename)
            img = Image.new('RGB', (1920, 1080), color=(100, 150, 200))
            img.save(filepath)

        files = export_tool._find_slide_files("slide_*.png", Path(temp_dir))

        # Should be sorted numerically
        assert "slide_001.png" in files[0]
        assert "slide_002.png" in files[1]
        assert "slide_010.png" in files[2]

    def test_get_slide_count(self, export_tool, temp_dir, sample_slides):
        """Test getting slide count."""
        count = export_tool.get_slide_count(input_dir=temp_dir)
        assert count == 3

        count = export_tool.get_slide_count("slide_00*.png", temp_dir)
        assert count == 3

        count = export_tool.get_slide_count("missing_*.png", temp_dir)
        assert count == 0

    @pytest.mark.asyncio
    async def test_export_success(self, export_tool, temp_dir, sample_slides):
        """Test successful PDF export."""
        # Execute export with input_dir
        output_dir = os.path.join(temp_dir, "exports")
        result = await export_tool.execute(
            title="Test Presentation",
            input_dir=temp_dir,
            output_dir=output_dir
        )

        assert result.error is None
        import json
        result_data = json.loads(result.output)
        assert result_data["success"] == True
        assert "file_path" in result_data
        assert "Test_Presentation" in result_data["file_path"]
        assert result_data["page_count"] == 3
        assert result_data["page_size"] == "A4"
        assert result_data["orientation"] == "landscape"
        assert result_data["quality"] == 95

        # Verify directory was created
        assert os.path.exists(output_dir)

        # Verify PDF file was created
        pdf_path = result_data["file_path"]
        assert os.path.exists(pdf_path)
        assert pdf_path.endswith('.pdf')

    @pytest.mark.asyncio
    async def test_export_with_different_page_sizes(self, export_tool, temp_dir, sample_slides):
        """Test export with different page sizes."""
        for page_size in ['A4', 'Letter', 'A3']:
            output_dir = os.path.join(temp_dir, f"exports_{page_size}")
            result = await export_tool.execute(
                title=f"Test {page_size}",
                input_dir=temp_dir,
                output_dir=output_dir,
                page_size=page_size
            )

            assert result.error is None
            result_data = json.loads(result.output)
            assert result_data["page_size"] == page_size

    @pytest.mark.asyncio
    async def test_export_portrait_orientation(self, export_tool, temp_dir, sample_slides):
        """Test export with portrait orientation."""
        output_dir = os.path.join(temp_dir, "exports_portrait")
        result = await export_tool.execute(
            title="Portrait Test",
            input_dir=temp_dir,
            output_dir=output_dir,
            orientation="portrait"
        )

        assert result.error is None
        result_data = json.loads(result.output)
        assert result_data["orientation"] == "portrait"

    @pytest.mark.asyncio
    async def test_export_no_slides(self, export_tool, temp_dir):
        """Test export when no slide files are found."""
        output_dir = os.path.join(temp_dir, "exports")
        result = await export_tool.execute(
            title="Empty Presentation",
            input_dir=temp_dir,
            output_dir=output_dir
        )

        assert result.error is not None
        assert "No slide files found" in result.error

    @pytest.mark.asyncio
    async def test_export_with_session_id(self, export_tool, temp_dir, sample_slides):
        """Test export using session_id."""
        # Create session directory
        session_dir = os.path.join(temp_dir, "data", "images", "test_session")
        os.makedirs(session_dir, exist_ok=True)

        # Copy slides to session directory
        for slide in sample_slides:
            shutil.copy2(slide, session_dir)

        # Use the full path to session directory as input_dir
        result = await export_tool.execute(
            title="Session Test",
            input_dir=session_dir,
            session_id="test_session"
        )

        assert result.error is None
        result_data = json.loads(result.output)
        assert result_data["session_id"] == "test_session"
        assert result_data["page_count"] == 3

    @pytest.mark.asyncio
    async def test_export_with_rgba_images(self, export_tool, temp_dir):
        """Test export with RGBA images (should convert to RGB)."""
        # Create RGBA images
        rgba_files = []
        for i in range(2):
            filename = f"slide_{i+1:03d}.png"
            filepath = os.path.join(temp_dir, filename)
            img = Image.new('RGBA', (1920, 1080), (100 + i*50, 150, 200, 128))
            img.save(filepath)
            rgba_files.append(filepath)

        output_dir = os.path.join(temp_dir, "exports")
        result = await export_tool.execute(
            title="RGBA Test",
            input_dir=temp_dir,
            output_dir=output_dir
        )

        assert result.error is None
        result_data = json.loads(result.output)
        assert result_data["page_count"] == 2

        # Verify PDF was created
        pdf_path = result_data["file_path"]
        assert os.path.exists(pdf_path)

    @pytest.mark.asyncio
    async def test_export_quality_parameter(self, export_tool, temp_dir, sample_slides):
        """Test export with different quality settings."""
        output_dir = os.path.join(temp_dir, "exports")

        # Test with different quality values
        for quality in [75, 90, 100]:
            filename = f"quality_test_{quality}.pdf"
            result = await export_tool.execute(
                title=f"Quality Test {quality}",
                input_dir=temp_dir,
                output_dir=output_dir,
                quality=quality
            )

            assert result.error is None
            result_data = json.loads(result.output)
            assert result_data["quality"] == quality

    @pytest.mark.asyncio
    async def test_export_title_sanitization(self, export_tool, temp_dir, sample_slides):
        """Test that presentation titles are sanitized for filenames."""
        output_dir = os.path.join(temp_dir, "exports")
        result = await export_tool.execute(
            title="Test@Presentation#1 - Special Characters!",
            input_dir=temp_dir,
            output_dir=output_dir
        )

        assert result.error is None
        # Special characters should be removed
        assert "TestPresentation1" in result.output

    @pytest.mark.asyncio
    async def test_export_error_handling(self, export_tool, temp_dir):
        """Test error handling during export."""
        # Create a corrupted file
        corrupted_path = os.path.join(temp_dir, "slide_001.png")
        with open(corrupted_path, 'w') as f:
            f.write("not an image")

        output_dir = os.path.join(temp_dir, "exports")
        result = await export_tool.execute(
            title="Error Test",
            input_dir=temp_dir,
            output_dir=output_dir
        )

        # Should fail gracefully
        assert result.error is not None
        assert "PDF" in result.error or "images" in result.error

    def test_tool_repr(self, export_tool):
        """Test string representation of the tool."""
        repr_str = repr(export_tool)
        assert "ExportPDFTool" in repr_str

    @pytest.mark.asyncio
    async def test_export_image_scaling(self, export_tool, temp_dir):
        """Test that images are properly scaled to fit the page."""
        # Create images with different aspect ratios
        images = [
            (1920, 1080),  # 16:9 landscape
            (1080, 1920),  # 9:16 portrait
            (1024, 1024),  # Square
        ]

        for i, (w, h) in enumerate(images):
            filename = f"slide_{i+1:03d}.png"
            filepath = os.path.join(temp_dir, filename)
            img = Image.new('RGB', (w, h), color=(100 + i*30, 150, 200))
            img.save(filepath)

        output_dir = os.path.join(temp_dir, "exports")
        result = await export_tool.execute(
            title="Scaling Test",
            input_dir=temp_dir,
            output_dir=output_dir
        )

        assert result.error is None
        result_data = json.loads(result.output)
        assert result_data["page_count"] == 3

    @pytest.mark.asyncio
    async def test_export_with_large_images(self, export_tool, temp_dir):
        """Test export with very large images."""
        # Create a large image
        large_img = Image.new('RGB', (4096, 3072), color=(100, 150, 200))
        large_path = os.path.join(temp_dir, "slide_001.png")
        large_img.save(large_path)

        output_dir = os.path.join(temp_dir, "exports")
        result = await export_tool.execute(
            title="Large Image Test",
            input_dir=temp_dir,
            output_dir=output_dir
        )

        assert result.error is None
        result_data = json.loads(result.output)
        assert result_data["page_count"] == 1