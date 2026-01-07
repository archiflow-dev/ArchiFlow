"""
Workspace API routes.

Handles file operations within agent workspace directories.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class FileInfo(BaseModel):
    """Information about a file in the workspace."""
    name: str
    path: str
    type: str  # 'file' or 'directory'
    size: int = 0
    extension: Optional[str] = None
    modified_time: Optional[float] = None


class FileContent(BaseModel):
    """Content of a file."""
    path: str
    content: str
    encoding: str = "utf-8"


class FileWriteRequest(BaseModel):
    """Request model for writing file content."""
    content: str
    encoding: str = "utf-8"


class FileListResponse(BaseModel):
    """Response model for file listing."""
    files: List[FileInfo]
    total_count: int


def _validate_session_path(session_id: str) -> Path:
    """
    Validate and get the workspace path for a session.

    Args:
        session_id: Session ID

    Returns:
        Path to the session workspace

    Raises:
        HTTPException: If session path is invalid
    """
    # Import here to avoid circular imports
    from ..services.workspace_manager import get_workspace_manager

    workspace_manager = get_workspace_manager()
    # Get all workspaces for default_user and find the matching one
    workspaces_dir = workspace_manager.base_path / "default_user"

    if not workspaces_dir.exists():
        raise HTTPException(status_code=404, detail=f"Session workspace not found: {session_id}")

    # Find the session directory
    session_path = workspaces_dir / session_id
    if not session_path.exists():
        raise HTTPException(status_code=404, detail=f"Session workspace not found: {session_id}")

    return session_path


def _get_file_info(file_path: Path, relative_path: str) -> FileInfo:
    """
    Get file information.

    Args:
        file_path: Absolute path to the file
        relative_path: Relative path from workspace root

    Returns:
        FileInfo object
    """
    stat = file_path.stat() if file_path.exists() else os.stat(file_path)

    file_type = "directory" if file_path.is_dir() else "file"
    extension = file_path.suffix if file_path.is_file() else None

    return FileInfo(
        name=file_path.name,
        path=relative_path.replace("\\", "/"),  # Normalize path separators
        type=file_type,
        size=stat.st_size,
        extension=extension[1:] if extension else None,  # Remove the dot
        modified_time=stat.st_mtime,
    )


@router.get("/sessions/{session_id}/files", response_model=FileListResponse)
async def list_workspace_files(
    session_id: str,
    path: str = Query("", description="Relative path within workspace (default: root)"),
    recursive: bool = Query(False, description="List files recursively"),
) -> FileListResponse:
    """
    List files in a session's workspace directory.

    Note: .archiflow/ audit directory and logs/ folders are always filtered out for security and UX.

    Args:
        session_id: Session ID
        path: Relative path within workspace to list
        recursive: Whether to list files recursively

    Returns:
        List of files in the workspace
    """
    try:
        session_path = _validate_session_path(session_id)

        # Get the target directory
        target_path = session_path / path if path else session_path
        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")

        files = []

        if recursive:
            # Recursively list all files
            for item in sorted(target_path.rglob("*")):
                try:
                    relative = item.relative_to(session_path)
                    relative_str = str(relative)

                    # Always filter out .archiflow/ audit directory and logs/ folders
                    parts = relative.parts
                    if len(parts) > 0 and (
                        parts[0] == ".archiflow" or
                        "logs" in parts
                    ):
                        continue

                    files.append(_get_file_info(item, relative_str))
                except (ValueError, OSError) as e:
                    logger.warning(f"Skipping {item}: {e}")
        else:
            # List only immediate children
            for item in sorted(target_path.iterdir()):
                try:
                    relative = item.relative_to(session_path)
                    relative_str = str(relative)

                    # Always filter out .archiflow/ audit directory and logs/ folders
                    if item.name in (".archiflow", "logs"):
                        continue

                    files.append(_get_file_info(item, relative_str))
                except (ValueError, OSError) as e:
                    logger.warning(f"Skipping {item}: {e}")

        logger.info(f"Listed {len(files)} items in workspace {session_id} (path={path}, recursive={recursive})")

        return FileListResponse(
            files=files,
            total_count=len(files)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing workspace files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/sessions/{session_id}/files/content")
async def read_workspace_file(
    request: Request,
    session_id: str,
    path: str = Query(..., description="Relative path to the file within workspace"),
    encoding: str = Query("utf-8", description="File encoding"),
):  # Returns FileContent for text files, FileResponse for binary files
    """
    Read the content of a file in the session's workspace.

    Note: For binary files (images, PDFs, etc.), this endpoint will return
    the raw binary data with appropriate content-type.

    Args:
        session_id: Session ID
        path: Relative path to the file
        encoding: File encoding (default: utf-8, only used for text files)

    Returns:
        File content (text) or binary data for images/PDFs
    """
    try:
        session_path = _validate_session_path(session_id)
        file_path = session_path / path

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail=f"Path is not a file: {path}")

        # Binary file extensions
        binary_extensions = {
            'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico',
            'pdf', 'zip', 'tar', 'gz', 'rar', '7z',
            'mp3', 'mp4', 'wav', 'avi', 'mov', 'wmv',
            'ttf', 'otf', 'woff', 'woff2', 'eot',
        }

        file_extension = file_path.suffix.lstrip('.').lower()

        # Check if this is a binary file
        if file_extension in binary_extensions:
            # For binary files, use FileResponse to serve the raw data
            logger.info(f"Serving binary file {path} from workspace {session_id}")

            # Set appropriate media type
            media_types = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'svg': 'image/svg+xml',
                'ico': 'image/x-icon',
                'pdf': 'application/pdf',
                'zip': 'application/zip',
                'tar': 'application/x-tar',
                'gz': 'application/gzip',
                'mp3': 'audio/mpeg',
                'mp4': 'video/mp4',
                'wav': 'audio/wav',
                'ttf': 'font/ttf',
                'otf': 'font/otf',
                'woff': 'font/woff',
                'woff2': 'font/woff2',
            }

            media_type = media_types.get(file_extension, 'application/octet-stream')

            # Get origin from request for CORS
            origin = request.headers.get("origin")

            # Manually add CORS headers for FileResponse
            # FileResponse doesn't go through CORSMiddleware properly
            headers = {}
            if origin:
                # In production, you should validate the origin against allowed origins
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Credentials"] = "true"
                headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                headers["Access-Control-Allow-Headers"] = "*"

            return FileResponse(
                path=str(file_path),
                media_type=media_type,
                filename=file_path.name,
                headers=headers,
            )

        # For text files, read and return content
        content = file_path.read_text(encoding=encoding)

        logger.info(f"Read text file {path} from workspace {session_id} ({len(content)} chars)")

        return FileContent(
            path=path.replace("\\", "/"),
            content=content,
            encoding=encoding,
        )

    except HTTPException:
        raise
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to decode file with encoding {encoding}")
    except Exception as e:
        logger.error(f"Error reading workspace file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.put("/sessions/{session_id}/files/content")
async def write_workspace_file(
    session_id: str,
    request: FileWriteRequest,
    path: str = Query(..., description="Relative path to the file within workspace"),
) -> FileContent:
    """
    Write content to a file in the session's workspace.

    Args:
        session_id: Session ID
        path: Relative path to the file
        request: Write request with content and encoding

    Returns:
        Updated file content
    """
    try:
        session_path = _validate_session_path(session_id)
        file_path = session_path / path

        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file content
        file_path.write_text(request.content, encoding=request.encoding)

        logger.info(f"Wrote file {path} in workspace {session_id} ({len(request.content)} chars)")

        return FileContent(
            path=path.replace("\\", "/"),
            content=request.content,
            encoding=request.encoding,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error writing workspace file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")
