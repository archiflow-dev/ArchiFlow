"""
Unit tests for ExportPPTXTool.
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from agent_framework.tools.ppt.export_pptx_tool import ExportPPTXTool


class TestExportPPTXTool:
    """Test cases for ExportPPTXTool."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def export_tool(self):
        """Create an ExportPPTXTool instance."""
        return ExportPPTXTool()

    @pytest.fixture
    def sample_slides(self, temp_dir):
        """Create sample slide images for testing."""
        from PIL import Image
        slide_files = []
        for i in range(3):
            filename = f"slide_{i+1:03d}.png"
            filepath = os.path.join(temp_dir, filename)
            img = Image.new('RGB', (1920, 1080), color=(100 + i*50, 150, 200))
            img.save(filepath)
            slide_files.append(filepath)
        return slide_files

    def test_tool_initialization(self, export_tool):
        """Test tool initialization."""
        assert export_tool.name == "export_pptx"
        assert "title" in export_tool.parameters["required"]
        # output_dir default is now dynamic based on session_id
        assert "output_dir" in export_tool.parameters["properties"]
        assert export_tool.parameters["properties"]["slide_pattern"]["default"] == "slide_*.png"

    def test_slide_dimensions(self, export_tool):
        """Test slide dimensions are set correctly."""
        assert export_tool.SLIDE_WIDTH_INCHES == 10.0
        assert export_tool.SLIDE_HEIGHT_INCHES == 5.625
        # Check aspect ratio is approximately 16:9
        aspect_ratio = export_tool.SLIDE_WIDTH_INCHES / export_tool.SLIDE_HEIGHT_INCHES
        assert abs(aspect_ratio - 16/9) < 0.001

    def test_find_slide_files(self, export_tool, temp_dir, sample_slides):
        """Test finding slide files."""
        from pathlib import Path

        # Test with input directory
        files = export_tool._find_slide_files("slide_*.png", Path(temp_dir))
        assert len(files) == 3
        assert "slide_001.png" in files[0]
        assert "slide_002.png" in files[1]
        assert "slide_003.png" in files[2]

        # Test with custom pattern
        files = export_tool._find_slide_files("slide_00*.png", Path(temp_dir))
        assert len(files) == 3

        # Test with non-matching pattern
        files = export_tool._find_slide_files("missing_*.png", Path(temp_dir))
        assert len(files) == 0

        # Test with default (current directory)
        os.chdir(temp_dir)
        files = export_tool._find_slide_files("slide_*.png")
        assert len(files) == 3

    def test_find_slide_files_sorting(self, export_tool, temp_dir):
        """Test that slide files are sorted numerically."""
        # Create files out of order
        from PIL import Image
        from pathlib import Path
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
        """Test successful export to PPTX."""

        # Mock python-pptx to avoid dependency
        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', True):
            with patch('agent_framework.tools.ppt.export_pptx_tool.Inches') as MockInches:
                with patch('agent_framework.tools.ppt.export_pptx_tool.Presentation') as MockPresentation:
                    # Setup mocks
                    MockInches.return_value = 914400  # Mock return value

                    mock_prs = Mock()
                    MockPresentation.return_value = mock_prs
                    mock_prs.slide_width = 9144000  # 10 inches in EMU
                    mock_prs.slide_height = 5143500  # 5.625 inches in EMU

                    mock_slide_layouts = [Mock() for _ in range(7)]
                    mock_prs.slide_layouts = mock_slide_layouts

                    mock_slide = Mock()
                    mock_prs.slides.add_slide.return_value = mock_slide

                    mock_shape = Mock()
                    mock_slide.shapes.add_picture.return_value = mock_shape

                    # Execute export with input_dir
                    output_dir = os.path.join(temp_dir, "exports")
                    result = await export_tool.execute(
                        title="Test Presentation",
                        input_dir=temp_dir,
                        session_id="test",
                        output_dir=output_dir
                    )

                    # Verify results
                    assert result.error is None
                    import json
                    result_data = json.loads(result.output)  # Parse the JSON string
                    assert result_data["success"] == True
                    assert "file_path" in result_data
                    assert "Test_Presentation" in result_data["file_path"]
                    assert result_data["slide_count"] == 3

                    # Verify directory was created
                    assert os.path.exists(output_dir)

    @pytest.mark.asyncio
    async def test_export_no_slides(self, export_tool, temp_dir):
        """Test export when no slide files are found."""
        os.chdir(temp_dir)

        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', True):
            with patch('agent_framework.tools.ppt.export_pptx_tool.Inches') as MockInches:
                with patch('agent_framework.tools.ppt.export_pptx_tool.Presentation') as MockPresentation:
                    MockInches.return_value = 914400
                    result = await export_tool.execute(
                        title="Empty Presentation",
                        input_dir=temp_dir,
                        session_id="test"
                    )

                    assert result.error is not None
                    assert "No slide files found" in result.error

    @pytest.mark.asyncio
    async def test_export_no_pptx_package(self, export_tool):
        """Test export when python-pptx is not installed."""
        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', False):
            result = await export_tool.execute(title="Test Presentation")

            assert result.error is not None
            assert "python-pptx package is required" in result.error

    @pytest.mark.asyncio
    async def test_export_custom_output_dir(self, export_tool, temp_dir, sample_slides):
        """Test export with custom output directory."""
        os.chdir(temp_dir)

        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', True):
            with patch('agent_framework.tools.ppt.export_pptx_tool.Inches') as MockInches:
                with patch('agent_framework.tools.ppt.export_pptx_tool.Presentation') as MockPresentation:
                    MockInches.return_value = 914400
                    mock_prs = Mock()
                    MockPresentation.return_value = mock_prs
                    mock_prs.slide_width = 9144000
                    mock_prs.slide_height = 5143500
                    mock_prs.slide_layouts = [Mock() for _ in range(7)]
                    mock_prs.slides.add_slide.return_value = Mock()

                    custom_dir = os.path.join(temp_dir, "custom_exports")
                    result = await export_tool.execute(
                        title="Custom Presentation",
                        input_dir=temp_dir,
                        session_id="test",
                        output_dir=custom_dir
                    )

                    assert result.error is None
                    assert os.path.exists(custom_dir)
                    assert "Custom_Presentation" in result.output

    @pytest.mark.asyncio
    async def test_export_filename_sanitization(self, export_tool, temp_dir, sample_slides):
        """Test that presentation titles are sanitized for filenames."""
        os.chdir(temp_dir)

        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', True):
            with patch('agent_framework.tools.ppt.export_pptx_tool.Inches') as MockInches:
                with patch('agent_framework.tools.ppt.export_pptx_tool.Presentation') as MockPresentation:
                    MockInches.return_value = 914400
                    mock_prs = Mock()
                    MockPresentation.return_value = mock_prs
                    mock_prs.slide_width = 9144000
                    mock_prs.slide_height = 5143500
                    mock_prs.slide_layouts = [Mock() for _ in range(7)]
                    mock_prs.slides.add_slide.return_value = Mock()

                    # Test with special characters
                    result = await export_tool.execute(
                        title="Test@Presentation#1!",
                        input_dir=temp_dir,
                        session_id="test"
                    )

                    assert result.error is None
                    # Special characters should be removed
                    assert "TestPresentation1" in result.output

    @pytest.mark.asyncio
    async def test_export_invalid_input_dir(self, export_tool, temp_dir):
        """Test export with invalid input directory."""
        invalid_dir = os.path.join(temp_dir, "nonexistent")

        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', True):
            with patch('agent_framework.tools.ppt.export_pptx_tool.Inches') as MockInches:
                with patch('agent_framework.tools.ppt.export_pptx_tool.Presentation') as MockPresentation:
                    MockInches.return_value = 914400
                    MockPresentation.return_value = Mock()

                    result = await export_tool.execute(
                        title="Test Presentation",
                        input_dir=invalid_dir
                    )

                    assert result.error is not None
                    assert "Input directory does not exist" in result.error

    @pytest.mark.asyncio
    async def test_export_error_handling(self, export_tool, temp_dir, sample_slides):
        """Test error handling during export."""
        os.chdir(temp_dir)

        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', True):
            with patch('agent_framework.tools.ppt.export_pptx_tool.Presentation') as MockPresentation:
                # Make Presentation raise an exception
                MockPresentation.side_effect = Exception("PPTX error")

                result = await export_tool.execute(
                    title="Error Test",
                    input_dir=temp_dir,
                    session_id="test"
                )

                assert result.error is not None
                assert "Error exporting to PPTX" in result.error

    def test_tool_repr(self, export_tool):
        """Test string representation of the tool."""
        repr_str = repr(export_tool)
        assert "ExportPPTXTool" in repr_str
        assert "pptx_available" in repr_str

    @pytest.mark.asyncio
    async def test_export_with_corrupted_slide(self, export_tool, temp_dir):
        """Test export when one slide file is corrupted."""
        from PIL import Image

        # Create normal slides
        for i in range(2):
            filename = f"slide_{i+1:03d}.png"
            filepath = os.path.join(temp_dir, filename)
            img = Image.new('RGB', (1920, 1080), color=(100, 150, 200))
            img.save(filepath)

        # Create a corrupted file
        corrupted_path = os.path.join(temp_dir, "slide_003.png")
        with open(corrupted_path, 'w') as f:
            f.write("not an image")

        os.chdir(temp_dir)

        with patch('agent_framework.tools.ppt.export_pptx_tool.PPTX_AVAILABLE', True):
            with patch('agent_framework.tools.ppt.export_pptx_tool.Inches') as MockInches:
                with patch('agent_framework.tools.ppt.export_pptx_tool.Presentation') as MockPresentation:
                    MockInches.return_value = 914400
                    mock_prs = Mock()
                    MockPresentation.return_value = mock_prs
                    mock_prs.slide_width = 9144000
                    mock_prs.slide_height = 5143500
                    mock_prs.slide_layouts = [Mock() for _ in range(7)]
                    mock_slide = Mock()
                    mock_prs.slides.add_slide.return_value = mock_slide
                    mock_slide.shapes.add_picture.return_value = Mock()

                    result = await export_tool.execute(
                        title="Mixed Slides",
                        input_dir=temp_dir,
                        session_id="test"
                    )

                    # Should still succeed with the good slides
                    assert result.error is None
                    import json
                    result_data = json.loads(result.output)
                    assert result_data["slide_count"] >= 2