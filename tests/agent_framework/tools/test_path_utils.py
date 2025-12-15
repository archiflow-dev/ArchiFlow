"""Tests for path resolution utilities."""

import os
import tempfile
from pathlib import Path
import pytest

from agent_framework.tools.path_utils import (
    resolve_path,
    is_safe_path,
    normalize_path
)


class TestResolvePath:
    """Tests for resolve_path function."""

    def test_absolute_path_unchanged(self):
        """Absolute paths should resolve to themselves."""
        abs_path = "/absolute/path/to/file.py"
        result = resolve_path(abs_path)
        assert result == str(Path(abs_path).resolve())

    def test_relative_path_with_working_directory(self):
        """Relative paths should resolve against working_directory."""
        result = resolve_path("src/main.py", working_directory="/project")
        assert result == str(Path("/project/src/main.py").resolve())

    def test_relative_path_without_working_directory(self):
        """Relative paths without working_directory use current directory."""
        result = resolve_path("test.py")
        expected = str(Path.cwd() / "test.py")
        assert result == expected

    def test_parent_directory_navigation(self):
        """Path with .. should resolve correctly."""
        result = resolve_path("../other/file.py", working_directory="/project/src")
        assert result == str(Path("/project/other/file.py").resolve())

    def test_current_directory_notation(self):
        """Path with . should resolve correctly."""
        result = resolve_path("./src/./main.py", working_directory="/project")
        assert result == str(Path("/project/src/main.py").resolve())

    def test_empty_path_raises_error(self):
        """Empty path should raise ValueError."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            resolve_path("")

    def test_whitespace_only_path_raises_error(self):
        """Whitespace-only path should raise ValueError."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            resolve_path("   ")

    def test_strict_mode_allows_internal_paths(self):
        """Strict mode should allow paths within working_directory."""
        result = resolve_path(
            "src/main.py",
            working_directory="/project",
            strict=True
        )
        assert result == str(Path("/project/src/main.py").resolve())

    def test_strict_mode_blocks_external_paths(self):
        """Strict mode should block paths outside working_directory."""
        with pytest.raises(ValueError, match="outside working directory"):
            resolve_path(
                "../../etc/passwd",
                working_directory="/project/src",
                strict=True
            )

    def test_strict_mode_with_absolute_external_path(self):
        """Strict mode should block absolute paths outside working_directory."""
        with pytest.raises(ValueError, match="outside working directory"):
            resolve_path(
                "/etc/passwd",
                working_directory="/project",
                strict=True
            )

    def test_windows_style_paths(self):
        """Should handle Windows-style paths correctly."""
        # Note: This test behavior depends on the platform
        result = resolve_path("src\\main.py", working_directory="/project")
        assert "main.py" in result

    def test_with_real_filesystem(self):
        """Test with actual temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test relative path resolution
            result = resolve_path("test.txt", working_directory=tmpdir)
            expected = str(Path(tmpdir) / "test.txt")
            assert result == expected

            # Test nested path
            result = resolve_path("subdir/file.py", working_directory=tmpdir)
            expected = str(Path(tmpdir) / "subdir" / "file.py")
            assert result == expected


class TestIsSafePath:
    """Tests for is_safe_path function."""

    def test_safe_relative_path(self):
        """Relative path within base should be safe."""
        assert is_safe_path("src/main.py", "/project") is True

    def test_unsafe_parent_traversal(self):
        """Path escaping base via .. should be unsafe."""
        assert is_safe_path("../../etc/passwd", "/project/src") is False

    def test_unsafe_absolute_path(self):
        """Absolute path outside base should be unsafe."""
        assert is_safe_path("/etc/passwd", "/project") is False

    def test_safe_absolute_path_within_base(self):
        """Absolute path within base should be safe."""
        assert is_safe_path("/project/src/main.py", "/project") is True

    def test_with_real_filesystem(self):
        """Test with actual temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()

            # Safe path
            assert is_safe_path(str(subdir / "file.py"), tmpdir) is True

            # Unsafe path
            parent = Path(tmpdir).parent
            assert is_safe_path(str(parent / "other"), tmpdir) is False

    def test_nonexistent_paths(self):
        """Should work with paths that don't exist yet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Non-existent but safe path
            assert is_safe_path("future/file.py", tmpdir) is True

            # Non-existent and unsafe path
            assert is_safe_path("../../outside", tmpdir) is False


class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_normalize_current_directory(self):
        """Current directory notation should be normalized."""
        result = normalize_path("./src/./main.py")
        assert result == os.path.normpath("src/main.py")

    def test_normalize_parent_directory(self):
        """Parent directory notation should be normalized."""
        result = normalize_path("src/../lib/module.py")
        assert result == os.path.normpath("lib/module.py")

    def test_normalize_multiple_slashes(self):
        """Multiple slashes should be normalized."""
        result = normalize_path("src//main.py")
        assert result == os.path.normpath("src/main.py")

    def test_preserve_absolute_path(self):
        """Absolute paths should remain absolute."""
        # Use platform-appropriate absolute path
        if os.name == 'nt':
            # Windows absolute path
            result = normalize_path("C:\\absolute\\path")
            assert os.path.isabs(result)
        else:
            # Unix absolute path
            result = normalize_path("/absolute/path")
            assert os.path.isabs(result)

    def test_cross_platform_separators(self):
        """Should handle different path separators."""
        result = normalize_path("src/utils\\helper.py")
        # Should normalize to platform-appropriate separator
        assert "helper.py" in result
        assert "\\" not in result or os.sep == "\\"
