"""
Manual verification script for Hierarchy System Phase 1.

This script verifies the core infrastructure is working correctly:
- paths.py: Path resolution utilities
- loader.py: Configuration file loading
- merger.py: Deep merge implementation

Run this script to verify Phase 1 implementation.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from agent_framework.config.paths import (
    get_global_archiflow_dir,
    get_project_archiflow_dir,
    resolve_config_paths,
    resolve_context_paths,
    ensure_project_dir,
)
from agent_framework.config.loader import (
    load_json_file,
    load_markdown_file,
    parse_frontmatter,
    load_settings_with_precedence,
)
from agent_framework.config.merger import (
    deep_merge,
    deep_merge_multiple,
    merge_with_precedence,
    get_effective_value,
)


def verify_path_resolution():
    """Verify path resolution utilities."""
    print("=" * 60)
    print("Verifying Path Resolution (paths.py)")
    print("=" * 60)

    # Get global directory
    global_dir = get_global_archiflow_dir()
    print(f"[OK] Global directory: {global_dir}")
    assert global_dir.name == ".archiflow"
    assert str(Path.home()) in str(global_dir)

    # Create temp project directory
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)

        # No .archiflow yet
        project_dir = get_project_archiflow_dir(temp_path)
        assert project_dir is None
        print("[OK] Returns None when no .archiflow directory exists")

        # Create .archiflow
        archiflow_dir = temp_path / ".archiflow"
        archiflow_dir.mkdir()
        project_dir = get_project_archiflow_dir(temp_path)
        assert project_dir == archiflow_dir
        print(f"[OK] Returns path when .archiflow exists: {project_dir}")

        # Create config files
        (archiflow_dir / "settings.json").write_text('{"key": "value"}', encoding="utf-8")
        (archiflow_dir / "ARCHIFLOW.md").write_text("# Context", encoding="utf-8")

        # Resolve config paths
        config_paths = resolve_config_paths("settings", working_dir=temp_path)
        assert len(config_paths) == 1
        assert config_paths[0].name == "settings.json"
        print(f"[OK] Resolved config paths: {len(config_paths)} found")

        # Resolve context paths
        context_paths = resolve_context_paths("ARCHIFLOW.md", working_dir=temp_path)
        assert len(context_paths) == 1
        assert context_paths[0].name == "ARCHIFLOW.md"
        print(f"[OK] Resolved context paths: {len(context_paths)} found")

        # Test ensure_project_dir
        new_temp = Path(tempfile.mkdtemp())
        new_project_dir = ensure_project_dir(new_temp)
        assert new_project_dir == new_temp / ".archiflow"
        assert new_project_dir.exists()
        shutil.rmtree(new_temp)
        print("[OK] ensure_project_dir creates directory")

    print("\n[PASS] Path resolution: PASSED\n")


def verify_file_loading():
    """Verify configuration file loading."""
    print("=" * 60)
    print("Verifying File Loading (loader.py)")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)

        # Load JSON file
        json_file = temp_path / "test.json"
        test_data = {"key": "value", "nested": {"x": 1, "y": 2}}
        json_file.write_text(json.dumps(test_data), encoding="utf-8")

        loaded = load_json_file(json_file)
        assert loaded == test_data
        print("[OK] load_json_file: loads valid JSON")

        # Load Markdown file
        md_file = temp_path / "test.md"
        md_content = "# Heading\n\nContent here"
        md_file.write_text(md_content, encoding="utf-8")

        loaded_md = load_markdown_file(md_file)
        assert loaded_md == md_content
        print("[OK] load_markdown_file: loads Markdown content")

        # Parse frontmatter
        frontmatter_content = """---
