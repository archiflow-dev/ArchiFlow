"""
Tests for comment API endpoints and service.

Tests cover:
- Comment CRUD operations
- File-based storage
- Filtering and pagination
- Agent submission flow
- Error handling
"""

import json
import pytest
from pathlib import Path
from httpx import AsyncClient

from src.web_backend.models.comment import (
    Comment,
    CommentCreate,
    CommentUpdate,
    CommentStatus,
)
from src.web_backend.services.comment_service import (
    CommentService,
    CommentNotFoundError,
    CommentServiceError,
)
from src.web_backend.services.workspace_manager import WorkspaceManager
from src.web_backend.services.session_store import SessionStore, SessionInfo


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def workspace_dir(tmp_path):
    """Create a temporary workspace directory."""
    workspace_dir = tmp_path / "workspaces"
    workspace_dir.mkdir()
    return workspace_dir


@pytest.fixture
def workspace_manager(workspace_dir):
    """Create a workspace manager for testing."""
    return WorkspaceManager(base_path=str(workspace_dir))


@pytest.fixture
def comment_service(workspace_manager):
    """Create a comment service for testing."""
    return CommentService(workspace_manager=workspace_manager)


@pytest.fixture
def sample_comment_data():
    """Sample comment creation data."""
    return {
        "file_path": "docs/chapter1.md",
        "line_number": 23,
        "selected_text": "The quick brown fox",
        "comment_text": "This should be more descriptive",
    }


@pytest.fixture
def sample_session_data():
    """Sample session data."""
    return {
        "agent_type": "comic",
        "user_prompt": "Create a comic",
    }


@pytest.fixture
async def test_session(client: AsyncClient, sample_session_data: dict):
    """Create a test session and return its ID."""
    response = await client.post("/api/sessions/", json=sample_session_data)
    assert response.status_code == 201
    return response.json()["id"]


# ============================================================================
# Service Tests
# ============================================================================

