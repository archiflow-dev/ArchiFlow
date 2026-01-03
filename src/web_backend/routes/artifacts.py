"""
Artifact API routes.

Handles artifact CRUD operations for session workspaces.
"""

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Depends
from fastapi.responses import FileResponse
from typing import Optional
from pydantic import BaseModel
import base64

from ..services.artifact_service import ArtifactService, ArtifactNotFoundError
from ..services.workspace_manager import WorkspaceSecurityError, get_workspace_manager
from ..services.storage_manager import StorageLimitError
from ..schemas.artifact import ArtifactList, ArtifactContent, ArtifactInfo, ArtifactCreate

router = APIRouter()


class ArtifactUpdate(BaseModel):
    """Request schema for updating artifact content."""
    content: Optional[str] = None
    content_base64: Optional[str] = None


def get_artifact_service(session_id: str) -> ArtifactService:
    """
    Dependency to get artifact service for a session.

    Note: In production, user_id would come from auth token.
    """
    user_id = "default_user"  # TODO: Get from auth
    return ArtifactService(user_id=user_id, session_id=session_id)


@router.get("/", response_model=ArtifactList)
async def list_artifacts(
    session_id: str,
    path: str = Query("", description="Directory path to list (relative to workspace)"),
):
    """
    List artifacts in a session's workspace.

    Returns a list of files and directories at the specified path.
    """
    service = get_artifact_service(session_id)

    # Ensure workspace exists
    workspace_manager = get_workspace_manager()
    if not workspace_manager.workspace_exists("default_user", session_id):
        workspace_manager.create_workspace("default_user", session_id)

    artifacts = await service.list(path)

    return ArtifactList(
        artifacts=[
            ArtifactInfo(
                name=a["name"],
                path=a["path"],
                is_directory=a["is_directory"],
                size=a.get("size"),
                mime_type=a.get("mime_type"),
                modified_at=a["modified_at"],
            )
            for a in artifacts
        ],
        path=path or "/",
        total=len(artifacts),
    )


@router.get("/{path:path}")
async def get_artifact(
    session_id: str,
    path: str,
    raw: bool = Query(False, description="Return raw file content"),
):
    """
    Get the content of a specific artifact.

    For text files, returns content as string.
    For binary files, returns base64-encoded content.
    If raw=true, returns the raw file for download.
    """
    service = get_artifact_service(session_id)

    try:
        if raw:
            # Return raw file
            file_path = await service.get_raw_path(path)
            return FileResponse(
                file_path,
                filename=file_path.name,
                media_type=service._get_mime_type(file_path),
            )

        content = await service.get_content(path)
        if not content:
            raise HTTPException(status_code=404, detail="Artifact not found")

        return ArtifactContent(
            path=content["path"],
            content=content.get("content"),
            content_base64=content.get("content_base64"),
            mime_type=content["mime_type"],
            size=content["size"],
            is_binary=content["is_binary"],
        )

    except ArtifactNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/", response_model=ArtifactInfo, status_code=201)
async def create_artifact(
    session_id: str,
    data: ArtifactCreate,
):
    """
    Create a new artifact.

    Accepts either text content or base64-encoded binary content.
    """
    service = get_artifact_service(session_id)

    # Ensure workspace exists
    workspace_manager = get_workspace_manager()
    if not workspace_manager.workspace_exists("default_user", session_id):
        workspace_manager.create_workspace("default_user", session_id)

    try:
        if data.content is not None:
            result = await service.save_content(data.path, data.content)
        elif data.content_base64 is not None:
            content = base64.b64decode(data.content_base64)
            result = await service.save_binary(data.path, content)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either content or content_base64 must be provided"
            )

        return ArtifactInfo(
            name=result["path"].split("/")[-1],
            path=result["path"],
            is_directory=False,
            size=result["size"],
            mime_type=result["mime_type"],
            modified_at=result["modified_at"],
        )

    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except StorageLimitError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.put("/{path:path}", response_model=ArtifactInfo)
async def update_artifact(
    session_id: str,
    path: str,
    data: ArtifactUpdate,
):
    """
    Update an existing artifact's content.
    """
    service = get_artifact_service(session_id)

    try:
        if data.content is not None:
            result = await service.save_content(path, data.content)
        elif data.content_base64 is not None:
            content = base64.b64decode(data.content_base64)
            result = await service.save_binary(path, content)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either content or content_base64 must be provided"
            )

        return ArtifactInfo(
            name=result["path"].split("/")[-1],
            path=result["path"],
            is_directory=False,
            size=result["size"],
            mime_type=result["mime_type"],
            modified_at=result["modified_at"],
        )

    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except StorageLimitError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.delete("/{path:path}", status_code=204)
async def delete_artifact(
    session_id: str,
    path: str,
):
    """
    Delete an artifact.
    """
    service = get_artifact_service(session_id)

    try:
        deleted = await service.delete(path)
        if not deleted:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return None

    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/{path:path}/download")
async def download_artifact(
    session_id: str,
    path: str,
):
    """
    Download an artifact as a file.
    """
    service = get_artifact_service(session_id)

    try:
        file_path = await service.get_raw_path(path)
        return FileResponse(
            file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    except ArtifactNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/upload", response_model=ArtifactInfo, status_code=201)
async def upload_artifact(
    session_id: str,
    file: UploadFile = File(...),
    path: str = Query("", description="Target directory path"),
):
    """
    Upload a file as an artifact.
    """
    service = get_artifact_service(session_id)

    # Ensure workspace exists
    workspace_manager = get_workspace_manager()
    if not workspace_manager.workspace_exists("default_user", session_id):
        workspace_manager.create_workspace("default_user", session_id)

    try:
        # Determine target path
        target_path = f"{path}/{file.filename}" if path else file.filename

        # Read file content
        content = await file.read()

        # Save binary content
        result = await service.save_binary(target_path, content)

        return ArtifactInfo(
            name=result["path"].split("/")[-1],
            path=result["path"],
            is_directory=False,
            size=result["size"],
            mime_type=result["mime_type"],
            modified_at=result["modified_at"],
        )

    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except StorageLimitError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.post("/directory", status_code=201)
async def create_directory(
    session_id: str,
    path: str = Query(..., description="Directory path to create"),
):
    """
    Create a directory.
    """
    service = get_artifact_service(session_id)

    # Ensure workspace exists
    workspace_manager = get_workspace_manager()
    if not workspace_manager.workspace_exists("default_user", session_id):
        workspace_manager.create_workspace("default_user", session_id)

    try:
        result = await service.create_directory(path)
        return result

    except WorkspaceSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))
