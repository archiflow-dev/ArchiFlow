"""
Unit tests for config.merger module.
"""
import os
import sys
import unittest

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src')))

from agent_framework.config.merger import (
    deep_merge,
    deep_merge_multiple,
    merge_with_precedence,
    merge_settings_configs,
    merge_context_files,
    merge_lists_with_append,
    merge_lists_unique,
    deep_merge_with_list_strategy,
    get_effective_value,
)


class TestDeepMerge(unittest.TestCase):
    """Test deep_merge function."""

    def test_merges_flat_dictionaries(self):
        """Test that flat dictionaries are merged."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)

        self.assertEqual(result["a"], 1)  # From base
        self.assertEqual(result["b"], 3)  # Overridden
        self.assertEqual(result["c"], 4)  # From override

    def test_merges_nested_dictionaries(self):
        """Test that nested dictionaries are merged recursively."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}, "c": 4}
        result = deep_merge(base, override)

        self.assertEqual(result["a"]["x"], 1)  # From base
        self.assertEqual(result["a"]["y"], 20)  # Overridden
        self.assertEqual(result["a"]["z"], 30)  # From override
        self.assertEqual(result["b"], 3)
        self.assertEqual(result["c"], 4)

    def test_replaces_lists_by_default(self):
        """Test that lists are replaced (not merged) by default."""
        base = {"items": ["a", "b"]}
        override = {"items": ["c", "d"]}
        result = deep_merge(base, override)

        self.assertEqual(result["items"], ["c", "d"])  # Replaced

    def test_does_not_modify_original_dictionaries(self):
        """Test that original dictionaries are not modified."""
        base = {"a": 1}
        override = {"b": 2}
        original_base = base.copy()
        original_override = override.copy()

        deep_merge(base, override)

        self.assertEqual(base, original_base)
        self.assertEqual(override, original_override)


class TestDeepMergeMultiple(unittest.TestCase):
    """Test deep_merge_multiple function."""

    def test_merges_multiple_configs_in_order(self):
        """Test that multiple configs are merged in precedence order."""
        c1 = {"a": {"x": 1}, "b": 1}
        c2 = {"a": {"y": 2}, "c": 2}
        c3 = {"a": {"z": 3}, "d": 3}
        result = deep_merge_multiple([c1, c2, c3])

        self.assertEqual(result["a"]["x"], 1)
        self.assertEqual(result["a"]["y"], 2)
        self.assertEqual(result["a"]["z"], 3)
        self.assertEqual(result["b"], 1)
        self.assertEqual(result["c"], 2)
        self.assertEqual(result["d"], 3)

    def test_returns_empty_dict_for_empty_list(self):
        """Test that empty dict is returned for empty list."""
        result = deep_merge_multiple([])
        self.assertEqual(result, {})

    def test_returns_single_config_for_single_item_list(self):
        """Test that single config is returned for one-item list."""
        config = {"a": 1}
        result = deep_merge_multiple([config])
        self.assertEqual(result, config)


class TestMergeWithPrecedence(unittest.TestCase):
    """Test merge_with_precedence function."""

    def test_merges_all_hierarchy_levels(self):
        """Test that all hierarchy levels are merged correctly."""
        framework = {"a": 1, "b": {"x": 10}}
        global_user = {"b": {"y": 20}, "c": 3}
        project = {"c": 30, "d": 4}
        project_local = {"d": 40, "e": 5}

        result = merge_with_precedence(
            framework=framework,
            global_user=global_user,
            project=project,
            project_local=project_local
        )

        self.assertEqual(result["a"], 1)  # From framework
        self.assertEqual(result["b"]["x"], 10)  # From framework
        self.assertEqual(result["b"]["y"], 20)  # From global
        self.assertEqual(result["c"], 30)  # Project overrides global
        self.assertEqual(result["d"], 40)  # Local overrides project
        self.assertEqual(result["e"], 5)  # From local

    def test_handles_missing_levels(self):
        """Test that missing hierarchy levels are handled."""
        framework = {"a": 1}
        project = {"b": 2}

        result = merge_with_precedence(
            framework=framework,
            project=project
        )

        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)


