"""
GitHub PR tools for fetching PR data and diffs.

This module provides tools for interacting with GitHub Pull Requests,
including fetching PR metadata, diffs, and comments.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from agent_framework.tools.tool_base import BaseTool, ToolResult


class FetchGitHubPRTool(BaseTool):
    """
    Tool for fetching GitHub PR data including diff and metadata.

    Supports two methods:
    1. GitHub CLI (`gh`) - Primary method, faster and easier
    2. GitHub API - Fallback method using REST API

    Usage:
        result = tool.execute(pr_url="https://github.com/owner/repo/pull/123")
    """

    name: str = "fetch_github_pr"
    description: str = "Fetch GitHub Pull Request data including diff, title, description, and metadata"

    parameters: Dict[str, Any] = {
        "type": "object",
        "required": ["pr_url"],
        "properties": {
            "pr_url": {
                "type": "string",
                "description": "GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)",
            },
            "save_to": {
                "type": "string",
                "description": "Directory to save PR data (defaults to .agent/review/)",
            },
            "method": {
                "type": "string",
                "enum": ["auto", "gh_cli", "api"],
                "description": "Method to use: 'auto' (try gh CLI first), 'gh_cli', or 'api'",
                "default": "auto",
            },
        },
    }

    def _parse_pr_url(self, pr_url: str) -> Optional[Dict[str, str]]:
        """
        Parse GitHub PR URL to extract owner, repo, and PR number.

        Supports formats:
        - https://github.com/owner/repo/pull/123
        - github.com/owner/repo/pull/123
        - owner/repo#123

        Returns:
            Dict with 'owner', 'repo', 'pr_number' or None if invalid
        """
        # Pattern 1: Full URL
        pattern1 = r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.match(pattern1, pr_url)
        if match:
            return {
                "owner": match.group(1),
                "repo": match.group(2).replace(".git", ""),
                "pr_number": match.group(3),
            }

        # Pattern 2: Short format (owner/repo#123)
        pattern2 = r"([^/]+)/([^#]+)#(\d+)"
        match = re.match(pattern2, pr_url)
        if match:
            return {
                "owner": match.group(1),
                "repo": match.group(2),
                "pr_number": match.group(3),
            }

        return None

    def _check_gh_cli_available(self) -> bool:
        """Check if GitHub CLI (gh) is installed and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False

            # Check if authenticated
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _fetch_via_gh_cli(
        self, owner: str, repo: str, pr_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch PR data using GitHub CLI.

        Returns:
            Dict with 'metadata', 'diff', and 'comments' or None on error
        """
        try:
            # Fetch PR metadata (JSON)
            metadata_cmd = [
                "gh",
                "pr",
                "view",
                pr_number,
                "--repo",
                f"{owner}/{repo}",
                "--json",
                "title,body,author,state,createdAt,updatedAt,baseRefName,headRefName,additions,deletions,changedFiles,commits",
            ]

            metadata_result = subprocess.run(
                metadata_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if metadata_result.returncode != 0:
                return None

            metadata = json.loads(metadata_result.stdout)

            # Fetch PR diff
            diff_cmd = [
                "gh",
                "pr",
                "diff",
                pr_number,
                "--repo",
                f"{owner}/{repo}",
            ]

            diff_result = subprocess.run(
                diff_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if diff_result.returncode != 0:
                return None

            diff = diff_result.stdout

            # Fetch PR comments (optional)
            comments_cmd = [
                "gh",
                "pr",
                "view",
                pr_number,
                "--repo",
                f"{owner}/{repo}",
                "--json",
                "comments",
            ]

            comments_result = subprocess.run(
                comments_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            comments = []
            if comments_result.returncode == 0:
                comments_data = json.loads(comments_result.stdout)
                comments = comments_data.get("comments", [])

            return {
                "metadata": metadata,
                "diff": diff,
                "comments": comments,
            }

        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            self._log_error(f"Error fetching PR via gh CLI: {e}")
            return None

    def _fetch_via_api(
        self, owner: str, repo: str, pr_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch PR data using GitHub REST API.

        Requires GITHUB_TOKEN environment variable.

        Returns:
            Dict with 'metadata', 'diff', and 'comments' or None on error
        """
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            self._log_error("GITHUB_TOKEN not found in environment")
            return None

        try:
            import requests
        except ImportError:
            self._log_error("requests library not installed (pip install requests)")
            return None

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        base_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

        try:
            # Fetch PR metadata
            response = requests.get(base_url, headers=headers, timeout=30)
            response.raise_for_status()
            metadata = response.json()

            # Fetch PR diff
            diff_headers = headers.copy()
            diff_headers["Accept"] = "application/vnd.github.v3.diff"
            diff_response = requests.get(base_url, headers=diff_headers, timeout=30)
            diff_response.raise_for_status()
            diff = diff_response.text

            # Fetch PR comments
            comments_url = f"{base_url}/comments"
            comments_response = requests.get(comments_url, headers=headers, timeout=30)
            comments_response.raise_for_status()
            comments = comments_response.json()

            return {
                "metadata": metadata,
                "diff": diff,
                "comments": comments,
            }

        except Exception as e:
            self._log_error(f"Error fetching PR via API: {e}")
            return None

    def _save_pr_data(
        self, pr_data: Dict[str, Any], save_dir: Path, pr_info: Dict[str, str]
    ) -> Dict[str, Path]:
        """
        Save PR data to files.

        Returns:
            Dict with paths to saved files
        """
        save_dir.mkdir(parents=True, exist_ok=True)

        saved_files = {}

        # Save diff
        diff_path = save_dir / "github_pr.diff"
        diff_path.write_text(pr_data["diff"], encoding="utf-8")
        saved_files["diff"] = diff_path

        # Save metadata as JSON
        metadata = pr_data["metadata"]
        metadata_path = save_dir / "github_pr_metadata.json"

        # Add PR info to metadata
        enhanced_metadata = {
            "pr_url": f"https://github.com/{pr_info['owner']}/{pr_info['repo']}/pull/{pr_info['pr_number']}",
            "owner": pr_info["owner"],
            "repo": pr_info["repo"],
            "pr_number": pr_info["pr_number"],
            **metadata,
        }

        metadata_path.write_text(
            json.dumps(enhanced_metadata, indent=2), encoding="utf-8"
        )
        saved_files["metadata"] = metadata_path

        # Save PR description (body) as markdown
        pr_body = metadata.get("body", "") or metadata.get("description", "")
        if pr_body:
            pr_desc_path = save_dir / "github_pr_description.md"

            # Create formatted PR description
            pr_title = metadata.get("title", "")
            pr_author = metadata.get("author", {})
            author_login = pr_author.get("login", "") if isinstance(pr_author, dict) else pr_author

            formatted_desc = f"# {pr_title}\n\n"
            if author_login:
                formatted_desc += f"**Author**: @{author_login}\n\n"
            formatted_desc += f"{pr_body}\n"

            pr_desc_path.write_text(formatted_desc, encoding="utf-8")
            saved_files["description"] = pr_desc_path

        # Save comments if any
        if pr_data.get("comments"):
            comments_path = save_dir / "github_pr_comments.json"
            comments_path.write_text(
                json.dumps(pr_data["comments"], indent=2), encoding="utf-8"
            )
            saved_files["comments"] = comments_path

        return saved_files

    def _log_error(self, message: str):
        """Helper to log errors."""
        # Simple error logging - can be enhanced with proper logger
        print(f"ERROR: {message}")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the GitHub PR fetch tool.

        Args:
            pr_url: GitHub PR URL
            save_to: Directory to save PR data (optional)
            method: Fetch method - 'auto', 'gh_cli', or 'api' (optional)

        Returns:
            ToolResult with success/error and saved file paths
        """
        pr_url = kwargs.get("pr_url")
        if not pr_url:
            return ToolResult(
                success=False,
                error="pr_url parameter is required",
            )

        # Parse PR URL
        pr_info = self._parse_pr_url(pr_url)
        if not pr_info:
            return ToolResult(
                success=False,
                error=f"Invalid GitHub PR URL: {pr_url}. "
                "Expected format: https://github.com/owner/repo/pull/123",
            )

        # Determine save directory
        save_to = kwargs.get("save_to")
        if save_to:
            save_dir = Path(save_to)
        else:
            # Default to .agent/review/ in current execution context
            if self.execution_context and self.execution_context.project_directory:
                save_dir = (
                    Path(self.execution_context.project_directory)
                    / ".agent"
                    / "review"
                )
            else:
                save_dir = Path.cwd() / ".agent" / "review"

        # Determine fetch method
        method = kwargs.get("method", "auto")

        pr_data = None

        if method in ("auto", "gh_cli"):
            # Try GitHub CLI first
            if self._check_gh_cli_available():
                pr_data = self._fetch_via_gh_cli(
                    pr_info["owner"], pr_info["repo"], pr_info["pr_number"]
                )
                if pr_data:
                    method_used = "gh_cli"

        if pr_data is None and method in ("auto", "api"):
            # Fallback to API
            pr_data = self._fetch_via_api(
                pr_info["owner"], pr_info["repo"], pr_info["pr_number"]
            )
            if pr_data:
                method_used = "api"

        if pr_data is None:
            error_msg = "Failed to fetch PR data. "
            if method == "gh_cli":
                error_msg += "GitHub CLI failed. Install/authenticate with 'gh auth login'."
            elif method == "api":
                error_msg += "GitHub API failed. Set GITHUB_TOKEN environment variable."
            else:
                error_msg += "Both gh CLI and API methods failed."

            return ToolResult(success=False, error=error_msg)

        # Save PR data to files
        saved_files = self._save_pr_data(pr_data, save_dir, pr_info)

        # Build result message
        result_msg = f"Successfully fetched PR #{pr_info['pr_number']} from {pr_info['owner']}/{pr_info['repo']}\n\n"
        result_msg += f"Method: {method_used}\n"
        result_msg += f"PR Title: {pr_data['metadata'].get('title', 'N/A')}\n\n"
        result_msg += "Saved files:\n"
        for file_type, path in saved_files.items():
            result_msg += f"  - {file_type}: {path}\n"

        return ToolResult(
            success=True,
            output=result_msg,
            data={
                "pr_info": pr_info,
                "saved_files": {k: str(v) for k, v in saved_files.items()},
                "method_used": method_used,
                "metadata": pr_data["metadata"],
            },
        )
