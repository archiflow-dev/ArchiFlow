"""
Tests for ArtifactService.
"""

import pytest
import tempfile
import asyncio
from pathlib import Path

from src.web_backend.services.artifact_service import (
    ArtifactService,
    ArtifactNotFoundError,
)
from src.web_backend.services.workspace_manager import (
    WorkspaceManager,
    WorkspaceSecurityError,
)
from src.web_backend.services.storage_manager import (
    StorageManager,
    StorageLimits,
    StorageLimitError,
)


class TestArtifactService:
    """Tests for ArtifactService class."""

    @pytest.fixture
    def temp_base(self):
        """Create a temporary directory for workspaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def workspace_manager(self, temp_base):
        """Create a WorkspaceManager."""
        return WorkspaceManager(base_path=temp_base)

    @pytest.fixture
    def storage_manager(self, workspace_manager):
        """Create a StorageManager with reasonable limits."""
        limits = StorageLimits(
            max_workspace_size_mb=10,
            max_file_size_mb=5,
            max_total_user_storage_gb=1,
        )
        return StorageManager(workspace_manager=workspace_manager, limits=limits)

    @pytest.fixture
    def service(self, workspace_manager, storage_manager):
        """Create an ArtifactService."""
        workspace_manager.create_workspace("user1", "session1")
        return ArtifactService(
            user_id="user1",
            session_id="session1",
            workspace_manager=workspace_manager,
            storage_manager=storage_manager,
        )

    def test_list_empty_directory(self, service):
        """Test listing an empty directory."""
        artifacts = asyncio.run(service.list("artifacts"))
        assert artifacts == []

    def test_list_with_files(self, service):
        """Test listing directory with files."""
        # Create some test files
        workspace = service.workspace

        (workspace / "test1.txt").write_text("Hello")
        (workspace / "test2.md").write_text("# Markdown")
        (workspace / "subdir").mkdir()

        artifacts = asyncio.run(service.list(""))

        # Should have at least our files (plus standard directories)
        names = [a["name"] for a in artifacts]
        assert "test1.txt" in names
        assert "test2.md" in names

    def test_list_filters_hidden_directory(self, service):
        """Test that .archiflow directory is filtered out."""
        artifacts = asyncio.run(service.list(""))
        names = [a["name"] for a in artifacts]
        assert ".archiflow" not in names

    def test_list_sorted_directories_first(self, service):
        """Test that directories are listed before files."""
        workspace = service.workspace

        (workspace / "file.txt").write_text("content")
        (workspace / "aaa_dir").mkdir()

        artifacts = asyncio.run(service.list(""))

        # Find positions
        dir_artifact = next(a for a in artifacts if a["name"] == "aaa_dir")
        file_artifact = next(a for a in artifacts if a["name"] == "file.txt")

        assert dir_artifact["is_directory"]
        assert not file_artifact["is_directory"]
        assert artifacts.index(dir_artifact) < artifacts.index(file_artifact)

    def test_get_content_text_file(self, service):
        """Test getting content of a text file."""
        workspace = service.workspace
        (workspace / "test.txt").write_text("Hello, World!")

        content = asyncio.run(service.get_content("test.txt"))

        assert content is not None
        assert content["content"] == "Hello, World!"
        assert content["is_binary"] is False
        assert content["mime_type"] == "text/plain"

    def test_get_content_markdown(self, service):
        """Test getting content of a markdown file."""
        workspace = service.workspace
        (workspace / "readme.md").write_text("# Title\n\nContent")

        content = asyncio.run(service.get_content("readme.md"))

        assert content["content"] == "# Title\n\nContent"
        assert content["type"] == "markdown"

    def test_get_content_json(self, service):
        """Test getting content of a JSON file."""
        workspace = service.workspace
        (workspace / "data.json").write_text('{"key": "value"}')

        content = asyncio.run(service.get_content("data.json"))

        assert content["content"] == '{"key": "value"}'
        assert content["type"] == "json"

    def test_get_content_binary(self, service):
        """Test getting content of a binary file."""
        workspace = service.workspace
        (workspace / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 100)

        content = asyncio.run(service.get_content("image.png"))

        assert content["content"] is None
        assert content["content_base64"] is not None
        assert content["is_binary"] is True

    def test_get_content_not_found(self, service):
        """Test getting content of nonexistent file."""
        content = asyncio.run(service.get_content("nonexistent.txt"))
        assert content is None

    def test_get_content_directory(self, service):
        """Test getting content of a directory fails."""
        workspace = service.workspace
        (workspace / "subdir").mkdir()

        with pytest.raises(ArtifactNotFoundError) as exc_info:
            asyncio.run(service.get_content("subdir"))

        assert "directory" in str(exc_info.value).lower()

    def test_save_content_creates_file(self, service):
        """Test saving text content creates a file."""
        result = asyncio.run(service.save_content("new_file.txt", "New content"))

        assert result is not None
        assert result["path"] == "new_file.txt"

        # Verify file exists
        workspace = service.workspace
        assert (workspace / "new_file.txt").read_text() == "New content"

    def test_save_content_creates_parents(self, service):
        """Test saving content creates parent directories."""
        result = asyncio.run(
            service.save_content("deep/nested/dir/file.txt", "Content")
        )

        workspace = service.workspace
        assert (workspace / "deep/nested/dir/file.txt").exists()

    def test_save_content_overwrites(self, service):
        """Test saving content overwrites existing file."""
        asyncio.run(service.save_content("file.txt", "Original"))
        asyncio.run(service.save_content("file.txt", "Updated"))

        content = asyncio.run(service.get_content("file.txt"))
        assert content["content"] == "Updated"

    def test_save_binary_content(self, service):
        """Test saving binary content."""
        binary_data = b"\x00\x01\x02\x03\x04\x05"
        result = asyncio.run(service.save_binary("binary.bin", binary_data))

        workspace = service.workspace
        assert (workspace / "binary.bin").read_bytes() == binary_data

    def test_delete_file(self, service):
        """Test deleting a file."""
        workspace = service.workspace
        (workspace / "to_delete.txt").write_text("Delete me")

        deleted = asyncio.run(service.delete("to_delete.txt"))

        assert deleted
        assert not (workspace / "to_delete.txt").exists()

    def test_delete_directory(self, service):
        """Test deleting a directory."""
        workspace = service.workspace
        subdir = workspace / "to_delete_dir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("Content")

        deleted = asyncio.run(service.delete("to_delete_dir"))

        assert deleted
        assert not subdir.exists()

    def test_delete_nonexistent(self, service):
        """Test deleting nonexistent file returns False."""
        deleted = asyncio.run(service.delete("nonexistent.txt"))
        assert not deleted

    def test_exists(self, service):
        """Test exists check."""
        assert not asyncio.run(service.exists("test.txt"))

        workspace = service.workspace
        (workspace / "test.txt").write_text("Content")

        assert asyncio.run(service.exists("test.txt"))

    def test_get_raw_path(self, service):
        """Test getting raw filesystem path."""
        workspace = service.workspace
        (workspace / "file.txt").write_text("Content")

        raw_path = asyncio.run(service.get_raw_path("file.txt"))

        assert raw_path == workspace / "file.txt"
        assert raw_path.exists()

    def test_get_raw_path_not_found(self, service):
        """Test getting raw path of nonexistent file."""
        with pytest.raises(ArtifactNotFoundError):
            asyncio.run(service.get_raw_path("nonexistent.txt"))

    def test_create_directory(self, service):
        """Test creating a directory."""
        result = asyncio.run(service.create_directory("new_directory"))

        assert result["is_directory"]
        workspace = service.workspace
        assert (workspace / "new_directory").is_dir()

    def test_create_nested_directory(self, service):
        """Test creating nested directories."""
        result = asyncio.run(service.create_directory("deep/nested/path"))

        workspace = service.workspace
        assert (workspace / "deep/nested/path").is_dir()

    def test_path_traversal_blocked(self, service):
        """Test that path traversal is blocked."""
        with pytest.raises(WorkspaceSecurityError):
            asyncio.run(service.save_content("../escape.txt", "Evil content"))

    def test_file_type_detection(self, service):
        """Test file type detection for various extensions."""
        workspace = service.workspace

        # Test different file types
        test_cases = [
            ("test.md", "markdown"),
            ("test.json", "json"),
            ("test.py", "code"),
            ("test.js", "code"),
            ("test.txt", "text"),
            ("test.pdf", "pdf"),
            ("test.png", "image"),
            ("test.unknown", "binary"),
        ]

        for filename, expected_type in test_cases:
            (workspace / filename).write_bytes(b"content")
            content = asyncio.run(service.get_content(filename))
            assert content["type"] == expected_type, f"Failed for {filename}"

    def test_mime_type_detection(self, service):
        """Test MIME type detection."""
        workspace = service.workspace

        (workspace / "test.json").write_text("{}")
        content = asyncio.run(service.get_content("test.json"))
        assert content["mime_type"] == "application/json"

        (workspace / "test.html").write_text("<html></html>")
        content = asyncio.run(service.get_content("test.html"))
        assert "html" in content["mime_type"]

    def test_version_hash(self, service):
        """Test that content includes version hash."""
        asyncio.run(service.save_content("file.txt", "Content"))

        content = asyncio.run(service.get_content("file.txt"))
        assert "version" in content
        assert len(content["version"]) == 16  # SHA-256 truncated to 16 chars

    def test_version_changes_on_update(self, service):
        """Test that version changes when content changes."""
        asyncio.run(service.save_content("file.txt", "Original"))
        content1 = asyncio.run(service.get_content("file.txt"))

        asyncio.run(service.save_content("file.txt", "Updated"))
        content2 = asyncio.run(service.get_content("file.txt"))

        assert content1["version"] != content2["version"]
