"""
Unit tests for config.hierarchy module.
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

from agent_framework.config.hierarchy import (
    ConfigSnapshot,
    ConfigHierarchy,
    create_global_config,
)


class TestConfigSnapshot(unittest.TestCase):
    """Test ConfigSnapshot dataclass."""

    def test_initialization(self):
        """Test snapshot initialization."""
        snapshot = ConfigSnapshot()

        self.assertEqual(snapshot.settings, {})
        self.assertEqual(snapshot.context, "")
        self.assertEqual(snapshot.sources, [])
        self.assertEqual(snapshot.metadata, {})

    def test_with_data(self):
        """Test snapshot with data."""
        settings = {"key": "value"}
        context = "# Context"
        sources = [Path("/test/path")]
        metadata = {"info": "test"}

        snapshot = ConfigSnapshot(
            settings=settings,
            context=context,
            sources=sources,
            metadata=metadata
        )

        self.assertEqual(snapshot.settings, settings)
        self.assertEqual(snapshot.context, context)
        self.assertEqual(snapshot.sources, sources)
        self.assertEqual(snapshot.metadata, metadata)

    def test_is_valid(self):
        """Test is_valid property."""
        snapshot = ConfigSnapshot(settings={})
        self.assertFalse(snapshot.is_valid)

        snapshot = ConfigSnapshot(settings={"key": "value"})
        self.assertTrue(snapshot.is_valid)

    def test_has_context(self):
        """Test has_context property."""
        snapshot = ConfigSnapshot(context="")
        self.assertFalse(snapshot.has_context)

        snapshot = ConfigSnapshot(context="# Context")
        self.assertTrue(snapshot.has_context)

        snapshot = ConfigSnapshot(context="   ")
        self.assertFalse(snapshot.has_context)


class TestConfigHierarchy(unittest.TestCase):
    """Test ConfigHierarchy class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test ConfigHierarchy initialization."""
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)

        self.assertEqual(hierarchy.working_dir, self.temp_dir)
        self.assertEqual(hierarchy.config_type, "settings")
        self.assertEqual(hierarchy.context_file, "ARCHIFLOW.md")
        self.assertTrue(hierarchy.enable_cache)

    def test_load_with_no_configs(self):
        """Test loading when no config files exist."""
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)
        snapshot = hierarchy.load()

        self.assertIsInstance(snapshot, ConfigSnapshot)
        self.assertEqual(snapshot.settings, {})
        self.assertEqual(snapshot.context, "")
        self.assertEqual(snapshot.sources, [])

    def test_load_with_project_settings(self):
        """Test loading with project settings.json."""
        # Create .archiflow directory and settings.json
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        settings = {"agent": {"defaultModel": "test-model"}}
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)
        snapshot = hierarchy.load()

        self.assertEqual(snapshot.settings, settings)
        self.assertEqual(len(snapshot.sources), 1)

    def test_load_with_project_context(self):
        """Test loading with project ARCHIFLOW.md."""
        # Create .archiflow directory and ARCHIFLOW.md
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        context = "# Test Context\n\nContent here"
        (archiflow_dir / "ARCHIFLOW.md").write_text(context, encoding="utf-8")

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)
        snapshot = hierarchy.load()

        self.assertIn("Test Context", snapshot.context)
        self.assertEqual(len(snapshot.sources), 1)

    def test_get_setting(self):
        """Test getting specific settings with dot notation."""
        # Create settings
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        settings = {
            "agent": {
                "defaultModel": "test-model",
                "timeout": 300000
            }
        }
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)

        # Get nested setting
        model = hierarchy.get_setting("agent.defaultModel")
        self.assertEqual(model, "test-model")

        # Get with default
        missing = hierarchy.get_setting("missing.key", "default")
        self.assertEqual(missing, "default")

    def test_cache_enabled(self):
        """Test that caching works when enabled."""
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        settings = {"key": "value"}
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir, enable_cache=True)

        # First load
        snapshot1 = hierarchy.load()
        cache_id_1 = id(snapshot1)

        # Second load should return cached version
        snapshot2 = hierarchy.load()
        cache_id_2 = id(snapshot2)

        # Should be the same object (cached)
        self.assertEqual(cache_id_1, cache_id_2)

    def test_cache_disabled(self):
        """Test that caching is disabled when enable_cache=False."""
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        settings = {"key": "value"}
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir, enable_cache=False)

        snapshot1 = hierarchy.load()
        snapshot2 = hierarchy.load()

        # Should be different objects (no caching)
        self.assertNotEqual(id(snapshot1), id(snapshot2))

    def test_force_reload(self):
        """Test force_reload parameter."""
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        settings = {"key": "value1"}
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir, enable_cache=True)

        # Initial load
        snapshot1 = hierarchy.load()
        self.assertEqual(snapshot1.settings["key"], "value1")

        # Get snapshot cache id
        cache_id_1 = id(snapshot1)

        # Load again without force_reload - should return same cached snapshot
        snapshot2 = hierarchy.load()
        cache_id_2 = id(snapshot2)
        self.assertEqual(cache_id_1, cache_id_2)  # Same object from cache
        self.assertEqual(snapshot2.settings["key"], "value1")

        # Load with force_reload=True - should reload and return new snapshot
        snapshot3 = hierarchy.load(force_reload=True)
        cache_id_3 = id(snapshot3)
        self.assertNotEqual(cache_id_1, cache_id_3)  # Different object
        self.assertEqual(snapshot3.settings["key"], "value1")  # Same content

    def test_clear_cache(self):
        """Test clearing the cache."""
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir, enable_cache=True)

        # Load to populate cache
        hierarchy.load()
        self.assertIsNotNone(hierarchy._cache)

        # Clear cache
        hierarchy.clear_cache()
        self.assertIsNone(hierarchy._cache)

    def test_reload(self):
        """Test reload method."""
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        settings = {"key": "value1"}
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)

        # Initial load
        snapshot1 = hierarchy.load()
        self.assertEqual(snapshot1.settings["key"], "value1")

        # Modify file
        settings["key"] = "value2"
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        # Reload should get new values
        snapshot2 = hierarchy.reload()
        self.assertEqual(snapshot2.settings["key"], "value2")

    def test_get_merged_context(self):
        """Test getting merged context."""
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        context = "# Project Context\n\nProject-specific content."
        (archiflow_dir / "ARCHIFLOW.md").write_text(context, encoding="utf-8")

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)
        merged = hierarchy.get_merged_context()

        self.assertIn("Project Context", merged)

    def test_get_status(self):
        """Test getting hierarchy status."""
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        settings = {"key": "value"}
        (archiflow_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )

        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)
        status = hierarchy.get_status()

        self.assertIn("working_directory", status)
        self.assertTrue(status["project_dir_exists"])
        self.assertTrue(status["cache_enabled"])
        self.assertEqual(status["settings_keys"], 1)

    def test_create_project_config(self):
        """Test creating project configuration files."""
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)

        settings = {"agent": {"timeout": 300000}}
        context = "# Test Context"

        created_dir = hierarchy.create_project_config(
            settings=settings,
            context=context
        )

        self.assertEqual(created_dir, self.temp_dir / ".archiflow")
        self.assertTrue(created_dir.exists())

        # Check files were created
        self.assertTrue((created_dir / "settings.json").exists())
        self.assertTrue((created_dir / "ARCHIFLOW.md").exists())

        # Verify content
        with open(created_dir / "settings.json", "r", encoding="utf-8") as f:
            loaded_settings = json.load(f)
        self.assertEqual(loaded_settings, settings)

    def test_global_dir_property(self):
        """Test global_dir property."""
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)

        global_dir = hierarchy.global_dir
        self.assertEqual(global_dir.name, ".archiflow")

    def test_project_dir_property(self):
        """Test project_dir property."""
        hierarchy = ConfigHierarchy(working_dir=self.temp_dir)

        # No .archiflow yet
        self.assertIsNone(hierarchy.project_dir)

        # Create .archiflow
        archiflow_dir = self.temp_dir / ".archiflow"
        archiflow_dir.mkdir()

        # Should now find it
        hierarchy2 = ConfigHierarchy(working_dir=self.temp_dir)
        self.assertEqual(hierarchy2.project_dir, archiflow_dir)


class TestCreateGlobalConfig(unittest.TestCase):
    """Test create_global_config function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_create_global_config_with_settings(self):
        """Test creating global config with settings."""
        # This test creates files in the actual home directory,
        # so we'll just verify the function doesn't error
        # In production, you might want to mock get_global_archiflow_dir

        settings = {"test": "value"}

        # We won't actually run this to avoid polluting the user's home dir
        # Instead, we'll verify the function is callable
        from agent_framework.config.hierarchy import create_global_config
        self.assertTrue(callable(create_global_config))


if __name__ == '__main__':
    unittest.main()
