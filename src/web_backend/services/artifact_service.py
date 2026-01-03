"""
Artifact Service for ArchiFlow Web Backend.

Manages file artifacts within session workspaces.
"""

from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime
import mimetypes
import base64
import hashlib
import aiofiles
import aiofiles.os
import logging

from .workspace_manager import WorkspaceManager, WorkspaceSecurityError, get_workspace_manager
from .storage_manager import StorageManager, StorageLimitError, get_storage_manager

logger = logging.getLogger(__name__)

# Initialize mimetypes
mimetypes.init()


class ArtifactNotFoundError(Exception):
    """Raised when an artifact is not found."""
    pass


class ArtifactService:
    """
    Service for managing artifacts within a session workspace.

    All file operations are sandboxed to the session workspace
    via WorkspaceManager path validation.
    """

    # File type categories
    TEXT_EXTENSIONS = {'.md', '.markdown', '.txt', '.json', '.yaml', '.yml', '.xml', '.html', '.css'}
    CODE_EXTENSIONS = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.cpp', '.c', '.h'}
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp'}
    DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}

    def __init__(
        self,
        user_id: str,
        session_id: str,
        workspace_manager: Optional[WorkspaceManager] = None,
        storage_manager: Optional[StorageManager] = None
    ):
        """
        Initialize ArtifactService.

        Args:
            user_id: User ID
            session_id: Session ID
            workspace_manager: WorkspaceManager instance
            storage_manager: StorageManager instance
        """
        self.user_id = user_id
        self.session_id = session_id
        self.workspace_manager = workspace_manager or get_workspace_manager()
        self.storage_manager = storage_manager or get_storage_manager()
        self.workspace = self.workspace_manager.get_workspace_path(user_id, session_id)

    def _safe_path(self, path: str) -> Path:
        """
        Validate and return safe path within workspace.

        Args:
            path: Relative path

        Returns:
            Absolute safe path

        Raises:
            WorkspaceSecurityError: If path escapes workspace
        """
        return self.workspace_manager.validate_path(self.workspace, path)

    def _detect_file_type(self, path: Path) -> str:
        """
        Detect the type category of a file.

        Args:
            path: Path to file

        Returns:
            Type category: 'markdown', 'json', 'code', 'image', 'pdf', 'document', or 'binary'
        """
        suffix = path.suffix.lower()

        if suffix in {'.md', '.markdown'}:
            return 'markdown'
        elif suffix == '.json':
            return 'json'
        elif suffix in self.CODE_EXTENSIONS:
            return 'code'
        elif suffix in self.IMAGE_EXTENSIONS:
            return 'image'
        elif suffix == '.pdf':
            return 'pdf'
        elif suffix in self.DOCUMENT_EXTENSIONS:
            return 'document'
        elif suffix in self.TEXT_EXTENSIONS:
            return 'text'
        else:
            return 'binary'

    def _get_mime_type(self, path: Path) -> str:
        """Get MIME type for a file."""
        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or 'application/octet-stream'

    def _compute_hash(self, content: Union[str, bytes]) -> str:
        """Compute SHA-256 hash of content."""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.sha256(content).hexdigest()[:16]

    async def list(self, subpath: str = "") -> List[dict]:
        """
        List artifacts in a directory.

        Args:
            subpath: Subdirectory path (relative to workspace)

        Returns:
            List of artifact info dicts
        """
        try:
            target = self._safe_path(subpath) if subpath else self.workspace
        except WorkspaceSecurityError:
            return []

        if not target.exists():
            return []

        artifacts = []
        try:
            for item in target.iterdir():
                # Skip hidden metadata directory
                if item.name == ".archiflow":
                    continue

                try:
                    stat = item.stat()
                    artifact = {
                        "name": item.name,
                        "path": str(item.relative_to(self.workspace)),
                        "type": self._detect_file_type(item) if item.is_file() else "directory",
                        "mime_type": self._get_mime_type(item) if item.is_file() else None,
                        "size": stat.st_size if item.is_file() else None,
                        "is_directory": item.is_dir(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                    artifacts.append(artifact)
                except OSError as e:
                    logger.warning(f"Error reading artifact {item}: {e}")

        except PermissionError as e:
            logger.error(f"Permission error listing {target}: {e}")
            return []

        # Sort: directories first, then by name
        return sorted(artifacts, key=lambda x: (not x["is_directory"], x["name"].lower()))

    async def get_content(self, path: str) -> Optional[dict]:
        """
        Get artifact content.

        Args:
            path: Relative path to artifact

        Returns:
            Dict with type and content, or None if not found
        """
        try:
            file_path = self._safe_path(path)
        except WorkspaceSecurityError as e:
            raise ArtifactNotFoundError(f"Invalid path: {e}")

        if not file_path.exists():
            return None

        if not file_path.is_file():
            raise ArtifactNotFoundError(f"Path is a directory: {path}")

        file_type = self._detect_file_type(file_path)
        mime_type = self._get_mime_type(file_path)
        stat = file_path.stat()

        result = {
            "path": path,
            "type": file_type,
            "mime_type": mime_type,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

        # Return content based on type
        if file_type in ('markdown', 'json', 'code', 'text'):
            # Text content - read as string
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                result["content"] = content
                result["content_base64"] = None
                result["is_binary"] = False
                result["version"] = self._compute_hash(content)
            except UnicodeDecodeError:
                # Fall back to binary
                async with aiofiles.open(file_path, 'rb') as f:
                    content = await f.read()
                result["content"] = None
                result["content_base64"] = base64.b64encode(content).decode('ascii')
                result["is_binary"] = True
                result["version"] = self._compute_hash(content)
        else:
            # Binary content - return base64 or URL
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            result["content"] = None
            result["content_base64"] = base64.b64encode(content).decode('ascii')
            result["is_binary"] = True
            result["version"] = self._compute_hash(content)

        return result

    async def save_content(
        self,
        path: str,
        content: str,
        create_parents: bool = True
    ) -> dict:
        """
        Save text content to an artifact.

        Args:
            path: Relative path to artifact
            content: Text content to save
            create_parents: Create parent directories if needed

        Returns:
            Artifact info dict
        """
        file_path = self._safe_path(path)

        # Check storage quota
        content_bytes = content.encode('utf-8')
        self.storage_manager.check_file_upload(
            self.user_id,
            self.session_id,
            len(content_bytes)
        )

        # Create parent directories
        if create_parents:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)

        logger.info(f"Saved artifact: {path} ({len(content_bytes)} bytes)")

        return await self.get_content(path)

    async def save_binary(
        self,
        path: str,
        content: bytes,
        create_parents: bool = True
    ) -> dict:
        """
        Save binary content to an artifact.

        Args:
            path: Relative path to artifact
            content: Binary content to save
            create_parents: Create parent directories if needed

        Returns:
            Artifact info dict
        """
        file_path = self._safe_path(path)

        # Check storage quota
        self.storage_manager.check_file_upload(
            self.user_id,
            self.session_id,
            len(content)
        )

        # Create parent directories
        if create_parents:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        logger.info(f"Saved binary artifact: {path} ({len(content)} bytes)")

        return await self.get_content(path)

    async def delete(self, path: str) -> bool:
        """
        Delete an artifact.

        Args:
            path: Relative path to artifact

        Returns:
            True if deleted, False if not found
        """
        file_path = self._safe_path(path)

        if not file_path.exists():
            return False

        if file_path.is_dir():
            import shutil
            shutil.rmtree(file_path)
        else:
            file_path.unlink()

        logger.info(f"Deleted artifact: {path}")
        return True

    async def exists(self, path: str) -> bool:
        """Check if an artifact exists."""
        try:
            file_path = self._safe_path(path)
            return file_path.exists()
        except WorkspaceSecurityError:
            return False

    async def get_raw_path(self, path: str) -> Path:
        """
        Get the raw filesystem path for an artifact.

        For serving files directly (e.g., FileResponse).

        Args:
            path: Relative path to artifact

        Returns:
            Absolute path

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
        """
        file_path = self._safe_path(path)

        if not file_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {path}")

        return file_path

    async def create_directory(self, path: str) -> dict:
        """
        Create a directory.

        Args:
            path: Relative path

        Returns:
            Directory info dict
        """
        dir_path = self._safe_path(path)
        dir_path.mkdir(parents=True, exist_ok=True)

        return {
            "name": dir_path.name,
            "path": path,
            "type": "directory",
            "is_directory": True,
        }
