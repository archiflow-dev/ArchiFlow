"""
Tests for ExportComicPDFTool.

Comprehensive test coverage for comic PDF export tool.
"""

import unittest
import tempfile
import shutil
import os
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch

from agent_framework.tools.comic.export_comic_pdf_tool import ExportComicPDFTool

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class TestExportComicPDFTool(unittest.TestCase):
    """Test suite for ExportComicPDFTool."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_id = "test_session"
        self.tool = ExportComicPDFTool()

        # Create test session directory structure
        self.session_dir = Path(self.temp_dir) / "data" / "sessions" / self.session_id
        self.panels_dir = self.session_dir / "panels"
        self.exports_dir = self.session_dir / "comic_exports"

        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.panels_dir.mkdir(exist_ok=True)

        # Change to temp dir for tests
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up test files."""
        os.chdir(self.original_cwd)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def parse_output(self, result):
        """Parse JSON output from ToolResult."""
        if result.error:
            return None
        return json.loads(result.output)

    def _create_test_panel(self, page: int, panel: int, size=(100, 100)) -> Path:
        """Create a test panel image."""
        if not PIL_AVAILABLE:
            return None

        img = Image.new('RGB', size, color=(255, 0, 0))
        filename = f"page_{page:02d}_panel_{panel:02d}.png"
        filepath = self.panels_dir / filename
        img.save(filepath)
        return filepath

    def _create_test_script(self, title: str = "Test Comic") -> Path:
        """Create a test script.md file."""
        script_path = self.session_dir / "script.md"
        script_path.write_text(f"# {title}\n\nA test comic script.", encoding='utf-8')
        return script_path

    # ===== Initialization Tests =====

    def test_initialization(self):
        """Test tool initialization."""
        self.assertIsNotNone(self.tool)
        self.assertEqual(self.tool.name, "export_comic_pdf")
        self.assertIn("Export comic to PDF", self.tool.description)

    def test_tool_schema(self):
        """Test tool schema structure."""
        schema = self.tool.parameters
        self.assertEqual(schema["type"], "object")
        self.assertIn("session_id", schema["properties"])
        self.assertIn("required", schema)
        self.assertIn("session_id", schema["required"])

    def test_tool_description(self):
        """Test tool has proper description."""
        self.assertIsNotNone(self.tool.description)
        self.assertGreater(len(self.tool.description), 10)

    # ===== Title Extraction Tests =====

    def test_extract_title_from_script(self):
        """Test extracting title from script.md."""
        script_path = self._create_test_script("My Awesome Comic")
        title = self.tool._extract_title_from_script(script_path)
        self.assertEqual(title, "My Awesome Comic")

    def test_extract_title_no_header(self):
        """Test title extraction when no header exists."""
        script_path = self.session_dir / "script.md"
        script_path.write_text("Just some text without a header", encoding='utf-8')
        title = self.tool._extract_title_from_script(script_path)
        self.assertEqual(title, "Untitled Comic")

    def test_extract_title_empty_file(self):
        """Test title extraction from empty file."""
        script_path = self.session_dir / "script.md"
        script_path.write_text("", encoding='utf-8')
        title = self.tool._extract_title_from_script(script_path)
        self.assertEqual(title, "Untitled Comic")

    # ===== Panel Grouping Tests =====

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_group_panels_by_page(self):
        """Test grouping panels by page number."""
        # Create panels for multiple pages
        panels = [
            self._create_test_panel(1, 1),
            self._create_test_panel(1, 2),
            self._create_test_panel(2, 1),
            self._create_test_panel(2, 2),
            self._create_test_panel(3, 1),
        ]

        grouped = self.tool._group_panels_by_page(panels)

        self.assertEqual(len(grouped), 3)
        self.assertEqual(len(grouped[1]), 2)
        self.assertEqual(len(grouped[2]), 2)
        self.assertEqual(len(grouped[3]), 1)

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_group_panels_single_page(self):
        """Test grouping panels from a single page."""
        panels = [
            self._create_test_panel(1, i) for i in range(1, 7)
        ]

        grouped = self.tool._group_panels_by_page(panels)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[1]), 6)

    def test_group_panels_empty_list(self):
        """Test grouping empty panel list."""
        grouped = self.tool._group_panels_by_page([])
        self.assertEqual(len(grouped), 0)

    # ===== Page Dimensions Tests =====

    def test_get_page_dimensions_letter(self):
        """Test getting Letter page dimensions."""
        width, height = self.tool._get_page_dimensions("Letter", 300)
        self.assertEqual(width, 2550)  # 8.5 inches * 300 DPI
        self.assertEqual(height, 3300)  # 11 inches * 300 DPI

    def test_get_page_dimensions_a4(self):
        """Test getting A4 page dimensions."""
        width, height = self.tool._get_page_dimensions("A4", 300)
        self.assertEqual(width, 2481)  # 8.27 inches * 300 DPI
        self.assertEqual(height, 3507)  # 11.69 inches * 300 DPI

    def test_get_page_dimensions_different_dpi(self):
        """Test page dimensions with different DPI."""
        width, height = self.tool._get_page_dimensions("Letter", 150)
        self.assertEqual(width, 1275)  # 8.5 inches * 150 DPI
        self.assertEqual(height, 1650)  # 11 inches * 150 DPI

    # ===== Cover Page Tests =====

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_create_cover_page(self):
        """Test creating cover page."""
        img = self.tool._create_cover_page("Test Comic", "Letter", 300)

        self.assertIsNotNone(img)
        self.assertEqual(img.mode, 'RGB')
        self.assertEqual(img.size, (2550, 3300))

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_create_cover_page_a4(self):
        """Test creating cover page with A4 size."""
        img = self.tool._create_cover_page("Test Comic", "A4", 300)

        self.assertIsNotNone(img)
        self.assertEqual(img.size, (2481, 3507))

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_create_cover_page_with_long_title(self):
        """Test creating cover page with long title."""
        long_title = "A Very Long Comic Book Title That Should Still Fit"
        img = self.tool._create_cover_page(long_title, "Letter", 300)

        self.assertIsNotNone(img)

    # ===== Credits Page Tests =====

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_create_credits_page(self):
        """Test creating credits page."""
        img = self.tool._create_credits_page("Test Comic", "Letter", 300)

        self.assertIsNotNone(img)
        self.assertEqual(img.mode, 'RGB')
        self.assertEqual(img.size, (2550, 3300))

    # ===== Panel Compositing Tests =====

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_composite_page_6_panels(self):
        """Test compositing 6 panels into a page."""
        panels = [Image.new('RGB', (100, 100), color=(i*40, 0, 0)) for i in range(6)]

        page_img = self.tool._composite_page(panels, 6, "Letter", 300)

        self.assertIsNotNone(page_img)
        self.assertEqual(page_img.mode, 'RGB')

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_composite_page_2_panels(self):
        """Test compositing 2 panels into a page."""
        panels = [Image.new('RGB', (100, 100), color=(i*100, 0, 0)) for i in range(2)]

        page_img = self.tool._composite_page(panels, 2, "Letter", 300)

        self.assertIsNotNone(page_img)

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_composite_page_9_panels(self):
        """Test compositing 9 panels into a page."""
        panels = [Image.new('RGB', (100, 100), color=(i*25, 0, 0)) for i in range(9)]

        page_img = self.tool._composite_page(panels, 9, "Letter", 300)

        self.assertIsNotNone(page_img)

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_composite_page_with_rgba_panels(self):
        """Test compositing RGBA panels."""
        panels = [Image.new('RGBA', (100, 100), color=(255, 0, 0, 128)) for _ in range(4)]

        page_img = self.tool._composite_page(panels, 4, "Letter", 300)

        self.assertIsNotNone(page_img)
        self.assertEqual(page_img.mode, 'RGB')

    # ===== Full Export Tests =====

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_basic(self):
        """Test basic PDF export."""
        async def run_test():
            # Create test panels
            for page in range(1, 3):
                for panel in range(1, 4):
                    self._create_test_panel(page, panel)

            # Create script
            self._create_test_script("Test Comic")

            # Export PDF
            result = await self.tool.execute(session_id=self.session_id)

            self.assertIsNone(result.error)
            output = self.parse_output(result)

            self.assertIsNotNone(output)
            self.assertTrue(output["success"])
            self.assertIn("pdf_path", output)
            self.assertEqual(output["title"], "Test Comic")
            self.assertGreater(output["page_count"], 0)
            self.assertEqual(output["image_count"], 6)

            # Verify PDF file exists
            pdf_path = Path(output["pdf_path"])
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 0)

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_without_cover(self):
        """Test PDF export without cover page."""
        async def run_test():
            # Create test panels
            self._create_test_panel(1, 1)
            self._create_test_panel(1, 2)

            # Export PDF without cover
            result = await self.tool.execute(
                session_id=self.session_id,
                include_cover=False
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_without_credits(self):
        """Test PDF export without credits page."""
        async def run_test():
            # Create test panels
            self._create_test_panel(1, 1)

            # Export PDF without credits
            result = await self.tool.execute(
                session_id=self.session_id,
                include_credits=False
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_custom_title(self):
        """Test PDF export with custom title."""
        async def run_test():
            # Create test panels
            self._create_test_panel(1, 1)

            # Export PDF with custom title
            result = await self.tool.execute(
                session_id=self.session_id,
                title="Custom Title"
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertEqual(output["title"], "Custom Title")

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_custom_output_path(self):
        """Test PDF export with custom output path."""
        async def run_test():
            # Create test panels
            self._create_test_panel(1, 1)

            # Custom output path
            custom_path = self.session_dir / "my_comic.pdf"

            # Export PDF
            result = await self.tool.execute(
                session_id=self.session_id,
                output_path=str(custom_path)
            )

            self.assertIsNone(result.error)
            self.assertTrue(custom_path.exists())

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_a4_size(self):
        """Test PDF export with A4 page size."""
        async def run_test():
            # Create test panels
            self._create_test_panel(1, 1)

            # Export PDF with A4 size
            result = await self.tool.execute(
                session_id=self.session_id,
                page_size="A4"
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_different_panels_per_page(self):
        """Test PDF export with different panels per page."""
        async def run_test():
            # Create test panels
            for i in range(1, 10):
                self._create_test_panel(1, i)

            # Export PDF with 9 panels per page
            result = await self.tool.execute(
                session_id=self.session_id,
                panels_per_page=9
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_low_dpi(self):
        """Test PDF export with lower DPI."""
        async def run_test():
            # Create test panels
            self._create_test_panel(1, 1)

            # Export PDF with lower DPI
            result = await self.tool.execute(
                session_id=self.session_id,
                dpi=150
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])

        asyncio.run(run_test())

    # ===== Error Handling Tests =====

    def test_export_pdf_session_not_found(self):
        """Test error when session directory doesn't exist."""
        async def run_test():
            result = await self.tool.execute(session_id="nonexistent_session")

            self.assertIsNotNone(result.error)
            self.assertIn("Session directory not found", result.error)

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_no_panels(self):
        """Test error when no panels exist."""
        async def run_test():
            result = await self.tool.execute(session_id=self.session_id)

            self.assertIsNotNone(result.error)
            self.assertIn("No images found", result.error)

        asyncio.run(run_test())

    @unittest.skipIf(PIL_AVAILABLE, "PIL is available")
    def test_export_pdf_no_pil(self):
        """Test error when PIL is not available."""
        async def run_test():
            result = await self.tool.execute(session_id=self.session_id)

            self.assertIsNotNone(result.error)
            self.assertIn("PIL (Pillow) is not installed", result.error)

        asyncio.run(run_test())

    # ===== Integration Tests =====

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_complete_workflow(self):
        """Test complete PDF export workflow."""
        async def run_test():
            # Create a complete comic with multiple pages
            for page in range(1, 4):  # 3 pages
                for panel in range(1, 7):  # 6 panels per page
                    self._create_test_panel(page, panel)

            # Create script
            self._create_test_script("Complete Comic Test")

            # Export PDF with all options
            result = await self.tool.execute(
                session_id=self.session_id,
                title="Complete Comic Test",
                page_size="Letter",
                panels_per_page=6,
                include_cover=True,
                include_credits=True,
                dpi=300
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)

            # Verify all outputs
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])
            self.assertEqual(output["title"], "Complete Comic Test")
            self.assertEqual(output["image_count"], 18)
            # Should have: 1 cover + 3 story pages + 1 credits = 5 pages
            self.assertEqual(output["page_count"], 5)

            # Verify file exists and has reasonable size
            pdf_path = Path(output["pdf_path"])
            self.assertTrue(pdf_path.exists())
            self.assertGreater(output["file_size_mb"], 0)

        asyncio.run(run_test())

    @unittest.skipIf(not PIL_AVAILABLE, "PIL not available")
    def test_export_pdf_mixed_image_counts(self):
        """Test PDF export with different panel counts per page."""
        async def run_test():
            # Page 1: 6 panels
            for i in range(1, 7):
                self._create_test_panel(1, i)

            # Page 2: 4 panels
            for i in range(1, 5):
                self._create_test_panel(2, i)

            # Page 3: 2 panels
            for i in range(1, 3):
                self._create_test_panel(3, i)

            # Export PDF
            result = await self.tool.execute(
                session_id=self.session_id,
                panels_per_page=6
            )

            self.assertIsNone(result.error)
            output = self.parse_output(result)
            self.assertIsNotNone(output)
            self.assertTrue(output["success"])
            self.assertEqual(output["image_count"], 12)

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