key: value
number: 42
tags: [tag1, tag2]
---
Body content"""
        frontmatter, body = parse_frontmatter(frontmatter_content)
        assert frontmatter["key"] == "value"
        assert frontmatter["number"] == 42
        assert frontmatter["tags"] == ["tag1", "tag2"]
        assert body.strip() == "Body content"
        print("[OK] parse_frontmatter: parses YAML frontmatter")

        # Parse without frontmatter
        no_fm_content = "# Just content\n\nNo frontmatter"
        frontmatter, body = parse_frontmatter(no_fm_content)
        assert frontmatter is None
        assert body == no_fm_content
        print("[OK] parse_frontmatter: handles missing frontmatter")

    print("\n[PASS] File loading: PASSED\n")


def verify_deep_merge():
    """Verify deep merge functionality."""
    print("=" * 60)
    print("Verifying Deep Merge (merger.py)")
    print("=" * 60)

    # Test basic merge
    base = {"a": 1, "b": 2}
    override = {"b": 3, "c": 4}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": 3, "c": 4}
    print("[OK] deep_merge: merges flat dictionaries")

    # Test nested merge
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 20, "z": 30}, "c": 4}
    result = deep_merge(base, override)
    assert result["a"]["x"] == 1  # From base
    assert result["a"]["y"] == 20  # Overridden
    assert result["a"]["z"] == 30  # From override
    print("[OK] deep_merge: merges nested dictionaries recursively")

    # Test list replacement
    base = {"items": ["a", "b"]}
    override = {"items": ["c", "d"]}
    result = deep_merge(base, override)
    assert result["items"] == ["c", "d"]  # Replaced
    print("[OK] deep_merge: replaces lists by default")

    # Test multiple merge
    c1 = {"a": {"x": 1}}
    c2 = {"a": {"y": 2}}
    c3 = {"a": {"z": 3}}
    result = deep_merge_multiple([c1, c2, c3])
    assert result["a"] == {"x": 1, "y": 2, "z": 3}
    print("[OK] deep_merge_multiple: merges multiple configs")

    # Test merge_with_precedence
    framework = {"a": 1, "b": {"x": 10}}
    global_user = {"b": {"y": 20}, "c": 3}
    project = {"c": 30, "d": 4}
    result = merge_with_precedence(framework=framework, global_user=global_user, project=project)
    assert result["a"] == 1
    assert result["b"]["x"] == 10
    assert result["b"]["y"] == 20
    assert result["c"] == 30  # Project overrides global
    assert result["d"] == 4
    print("[OK] merge_with_precedence: respects hierarchy levels")

    # Test get_effective_value
    configs = [{"a": {"x": 1}}, {"a": {"x": 2}}, {"a": {"x": 3}}]
    value = get_effective_value(configs, "a.x")
    assert value == 3  # From highest precedence
    print("[OK] get_effective_value: gets highest precedence value")

    print("\n[PASS] Deep merge: PASSED\n")


def verify_full_workflow():
    """Verify the full workflow with temporary config files."""
    print("=" * 60)
    print("Verifying Full Workflow (Integration)")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)

        # Create project structure
        archiflow_dir = temp_path / ".archiflow"
        archiflow_dir.mkdir()

        # Create settings.json
        settings = {
            "agent": {
                "defaultModel": "test-model",
                "maxIterations": 10,
                "timeout": 300000
            },
            "autoRefinement": {
                "enabled": False,
                "threshold": 9.0
            }
        }
        (archiflow_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

        # Load settings
        config_list = load_settings_with_precedence("settings", working_dir=temp_path)
        assert len(config_list) == 1
        _, loaded_data = config_list[0]
        assert loaded_data["agent"]["defaultModel"] == "test-model"
        print("[OK] Loaded settings from project directory")

        # Create ARCHIFLOW.md with frontmatter
        context_content = """---
name: test-project
description: Test project context
---

# Test Project

This is a test project for verification.
"""
        (archiflow_dir / "ARCHIFLOW.md").write_text(context_content, encoding="utf-8")

        # Load context
        context_paths = resolve_context_paths("ARCHIFLOW.md", working_dir=temp_path)
        assert len(context_paths) == 1
        loaded_context = load_markdown_file(context_paths[0])
        assert "Test Project" in loaded_context
        print("[OK] Loaded context from project directory")

        # Parse frontmatter from context
        frontmatter, body = parse_frontmatter(loaded_context)
        assert frontmatter["name"] == "test-project"
        assert frontmatter["description"] == "Test project context"
        assert "Test Project" in body
        print("[OK] Parsed frontmatter from context file")

    print("\n[PASS] Full workflow: PASSED\n")


def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("Hierarchy System Phase 1 - Manual Verification")
    print("=" * 60 + "\n")

    try:
        verify_path_resolution()
        verify_file_loading()
        verify_deep_merge()
        verify_full_workflow()

        print("=" * 60)
        print("[SUCCESS] ALL PHASE 1 VERIFICATION TESTS PASSED")
        print("=" * 60 + "\n")

        print("Summary:")
        print("  [OK] paths.py: All path resolution utilities working")
        print("  [OK] loader.py: JSON and Markdown loading working")
        print("  [OK] merger.py: Deep merge working correctly")
        print("  [OK] Integration: Full workflow verified")
        print("\nPhase 1 implementation is complete and ready for Phase 2!")

    except AssertionError as e:
        print(f"\n[FAIL] VERIFICATION FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}\n")
        raise


if __name__ == "__main__":
    main()