class TestMergeSettingsConfigs(unittest.TestCase):
    """Test merge_settings_configs function."""

    def test_merges_configs_with_paths(self):
        """Test that configs are merged correctly."""
        from pathlib import Path

        c1 = (Path("config1.json"), {"a": 1, "b": {"x": 10}})
        c2 = (Path("config2.json"), {"b": {"y": 20}, "c": 2})
        configs = [c1, c2]

        result = merge_settings_configs(configs)

        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"]["x"], 10)
        self.assertEqual(result["b"]["y"], 20)
        self.assertEqual(result["c"], 2)


class TestMergeContextFiles(unittest.TestCase):
    """Test merge_context_files function."""

    def test_concatenates_all_contexts(self):
        """Test that all contexts are concatenated."""
        framework = "# Framework\n\nFramework content"
        global_user = "# Global\n\nGlobal content"
        project = "# Project\n\nProject content"

        result = merge_context_files(
            framework_path=framework,
            global_path=global_user,
            project_path=project
        )

        self.assertIn("Framework Defaults", result)
        self.assertIn("Framework content", result)
        self.assertIn("~/.archiflow/ARCHIFLOW.md", result)
        self.assertIn("Global content", result)
        self.assertIn("./.archiflow/ARCHIFLOW.md", result)
        self.assertIn("Project content", result)

    def test_returns_empty_string_for_no_contexts(self):
        """Test that empty string is returned when no contexts provided."""
        result = merge_context_files()
        self.assertEqual(result, "")


class TestMergeListsAppend(unittest.TestCase):
    """Test merge_lists_with_append function."""

    def test_appends_lists(self):
        """Test that lists are appended."""
        base = [1, 2, 3]
        override = [4, 5, 6]
        result = merge_lists_with_append(base, override)

        self.assertEqual(result, [1, 2, 3, 4, 5, 6])


class TestMergeListsUnique(unittest.TestCase):
    """Test merge_lists_unique function."""

    def test_keeps_unique_items(self):
        """Test that unique items are kept."""
        base = [1, 2, 3]
        override = [3, 4, 5]
        result = merge_lists_unique(base, override)

        self.assertEqual(result, [1, 2, 3, 4, 5])

    def test_preserves_order(self):
        """Test that order is preserved."""
        base = [3, 1, 2]
        override = [2, 4, 3]
        result = merge_lists_unique(base, override)

        self.assertEqual(result, [3, 1, 2, 4])


class TestDeepMergeWithListStrategy(unittest.TestCase):
    """Test deep_merge_with_list_strategy function."""

    def test_replace_strategy(self):
        """Test list replacement strategy."""
        base = {"items": ["a", "b"]}
        override = {"items": ["c", "d"]}
        result = deep_merge_with_list_strategy(base, override, "replace")

        self.assertEqual(result["items"], ["c", "d"])

    def test_append_strategy(self):
        """Test list append strategy."""
        base = {"items": ["a", "b"]}
        override = {"items": ["c", "d"]}
        result = deep_merge_with_list_strategy(base, override, "append")

        self.assertEqual(result["items"], ["a", "b", "c", "d"])

    def test_unique_strategy(self):
        """Test list unique strategy."""
        base = {"items": ["a", "b"]}
        override = {"items": ["b", "c"]}
        result = deep_merge_with_list_strategy(base, override, "unique")

        self.assertEqual(result["items"], ["a", "b", "c"])


class TestGetEffectiveValue(unittest.TestCase):
    """Test get_effective_value function."""

    def test_gets_value_from_highest_precedence(self):
        """Test that value from highest precedence is returned."""
        configs = [
            {"a": {"x": 1}},
            {"a": {"x": 2}},
            {"a": {"x": 3}}
        ]

        result = get_effective_value(configs, "a.x")

        self.assertEqual(result, 3)  # From last config

    def test_returns_default_when_key_not_found(self):
        """Test that default is returned when key is not found."""
        configs = [{"a": 1}]

        result = get_effective_value(configs, "b", default="default_value")

        self.assertEqual(result, "default_value")

    def test_navigates_nested_keys(self):
        """Test that nested keys are navigated correctly."""
        configs = [
            {"level1": {"level2": {"level3": "value"}}}
        ]

        result = get_effective_value(configs, "level1.level2.level3")

        self.assertEqual(result, "value")

    def test_returns_none_for_missing_nested_key(self):
        """Test that None is returned for missing nested key."""
        configs = [{"level1": {"level2": "value"}}]

        result = get_effective_value(configs, "level1.level2.level3")

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
