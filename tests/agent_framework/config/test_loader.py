"""
Unit tests for config.loader module.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.config.loader import (
    ConfigLoadError,
    load_json_file,
    load_json_with_defaults,
    load_markdown_file,
    concatenate_markdown_files,
    load_settings_with_precedence,
    load_context_with_precedence,
    parse_frontmatter,
    load_tool_config,
)


class TestLoadJsonFile(unittest.TestCase):
    """Test load_json_file function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_loads_valid_json(self):
        """Test that valid JSON is loaded correctly."""
        test_file = self.temp_dir / "test.json"
        test_data = {"key": "value", "number": 42}
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        result = load_json_file(test_file)

        self.assertEqual(result, test_data)

    def test_raises_error_for_invalid_json(self):
        """Test that ConfigLoadError is raised for invalid JSON."""
        test_file = self.temp_dir / "invalid.json"
        test_file.write_text("{invalid json}", encoding="utf-8")

        with self.assertRaises(ConfigLoadError):
            load_json_file(test_file)

    def test_raises_error_for_non_object_json(self):
        """Test that ConfigLoadError is raised for non-object JSON."""
        test_file = self.temp_dir / "array.json"
        test_file.write_text('["item1", "item2"]', encoding="utf-8")

        with self.assertRaises(ConfigLoadError):
            load_json_file(test_file)

    def test_raises_error_for_missing_file(self):
        """Test that ConfigLoadError is raised for missing file."""
        test_file = self.temp_dir / "missing.json"

        with self.assertRaises(ConfigLoadError):
            load_json_file(test_file)


class TestLoadJsonWithDefaults(unittest.TestCase):
    """Test load_json_with_defaults function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_returns_loaded_json_when_file_exists(self):
        """Test that loaded JSON is returned when file exists."""
        test_file = self.temp_dir / "test.json"
        test_data = {"key": "value"}
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        result = load_json_with_defaults(test_file, {"default": "value"})

        self.assertEqual(result, test_data)

    def test_returns_defaults_when_file_missing(self):
        """Test that defaults are returned when file is missing."""
        test_file = self.temp_dir / "missing.json"
        defaults = {"default": "value"}

        result = load_json_with_defaults(test_file, defaults)

        self.assertEqual(result, defaults)

    def test_returns_empty_dict_when_file_missing_and_no_defaults(self):
        """Test that empty dict is returned when file missing and no defaults."""
        test_file = self.temp_dir / "missing.json"

        result = load_json_with_defaults(test_file)

        self.assertEqual(result, {})


class TestLoadMarkdownFile(unittest.TestCase):
    """Test load_markdown_file function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_loads_markdown_content(self):
        """Test that Markdown content is loaded correctly."""
        test_file = self.temp_dir / "test.md"
        content = "# Heading\n\nSome content"
        test_file.write_text(content, encoding="utf-8")

        result = load_markdown_file(test_file)

        self.assertEqual(result, content)

    def test_raises_error_for_missing_file(self):
        """Test that ConfigLoadError is raised for missing file."""
        test_file = self.temp_dir / "missing.md"

        with self.assertRaises(ConfigLoadError):
            load_markdown_file(test_file)


class TestConcatenateMarkdownFiles(unittest.TestCase):
    """Test concatenate_markdown_files function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_concatenates_multiple_files(self):
        """Test that multiple files are concatenated."""
        file1 = self.temp_dir / "file1.md"
        file2 = self.temp_dir / "file2.md"
        file1.write_text("Content 1", encoding="utf-8")
        file2.write_text("Content 2", encoding="utf-8")

        result = concatenate_markdown_files([file1, file2])

        self.assertEqual(result, "Content 1\n\nContent 2")

    def test_uses_custom_delimiter(self):
        """Test that custom delimiter is used."""
        file1 = self.temp_dir / "file1.md"
        file2 = self.temp_dir / "file2.md"
        file1.write_text("Content 1", encoding="utf-8")
        file2.write_text("Content 2", encoding="utf-8")

        result = concatenate_markdown_files([file1, file2], delimiter=" --- ")

        self.assertEqual(result, "Content 1 --- Content 2")

    def test_skips_missing_files(self):
        """Test that missing files are skipped."""
        file1 = self.temp_dir / "file1.md"
        file2 = self.temp_dir / "missing.md"
        file1.write_text("Content 1", encoding="utf-8")

        result = concatenate_markdown_files([file1, file2])

        self.assertEqual(result, "Content 1")

    def test_returns_empty_string_for_empty_list(self):
        """Test that empty string is returned for empty list."""
        result = concatenate_markdown_files([])
        self.assertEqual(result, "")


class TestParseFrontmatter(unittest.TestCase):
    """Test parse_frontmatter function."""

    def test_parses_valid_frontmatter(self):
        """Test that valid frontmatter is parsed."""
        content = """---
key: value
number: 42
tags: [tag1, tag2]
---
Body content"""

        frontmatter, body = parse_frontmatter(content)

        self.assertEqual(frontmatter["key"], "value")
        self.assertEqual(frontmatter["number"], 42)
        self.assertEqual(frontmatter["tags"], ["tag1", "tag2"])
        self.assertEqual(body.strip(), "Body content")

    def test_returns_none_for_no_frontmatter(self):
        """Test that None is returned when there's no frontmatter."""
        content = "# Just content\n\nNo frontmatter here"

        frontmatter, body = parse_frontmatter(content)

        self.assertIsNone(frontmatter)
        self.assertEqual(body, content)

    def test_parses_boolean_values(self):
        """Test that boolean values are parsed correctly."""
        content = """---
flag_true: true
flag_false: false
---
Content"""

        frontmatter, body = parse_frontmatter(content)

        self.assertTrue(frontmatter["flag_true"])
        self.assertFalse(frontmatter["flag_false"])

    def test_parses_numeric_values(self):
        """Test that numeric values are parsed correctly."""
        content = """---
integer: 42
float: 3.14
---
Content"""

        frontmatter, body = parse_frontmatter(content)

        self.assertEqual(frontmatter["integer"], 42)
        self.assertEqual(frontmatter["float"], 3.14)


if __name__ == '__main__':
    unittest.main()