class TestCommentService:
    """Tests for CommentService."""

    @pytest.mark.asyncio
    async def test_create_comment(self, comment_service: CommentService):
        """Test creating a comment."""
        comment_create = CommentCreate(
            file_path="test.md",
            line_number=1,
            comment_text="Test comment",
        )

        comment = comment_service.create_comment(
            comment_create=comment_create,
            session_id="test_session",
        )

        assert comment.id.startswith("comment_")
        assert comment.session_id == "test_session"
        assert comment.file_path == "test.md"
        assert comment.line_number == 1
        assert comment.comment_text == "Test comment"
        assert comment.status == CommentStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_comment_with_selected_text(self, comment_service: CommentService):
        """Test creating a comment with selected text."""
        comment_create = CommentCreate(
            file_path="test.md",
            line_number=5,
            selected_text="Selected text",
            comment_text="Comment on selection",
        )

        comment = comment_service.create_comment(
            comment_create=comment_create,
            session_id="test_session",
        )

        assert comment.selected_text == "Selected text"

    @pytest.mark.asyncio
    async def test_list_comments_empty(self, comment_service: CommentService):
        """Test listing comments when none exist."""
        comments = comment_service.list_comments(session_id="empty_session")
        assert comments == []

    @pytest.mark.asyncio
    async def test_list_comments(self, comment_service: CommentService):
        """Test listing comments."""
        session_id = "test_session"

        # Create multiple comments
        for i in range(3):
            comment_create = CommentCreate(
                file_path=f"file{i}.md",
                line_number=i + 1,
                comment_text=f"Comment {i}",
            )
            comment_service.create_comment(comment_create, session_id)

        # List all comments
        comments = comment_service.list_comments(session_id=session_id)
        assert len(comments) == 3

    @pytest.mark.asyncio
    async def test_list_comments_filter_by_file(self, comment_service: CommentService):
        """Test filtering comments by file path."""
        session_id = "test_session"

        # Create comments for different files
        comment_service.create_comment(
            CommentCreate(file_path="file1.md", line_number=1, comment_text="Comment 1"),
            session_id,
        )
        comment_service.create_comment(
            CommentCreate(file_path="file2.md", line_number=1, comment_text="Comment 2"),
            session_id,
        )
        comment_service.create_comment(
            CommentCreate(file_path="file1.md", line_number=2, comment_text="Comment 3"),
            session_id,
        )

        # Filter by file
        comments = comment_service.list_comments(session_id=session_id, file_path="file1.md")
        assert len(comments) == 2
        assert all(c.file_path == "file1.md" for c in comments)

    @pytest.mark.asyncio
    async def test_list_comments_filter_by_status(self, comment_service: CommentService):
        """Test filtering comments by status."""
        session_id = "test_session"

        # Create comments with different statuses
        comment1 = comment_service.create_comment(
            CommentCreate(file_path="file.md", line_number=1, comment_text="Pending"),
            session_id,
        )

        comment2 = comment_service.create_comment(
            CommentCreate(file_path="file.md", line_number=2, comment_text="Resolved"),
            session_id,
        )

        # Update one comment to resolved
        comment_service.update_comment(
            comment_id=comment2.id,
            comment_update=CommentUpdate(status=CommentStatus.RESOLVED),
            session_id=session_id,
        )

        # Filter pending comments
        pending = comment_service.list_comments(
            session_id=session_id,
            status=CommentStatus.PENDING,
        )
        assert len(pending) == 1
        assert pending[0].id == comment1.id

    @pytest.mark.asyncio
    async def test_get_comment(self, comment_service: CommentService):
        """Test getting a specific comment."""
        comment_create = CommentCreate(
            file_path="test.md",
            line_number=1,
            comment_text="Test comment",
        )

        created = comment_service.create_comment(comment_create, "test_session")
        retrieved = comment_service.get_comment(created.id, "test_session")

        assert retrieved.id == created.id
        assert retrieved.comment_text == "Test comment"

    @pytest.mark.asyncio
    async def test_get_comment_not_found(self, comment_service: CommentService):
        """Test getting a non-existent comment."""
        with pytest.raises(CommentNotFoundError):
            comment_service.get_comment("nonexistent_id", "test_session")

    @pytest.mark.asyncio
    async def test_update_comment_text(self, comment_service: CommentService):
        """Test updating comment text."""
        comment = comment_service.create_comment(
            CommentCreate(file_path="test.md", line_number=1, comment_text="Original"),
            "test_session",
        )

        updated = comment_service.update_comment(
            comment_id=comment.id,
            comment_update=CommentUpdate(comment_text="Updated"),
            session_id="test_session",
        )

        assert updated.comment_text == "Updated"
        assert updated.updated_at != comment.updated_at

    @pytest.mark.asyncio
    async def test_update_comment_status(self, comment_service: CommentService):
        """Test updating comment status."""
        comment = comment_service.create_comment(
            CommentCreate(file_path="test.md", line_number=1, comment_text="Test"),
            "test_session",
        )

        updated = comment_service.update_comment(
            comment_id=comment.id,
            comment_update=CommentUpdate(status=CommentStatus.RESOLVED),
            session_id="test_session",
        )

        assert updated.status == CommentStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_update_comment_both_fields(self, comment_service: CommentService):
        """Test updating both comment text and status."""
        comment = comment_service.create_comment(
            CommentCreate(file_path="test.md", line_number=1, comment_text="Original"),
            "test_session",
        )

        updated = comment_service.update_comment(
            comment_id=comment.id,
            comment_update=CommentUpdate(
                comment_text="Updated text",
                status=CommentStatus.RESOLVED,
            ),
            session_id="test_session",
        )

        assert updated.comment_text == "Updated text"
        assert updated.status == CommentStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_delete_comment(self, comment_service: CommentService):
        """Test deleting a comment."""
        comment = comment_service.create_comment(
            CommentCreate(file_path="test.md", line_number=1, comment_text="Test"),
            "test_session",
        )

        # Delete the comment
        comment_service.delete_comment(comment.id, "test_session")

        # Verify it's gone
        with pytest.raises(CommentNotFoundError):
            comment_service.get_comment(comment.id, "test_session")

    @pytest.mark.asyncio
    async def test_delete_comment_not_found(self, comment_service: CommentService):
        """Test deleting a non-existent comment."""
        with pytest.raises(CommentNotFoundError):
            comment_service.delete_comment("nonexistent_id", "test_session")

    @pytest.mark.asyncio
    async def test_get_pending_comments(self, comment_service: CommentService):
        """Test getting pending comments for agent submission."""
        session_id = "test_session"

        # Create comments with different statuses
        comment1 = comment_service.create_comment(
            CommentCreate(file_path="file.md", line_number=1, comment_text="Pending 1"),
            session_id,
        )

        comment2 = comment_service.create_comment(
            CommentCreate(file_path="file.md", line_number=2, comment_text="Pending 2"),
            session_id,
        )

        comment3 = comment_service.create_comment(
            CommentCreate(file_path="file.md", line_number=3, comment_text="Resolved"),
            session_id,
        )

        # Mark one as resolved
        comment_service.update_comment(
            comment_id=comment3.id,
            comment_update=CommentUpdate(status=CommentStatus.RESOLVED),
            session_id=session_id,
        )

        # Get pending comments
        pending = comment_service.get_pending_comments(session_id=session_id)
        assert len(pending) == 2
        pending_ids = {c.id for c in pending}
        assert comment1.id in pending_ids
        assert comment2.id in pending_ids
        assert comment3.id not in pending_ids

    @pytest.mark.asyncio
    async def test_mark_comments_submitted(self, comment_service: CommentService):
        """Test marking comments as submitted."""
        session_id = "test_session"

        # Create pending comments
        comment1 = comment_service.create_comment(
            CommentCreate(file_path="file.md", line_number=1, comment_text="Comment 1"),
            session_id,
        )

        comment2 = comment_service.create_comment(
            CommentCreate(file_path="file.md", line_number=2, comment_text="Comment 2"),
            session_id,
        )

        # Mark as submitted
        count = comment_service.mark_comments_submitted(
            comment_ids=[comment1.id, comment2.id],
            session_id=session_id,
        )

        assert count == 2

        # Verify status
        updated1 = comment_service.get_comment(comment1.id, session_id)
        updated2 = comment_service.get_comment(comment2.id, session_id)
        assert updated1.status == CommentStatus.SUBMITTED
        assert updated2.status == CommentStatus.SUBMITTED

    @pytest.mark.asyncio
    async def test_format_comments_for_agent(self, comment_service: CommentService):
        """Test formatting comments for agent submission."""
        comments = [
            Comment(
                id="c1",
                session_id="s1",
                file_path="chapter1.md",
                line_number=10,
                selected_text="Original text 1",
                comment_text="Fix this",
            ),
            Comment(
                id="c2",
                session_id="s1",
                file_path="chapter1.md",
                line_number=20,
                selected_text="Original text 2",
                comment_text="Also fix this",
            ),
        ]

        formatted = comment_service.format_comments_for_agent(comments)

        assert "chapter1.md" in formatted
        assert "Line 10" in formatted
        assert "Line 20" in formatted
        assert "Original text 1" in formatted
        assert "Fix this" in formatted
        assert "Also fix this" in formatted

    @pytest.mark.asyncio
    async def test_format_comments_for_agent_multiple_files(self, comment_service: CommentService):
        """Test formatting comments across multiple files."""
        comments = [
            Comment(
                id="c1",
                session_id="s1",
                file_path="file1.md",
                line_number=1,
                selected_text="Text 1",
                comment_text="Comment 1",
            ),
            Comment(
                id="c2",
                session_id="s1",
                file_path="file2.md",
                line_number=5,
                selected_text="Text 2",
                comment_text="Comment 2",
            ),
        ]

        formatted = comment_service.format_comments_for_agent(comments)

        assert "file1.md" in formatted
        assert "file2.md" in formatted
        assert "Line 1" in formatted
        assert "Line 5" in formatted

    @pytest.mark.asyncio
    async def test_persistence_saves_to_file(self, comment_service: CommentService, workspace_dir):
        """Test that comments are persisted to JSON file."""
        session_id = "persist_session"
        user_id = "default_user"

        # Create a comment
        comment = comment_service.create_comment(
            CommentCreate(file_path="test.md", line_number=1, comment_text="Persist me"),
            session_id,
            user_id,
        )

        # Check file exists
        comments_file = workspace_dir / user_id / session_id / ".comments.json"
        assert comments_file.exists()

        # Verify content
        with open(comments_file, 'r') as f:
            data = json.load(f)
            assert "comments" in data
            assert len(data["comments"]) == 1
            assert data["comments"][0]["id"] == comment.id

    @pytest.mark.asyncio
    async def test_persistence_loads_from_file(self, comment_service: CommentService, workspace_dir):
        """Test that comments are loaded from existing JSON file."""
        session_id = "load_session"
        user_id = "default_user"

        # Manually create comments file
        workspace_path = workspace_dir / user_id / session_id
        workspace_path.mkdir(parents=True)
        comments_file = workspace_path / ".comments.json"

        existing_comments = {
            "comments": [
                {
                    "id": "comment_existing",
                    "session_id": session_id,
                    "file_path": "existing.md",
                    "line_number": 1,
                    "selected_text": "Existing",
                    "comment_text": "Pre-existing comment",
                    "author": "test_user",
                    "status": "pending",
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            ]
        }

        with open(comments_file, 'w') as f:
            json.dump(existing_comments, f)

        # Load comments
        comments = comment_service.list_comments(session_id=session_id, user_id=user_id)

        assert len(comments) == 1
        assert comments[0].id == "comment_existing"
        assert comments[0].comment_text == "Pre-existing comment"


# ============================================================================
# API Tests
# ============================================================================

class TestCommentsAPI:
    """Tests for comments API endpoints."""

    @pytest.mark.asyncio
    async def test_create_comment_endpoint(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test creating a comment via API."""
        response = await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["file_path"] == sample_comment_data["file_path"]
        assert data["line_number"] == sample_comment_data["line_number"]
        assert data["comment_text"] == sample_comment_data["comment_text"]
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_comment_validation_error(self, client: AsyncClient, test_session: str):
        """Test comment creation with invalid data."""
        invalid_data = {
            "file_path": "",  # Empty file path
            "line_number": -1,  # Invalid line number
            "comment_text": "",  # Empty comment
        }

        response = await client.post(
            f"/api/sessions/{test_session}/comments",
            json=invalid_data,
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_comments_empty(
        self,
        client: AsyncClient,
        test_session: str,
    ):
        """Test listing comments when none exist."""
        response = await client.get(f"/api/sessions/{test_session}/comments")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["comments"] == []

    @pytest.mark.asyncio
    async def test_list_comments_with_data(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test listing comments after creating some."""
        # Create comments
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json={**sample_comment_data, "line_number": 10, "comment_text": "Second comment"},
        )

        # List comments
        response = await client.get(f"/api/sessions/{test_session}/comments")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["comments"]) == 2

    @pytest.mark.asyncio
    async def test_list_comments_by_file(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test filtering comments by file path."""
        # Create comments for different files
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json={**sample_comment_data, "file_path": "other.md"},
        )

        # Filter by file
        response = await client.get(
            f"/api/sessions/{test_session}/comments",
            params={"file_path": sample_comment_data["file_path"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["comments"][0]["file_path"] == sample_comment_data["file_path"]

    @pytest.mark.asyncio
    async def test_list_file_comments(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test listing comments for a specific file."""
        # Create comments
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )

        # List comments for file
        response = await client.get(
            f"/api/sessions/{test_session}/files/{sample_comment_data['file_path']}/comments",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["file_path"] == sample_comment_data["file_path"]

    @pytest.mark.asyncio
    async def test_get_comment(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test getting a specific comment."""
        # Create a comment
        create_response = await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        comment_id = create_response.json()["id"]

        # Get the comment
        response = await client.get(
            f"/api/comments/{comment_id}",
            params={"session_id": test_session},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == comment_id

    @pytest.mark.asyncio
    async def test_get_comment_not_found(self, client: AsyncClient, test_session: str):
        """Test getting a non-existent comment."""
        response = await client.get(
            "/comments/nonexistent_id",
            params={"session_id": test_session},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_comment(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test updating a comment."""
        # Create a comment
        create_response = await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        comment_id = create_response.json()["id"]

        # Update the comment
        update_data = {"comment_text": "Updated comment"}
        response = await client.put(
            f"/api/comments/{comment_id}",
            params={"session_id": test_session},
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["comment_text"] == "Updated comment"

    @pytest.mark.asyncio
    async def test_resolve_comment(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test resolving a comment."""
        # Create a comment
        create_response = await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        comment_id = create_response.json()["id"]

        # Resolve the comment
        response = await client.post(
            f"/api/comments/{comment_id}/resolve",
            params={"session_id": test_session},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_delete_comment(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test deleting a comment."""
        # Create a comment
        create_response = await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        comment_id = create_response.json()["id"]

        # Delete the comment
        response = await client.delete(
            f"/api/comments/{comment_id}",
            params={"session_id": test_session},
        )

        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(
            f"/api/comments/{comment_id}",
            params={"session_id": test_session},
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_pending_comments(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test getting pending comments."""
        # Create comments
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )

        # Get pending comments
        response = await client.get(f"/api/sessions/{test_session}/comments/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1

    @pytest.mark.asyncio
    async def test_submit_comments_to_agent(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test submitting comments to agent."""
        # Create pending comments
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json={**sample_comment_data, "line_number": 5, "comment_text": "Second comment"},
        )

        # Submit to agent
        response = await client.post(
            f"/api/sessions/{test_session}/comments/submit-to-agent",
            json={"file_path": None, "prompt_override": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["submitted_count"] == 2
        assert len(data["comment_ids"]) == 2

        # Verify comments are marked as submitted
        list_response = await client.get(
            f"/api/sessions/{test_session}/comments",
            params={"status": "submitted"},
        )
        list_data = list_response.json()
        assert list_data["total_count"] == 2

    @pytest.mark.asyncio
    async def test_submit_comments_for_specific_file(
        self,
        client: AsyncClient,
        test_session: str,
        sample_comment_data: dict,
    ):
        """Test submitting comments for a specific file."""
        # Create comments for different files
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json=sample_comment_data,
        )
        await client.post(
            f"/api/sessions/{test_session}/comments",
            json={**sample_comment_data, "file_path": "other.md"},
        )

        # Submit only comments for specific file
        response = await client.post(
            f"/api/sessions/{test_session}/comments/submit-to-agent",
            json={"file_path": sample_comment_data["file_path"], "prompt_override": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["submitted_count"] == 1

    @pytest.mark.asyncio
    async def test_submit_comments_when_none_pending(
        self,
        client: AsyncClient,
        test_session: str,
    ):
        """Test submitting when there are no pending comments."""
        response = await client.post(
            f"/api/sessions/{test_session}/comments/submit-to-agent",
            json={"file_path": None, "prompt_override": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["submitted_count"] == 0
        assert "No pending comments" in data["message"]
