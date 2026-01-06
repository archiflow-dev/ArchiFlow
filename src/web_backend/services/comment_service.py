"""
Comment Service for ArchiFlow Web Backend.

Manages document comments with file-based storage in session workspaces.
Comments are stored in .comments.json files within each session's workspace.
"""

import logging
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from ..models.comment import (
    Comment,
    CommentCreate,
    CommentUpdate,
    CommentStatus,
)
from ..services.workspace_manager import WorkspaceManager, get_workspace_manager
from ..services.session_store import get_session_store

logger = logging.getLogger(__name__)


COMMENTS_FILE = ".comments.json"


class CommentNotFoundError(Exception):
    """Raised when a comment is not found."""
    pass


class CommentServiceError(Exception):
    """Raised when a comment service operation fails."""
    pass


class CommentService:
    """
    Service for managing document comments.

    Comments are stored per-session in .comments.json files in the workspace.
    This design aligns with the file-based workspace architecture.
    """

    def __init__(
        self,
        workspace_manager: Optional[WorkspaceManager] = None,
    ):
        """
        Initialize CommentService.

        Args:
            workspace_manager: Workspace manager instance. If None, uses default.
        """
        self.workspace_manager = workspace_manager or get_workspace_manager()

    def _get_comments_file_path(self, session_id: str, user_id: str = "default_user") -> Path:
        """
        Get the path to the comments file for a session.

        Args:
            session_id: Session ID
            user_id: User ID (default: default_user)

        Returns:
            Path to the .comments.json file
        """
        workspace_path = self.workspace_manager.get_workspace_path(user_id, session_id)
        return workspace_path / COMMENTS_FILE

    def _load_comments(self, session_id: str, user_id: str = "default_user") -> List[Dict]:
        """
        Load comments from the comments file.

        Args:
            session_id: Session ID
            user_id: User ID (default: default_user)

        Returns:
            List of comment dictionaries

        Raises:
            CommentServiceError: If loading fails
        """
        comments_path = self._get_comments_file_path(session_id, user_id)

        if not comments_path.exists():
            return []

        try:
            with open(comments_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('comments', [])
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in comments file {comments_path}: {e}")
            raise CommentServiceError(f"Invalid comments file format: {e}")
        except Exception as e:
            logger.error(f"Error loading comments from {comments_path}: {e}")
            raise CommentServiceError(f"Failed to load comments: {e}")

    def _save_comments(
        self,
        session_id: str,
        comments: List[Dict],
        user_id: str = "default_user"
    ) -> None:
        """
        Save comments to the comments file.

        Args:
            session_id: Session ID
            comments: List of comment dictionaries
            user_id: User ID (default: default_user)

        Raises:
            CommentServiceError: If saving fails
        """
        comments_path = self._get_comments_file_path(session_id, user_id)

        # Ensure directory exists
        comments_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(comments_path, 'w', encoding='utf-8') as f:
                json.dump({'comments': comments}, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved {len(comments)} comments to {comments_path}")
        except Exception as e:
            logger.error(f"Error saving comments to {comments_path}: {e}")
            raise CommentServiceError(f"Failed to save comments: {e}")

    def list_comments(
        self,
        session_id: str,
        file_path: Optional[str] = None,
        status: Optional[CommentStatus] = None,
        user_id: str = "default_user"
    ) -> List[Comment]:
        """
        List all comments for a session.

        Args:
            session_id: Session ID
            file_path: Optional filter by file path
            status: Optional filter by status
            user_id: User ID (default: default_user)

        Returns:
            List of comments

        Raises:
            CommentServiceError: If loading fails
        """
        comments_data = self._load_comments(session_id, user_id)

        # Filter by file path if specified
        if file_path is not None:
            comments_data = [c for c in comments_data if c.get('file_path') == file_path]

        # Filter by status if specified
        if status is not None:
            comments_data = [c for c in comments_data if c.get('status') == status.value]

        return [Comment(**c) for c in comments_data]

    def get_comment(
        self,
        comment_id: str,
        session_id: str,
        user_id: str = "default_user"
    ) -> Comment:
        """
        Get a specific comment by ID.

        Args:
            comment_id: Comment ID
            session_id: Session ID
            user_id: User ID (default: default_user)

        Returns:
            The comment

        Raises:
            CommentNotFoundError: If comment not found
            CommentServiceError: If loading fails
        """
        comments_data = self._load_comments(session_id, user_id)

        for comment_data in comments_data:
            if comment_data.get('id') == comment_id:
                return Comment(**comment_data)

        raise CommentNotFoundError(f"Comment {comment_id} not found in session {session_id}")

    def create_comment(
        self,
        comment_create: CommentCreate,
        session_id: str,
        user_id: str = "default_user"
    ) -> Comment:
        """
        Create a new comment.

        Args:
            comment_create: Comment creation data
            session_id: Session ID
            user_id: User ID (default: default_user)

        Returns:
            The created comment

        Raises:
            CommentServiceError: If creation fails
        """
        # Validate session exists
        try:
            session_store = get_session_store()
            session_info = session_store.get_session(session_id)
            if not session_info:
                raise CommentServiceError(f"Session {session_id} not found")
        except Exception as e:
            logger.warning(f"Failed to validate session {session_id}: {e}")
            # Continue anyway - comments might be created for completed sessions

        # Create the comment
        comment = Comment(
            session_id=session_id,
            file_path=comment_create.file_path,
            line_number=comment_create.line_number,
            selected_text=comment_create.selected_text,
            comment_text=comment_create.comment_text,
            author=comment_create.author,
        )

        # Load existing comments and add new one
        comments_data = self._load_comments(session_id, user_id)
        comments_data.append(comment.model_dump())

        # Save
        self._save_comments(session_id, comments_data, user_id)

        logger.info(
            f"Created comment {comment.id} on {comment.file_path}:{comment.line_number} "
            f"in session {session_id}"
        )

        return comment

    def update_comment(
        self,
        comment_id: str,
        comment_update: CommentUpdate,
        session_id: str,
        user_id: str = "default_user"
    ) -> Comment:
        """
        Update an existing comment.

        Args:
            comment_id: Comment ID
            comment_update: Update data
            session_id: Session ID
            user_id: User ID (default: default_user)

        Returns:
            The updated comment

        Raises:
            CommentNotFoundError: If comment not found
            CommentServiceError: If update fails
        """
        comments_data = self._load_comments(session_id, user_id)

        # Find and update the comment
        updated = False
        for comment_data in comments_data:
            if comment_data.get('id') == comment_id:
                if comment_update.comment_text is not None:
                    comment_data['comment_text'] = comment_update.comment_text
                if comment_update.status is not None:
                    comment_data['status'] = comment_update.status.value
                comment_data['updated_at'] = datetime.utcnow().isoformat()
                updated = True
                break

        if not updated:
            raise CommentNotFoundError(f"Comment {comment_id} not found in session {session_id}")

        # Save
        self._save_comments(session_id, comments_data, user_id)

        logger.info(f"Updated comment {comment_id} in session {session_id}")

        # Return updated comment
        return self.get_comment(comment_id, session_id, user_id)

    def delete_comment(
        self,
        comment_id: str,
        session_id: str,
        user_id: str = "default_user"
    ) -> None:
        """
        Delete a comment.

        Args:
            comment_id: Comment ID
            session_id: Session ID
            user_id: User ID (default: default_user)

        Raises:
            CommentNotFoundError: If comment not found
            CommentServiceError: If deletion fails
        """
        comments_data = self._load_comments(session_id, user_id)

        # Find and remove the comment
        original_count = len(comments_data)
        comments_data = [c for c in comments_data if c.get('id') != comment_id]

        if len(comments_data) == original_count:
            raise CommentNotFoundError(f"Comment {comment_id} not found in session {session_id}")

        # Save
        self._save_comments(session_id, comments_data, user_id)

        logger.info(f"Deleted comment {comment_id} from session {session_id}")

    def get_pending_comments(
        self,
        session_id: str,
        file_path: Optional[str] = None,
        user_id: str = "default_user"
    ) -> List[Comment]:
        """
        Get all pending comments for submission to agent.

        Args:
            session_id: Session ID
            file_path: Optional filter by file path
            user_id: User ID (default: default_user)

        Returns:
            List of pending comments

        Raises:
            CommentServiceError: If loading fails
        """
        return self.list_comments(
            session_id=session_id,
            file_path=file_path,
            status=CommentStatus.PENDING,
            user_id=user_id
        )

    def mark_comments_submitted(
        self,
        comment_ids: List[str],
        session_id: str,
        user_id: str = "default_user"
    ) -> int:
        """
        Mark comments as submitted to agent.

        Args:
            comment_ids: List of comment IDs to mark
            session_id: Session ID
            user_id: User ID (default: default_user)

        Returns:
            Number of comments marked

        Raises:
            CommentServiceError: If update fails
        """
        comments_data = self._load_comments(session_id, user_id)

        marked_count = 0
        for comment_data in comments_data:
            if comment_data.get('id') in comment_ids:
                comment_data['status'] = CommentStatus.SUBMITTED.value
                comment_data['updated_at'] = datetime.utcnow().isoformat()
                marked_count += 1

        # Save
        self._save_comments(session_id, comments_data, user_id)

        logger.info(f"Marked {marked_count} comments as submitted in session {session_id}")

        return marked_count

    def format_comments_for_agent(
        self,
        comments: List[Comment],
        file_path: Optional[str] = None
    ) -> str:
        """
        Format comments for submission to an agent.

        Args:
            comments: List of comments to format
            file_path: Optional specific file path

        Returns:
            Formatted string for agent prompt
        """
        if not comments:
            return "No comments to process."

        # Group by file
        comments_by_file: Dict[str, List[Comment]] = {}
        for comment in comments:
            if comment.file_path not in comments_by_file:
                comments_by_file[comment.file_path] = []
            comments_by_file[comment.file_path].append(comment)

        # Format output
        lines = []
        lines.append("Please update the document(s) based on the following comments:\n")

        for file, file_comments in sorted(comments_by_file.items()):
            lines.append(f"## File: {file}")
            lines.append("")

            # Sort by line number
            for comment in sorted(file_comments, key=lambda c: c.line_number):
                selected = comment.selected_text or "(no text selected)"
                lines.append(f"- Line {comment.line_number}: '{selected}'")
                lines.append(f"  → {comment.comment_text}")
                lines.append("")

        return "\n".join(lines)


# Singleton instance
_comment_service: Optional[CommentService] = None


def get_comment_service() -> CommentService:
    """Get the singleton comment service instance."""
    global _comment_service
    if _comment_service is None:
        _comment_service = CommentService()
    return _comment_service
