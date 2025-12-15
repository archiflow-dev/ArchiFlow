"""
GitHub Review Posting tools for submitting code reviews to GitHub PRs.

This module provides tools for posting review comments, inline comments,
and review verdicts to GitHub Pull Requests.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.tools.tool_base import BaseTool, ToolResult


class PostGitHubReviewTool(BaseTool):
    """
    Tool for posting code review results to GitHub Pull Requests.

    Converts review JSON (CodeReviewAgent format) to GitHub review format
    and posts it to the PR.

    Supports:
    - Review comments (overall summary)
    - Inline comments (file-specific, line-specific)
    - Review verdict (APPROVE, REQUEST_CHANGES, COMMENT)

    Usage:
        result = tool.execute(
            pr_url="https://github.com/owner/repo/pull/123",
            review_file=".agent/review/results/latest.json"
        )
    """

    name: str = "post_github_review"
    description: str = "Post a code review to a GitHub Pull Request"

    parameters: Dict[str, Any] = {
            "type": "object",
            "required": ["pr_url", "review_data"],
            "properties": {
                "pr_url": {
                    "type": "string",
                    "description": "GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)",
                },
                "review_data": {
                    "type": ["object", "string"],
                    "description": "Review data as JSON object or path to review JSON file",
                },
                "method": {
                    "type": "string",
                    "enum": ["auto", "gh_cli", "api"],
                    "description": "Method to use: 'auto' (try gh CLI first), 'gh_cli', or 'api'",
                    "default": "auto",
                },
                "commit_id": {
                    "type": "string",
                    "description": "Specific commit SHA to review (optional, uses latest if not provided)",
                },
            },
        }

    def _log_error(self, message: str):
        """Helper to log errors."""
        print(f"ERROR: {message}")

    def _parse_pr_url(self, pr_url: str) -> Optional[Dict[str, str]]:
        """
        Parse GitHub PR URL to extract owner, repo, and PR number.

        Returns:
            Dict with 'owner', 'repo', 'pr_number' or None if invalid
        """
        import re

        pattern = r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.match(pattern, pr_url)
        if match:
            return {
                "owner": match.group(1),
                "repo": match.group(2).replace(".git", ""),
                "pr_number": match.group(3),
            }
        return None

    def _load_review_data(self, review_data: Any) -> Optional[Dict[str, Any]]:
        """
        Load review data from file or object.

        Args:
            review_data: Either a dict (review JSON) or string (path to file)

        Returns:
            Review data dict or None on error
        """
        if isinstance(review_data, dict):
            return review_data

        if isinstance(review_data, str):
            try:
                review_path = Path(review_data)
                if not review_path.exists():
                    self._log_error(f"Review file not found: {review_data}")
                    return None

                with open(review_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                self._log_error(f"Error loading review file: {e}")
                return None

        return None

    def _convert_verdict(self, verdict: str) -> str:
        """
        Convert CodeReviewAgent verdict to GitHub review event.

        CodeReviewAgent verdicts:
        - APPROVE → APPROVE
        - REQUEST_CHANGES → REQUEST_CHANGES
        - COMMENT → COMMENT

        Returns:
            GitHub review event string
        """
        verdict_map = {
            "APPROVE": "APPROVE",
            "REQUEST_CHANGES": "REQUEST_CHANGES",
            "COMMENT": "COMMENT",
        }
        return verdict_map.get(verdict, "COMMENT")

    def _build_review_body(self, review_data: Dict[str, Any]) -> str:
        """
        Build the main review comment body from review data.

        Returns:
            Formatted markdown review body
        """
        body = f"## {review_data.get('summary', 'Code Review')}\n\n"

        # Add strengths section
        strengths = review_data.get("strengths", [])
        if strengths:
            body += "### ✅ Strengths\n\n"
            for strength in strengths:
                body += f"- {strength}\n"
            body += "\n"

        # Add recommendations section
        recommendations = review_data.get("recommendations", [])
        if recommendations:
            body += "### 📋 Recommendations\n\n"

            # Group by priority
            high_priority = [r for r in recommendations if r.get("priority") == "HIGH"]
            medium_priority = [
                r for r in recommendations if r.get("priority") == "MEDIUM"
            ]
            low_priority = [r for r in recommendations if r.get("priority") == "LOW"]

            if high_priority:
                body += "**🔴 High Priority**\n"
                for rec in high_priority:
                    body += f"- {rec.get('item', rec)}\n"
                body += "\n"

            if medium_priority:
                body += "**🟡 Medium Priority**\n"
                for rec in medium_priority:
                    body += f"- {rec.get('item', rec)}\n"
                body += "\n"

            if low_priority:
                body += "**🟢 Low Priority**\n"
                for rec in low_priority:
                    body += f"- {rec.get('item', rec)}\n"
                body += "\n"

        # Add footer
        body += "\n---\n"
        body += "*🤖 This review was generated by CodeReviewAgent*\n"

        return body

    def _build_inline_comments(
        self, review_data: Dict[str, Any], commit_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Build GitHub inline comments from review comments.

        GitHub inline comment format:
        {
            "path": "file.py",
            "line": 42,
            "body": "Comment text",
            "side": "RIGHT"  # RIGHT for new version, LEFT for old
        }

        Returns:
            List of GitHub inline comment objects
        """
        comments = review_data.get("comments", [])
        inline_comments = []

        severity_icons = {
            "CRITICAL": "🔴",
            "MAJOR": "🟠",
            "MINOR": "🟡",
            "NIT": "⚪",
        }

        for comment in comments:
            file_path = comment.get("file", "")
            line = comment.get("line", 1)
            severity = comment.get("severity", "MINOR")
            category = comment.get("category", "code_quality")
            issue = comment.get("issue", "")
            suggestion = comment.get("suggestion", "")
            code_example = comment.get("code_example", "")

            # Build comment body
            icon = severity_icons.get(severity, "💬")
            body = f"{icon} **{severity}** ({category})\n\n"
            body += f"**Issue**: {issue}\n\n"

            if suggestion:
                body += f"**Suggestion**: {suggestion}\n\n"

            if code_example:
                # Try to detect language from file extension
                ext = Path(file_path).suffix.lstrip(".")
                lang = ext if ext in ["py", "js", "ts", "java", "go", "rs"] else ""

                body += "**Example**:\n"
                body += f"```{lang}\n{code_example}\n```\n"

            github_comment = {
                "path": file_path,
                "line": line,
                "body": body,
                "side": "RIGHT",  # Comment on new version of file
            }

            # Add commit_id if provided (required for some API calls)
            if commit_id:
                github_comment["commit_id"] = commit_id

            inline_comments.append(github_comment)

        return inline_comments

    def _check_gh_cli_available(self) -> bool:
        """Check if GitHub CLI (gh) is installed and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _post_via_gh_cli(
        self,
        owner: str,
        repo: str,
        pr_number: str,
        review_body: str,
        inline_comments: List[Dict[str, Any]],
        verdict: str,
    ) -> bool:
        """
        Post review using GitHub CLI.

        Note: gh CLI has limited support for inline comments in reviews.
        This method posts the main review and attempts to add comments.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build gh pr review command
            cmd = [
                "gh",
                "pr",
                "review",
                pr_number,
                "--repo",
                f"{owner}/{repo}",
                "--body",
                review_body,
            ]

            # Add review verdict
            if verdict == "APPROVE":
                cmd.append("--approve")
            elif verdict == "REQUEST_CHANGES":
                cmd.append("--request-changes")
            elif verdict == "COMMENT":
                cmd.append("--comment")

            # Execute review command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                self._log_error(f"gh CLI error: {result.stderr}")
                return False

            # Post inline comments separately (gh CLI limitation)
            # Note: gh CLI doesn't support inline comments in reviews well
            # We'll post them as regular PR comments instead
            for comment in inline_comments:
                comment_cmd = [
                    "gh",
                    "pr",
                    "comment",
                    pr_number,
                    "--repo",
                    f"{owner}/{repo}",
                    "--body",
                    f"**{comment['path']}:{comment['line']}**\n\n{comment['body']}",
                ]

                subprocess.run(
                    comment_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                # Don't fail if comments fail, main review is more important

            return True

        except (subprocess.TimeoutExpired, Exception) as e:
            self._log_error(f"Error posting review via gh CLI: {e}")
            return False

    def _post_via_api(
        self,
        owner: str,
        repo: str,
        pr_number: str,
        review_body: str,
        inline_comments: List[Dict[str, Any]],
        verdict: str,
        commit_id: Optional[str] = None,
    ) -> bool:
        """
        Post review using GitHub REST API.

        Requires GITHUB_TOKEN environment variable.

        Returns:
            True if successful, False otherwise
        """
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            self._log_error("GITHUB_TOKEN not found in environment")
            return False

        try:
            import requests
        except ImportError:
            self._log_error("requests library not installed (pip install requests)")
            return False

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Get latest commit if not provided
        if not commit_id:
            pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            try:
                pr_response = requests.get(pr_url, headers=headers, timeout=30)
                pr_response.raise_for_status()
                pr_data = pr_response.json()
                commit_id = pr_data["head"]["sha"]
            except Exception as e:
                self._log_error(f"Error fetching PR commit: {e}")
                return False

        # Build review request
        review_url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        )

        review_request = {
            "body": review_body,
            "event": verdict,
            "commit_id": commit_id,
        }

        # Add inline comments if any
        if inline_comments:
            # Convert to GitHub API format
            api_comments = []
            for comment in inline_comments:
                api_comments.append(
                    {
                        "path": comment["path"],
                        "line": comment["line"],
                        "body": comment["body"],
                        "side": comment.get("side", "RIGHT"),
                    }
                )
            review_request["comments"] = api_comments

        try:
            response = requests.post(
                review_url,
                headers=headers,
                json=review_request,
                timeout=30,
            )
            response.raise_for_status()
            return True

        except Exception as e:
            self._log_error(f"Error posting review via API: {e}")
            return False

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the GitHub review posting tool.

        Args:
            pr_url: GitHub PR URL
            review_data: Review data (dict or file path)
            method: Posting method - 'auto', 'gh_cli', or 'api' (optional)
            commit_id: Specific commit SHA to review (optional)

        Returns:
            ToolResult with success/error
        """
        pr_url = kwargs.get("pr_url")
        if not pr_url:
            return ToolResult(success=False, error="pr_url parameter is required")

        # Parse PR URL
        pr_info = self._parse_pr_url(pr_url)
        if not pr_info:
            return ToolResult(
                success=False,
                error=f"Invalid GitHub PR URL: {pr_url}",
            )

        # Load review data
        review_data_input = kwargs.get("review_data")
        review_data = self._load_review_data(review_data_input)
        if not review_data:
            return ToolResult(
                success=False,
                error="Failed to load review data",
            )

        # Validate review data has required fields
        if "verdict" not in review_data:
            return ToolResult(
                success=False,
                error="Review data missing 'verdict' field",
            )

        # Convert review data to GitHub format
        verdict = self._convert_verdict(review_data.get("verdict", "COMMENT"))
        review_body = self._build_review_body(review_data)
        inline_comments = self._build_inline_comments(
            review_data, kwargs.get("commit_id")
        )

        # Determine posting method
        method = kwargs.get("method", "auto")
        success = False
        method_used = None

        if method in ("auto", "gh_cli"):
            if self._check_gh_cli_available():
                success = self._post_via_gh_cli(
                    pr_info["owner"],
                    pr_info["repo"],
                    pr_info["pr_number"],
                    review_body,
                    inline_comments,
                    verdict,
                )
                if success:
                    method_used = "gh_cli"

        if not success and method in ("auto", "api"):
            success = self._post_via_api(
                pr_info["owner"],
                pr_info["repo"],
                pr_info["pr_number"],
                review_body,
                inline_comments,
                verdict,
                kwargs.get("commit_id"),
            )
            if success:
                method_used = "api"

        if not success:
            error_msg = "Failed to post review to GitHub. "
            if method == "gh_cli":
                error_msg += "GitHub CLI failed."
            elif method == "api":
                error_msg += "GitHub API failed."
            else:
                error_msg += "Both gh CLI and API methods failed."

            return ToolResult(success=False, error=error_msg)

        # Build success message
        result_msg = f"Successfully posted review to PR #{pr_info['pr_number']}\n\n"
        result_msg += f"Method: {method_used}\n"
        result_msg += f"Verdict: {verdict}\n"
        result_msg += f"Inline comments: {len(inline_comments)}\n"
        result_msg += f"PR URL: {pr_url}\n"

        return ToolResult(
            success=True,
            output=result_msg,
            data={
                "pr_info": pr_info,
                "verdict": verdict,
                "comment_count": len(inline_comments),
                "method_used": method_used,
            },
        )
