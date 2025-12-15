"""
Tests for CodeReviewAgent Phase 3: External Integrations

Tests cover:
- Phase 3.1: GitHub PR Fetching
- Phase 3.2: GitHub Review Posting
- Phase 3.3: User-Provided Files Support
- Phase 3.4: Export Formats (Reviewdog, SARIF)
"""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

from agent_framework.agents.code_review_agent import CodeReviewAgent
from agent_framework.llm.mock import MockLLMProvider
try:
    from agent_framework.tools.github_pr import FetchGitHubPRTool
    from agent_framework.tools.github_review import PostGitHubReviewTool
except ImportError:
    # If tools aren't registered yet, we can skip those specific tests
    FetchGitHubPRTool = None
    PostGitHubReviewTool = None


class TestPhase31GitHubPRFetching(unittest.TestCase):
    """Test Phase 3.1: GitHub PR Fetching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.tool = FetchGitHubPRTool()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_pr_url_full_url(self):
        """Test parsing full GitHub PR URL."""
        url = "https://github.com/owner/repo/pull/123"
        result = self.tool._parse_pr_url(url)

        self.assertIsNotNone(result)
        self.assertEqual(result["owner"], "owner")
        self.assertEqual(result["repo"], "repo")
        self.assertEqual(result["pr_number"], "123")

    def test_parse_pr_url_short_format(self):
        """Test parsing short GitHub PR format."""
        url = "owner/repo#123"
        result = self.tool._parse_pr_url(url)

        self.assertIsNotNone(result)
        self.assertEqual(result["owner"], "owner")
        self.assertEqual(result["repo"], "repo")
        self.assertEqual(result["pr_number"], "123")

    def test_parse_pr_url_invalid(self):
        """Test parsing invalid PR URL."""
        url = "not-a-valid-url"
        result = self.tool._parse_pr_url(url)

        self.assertIsNone(result)

    def test_parse_pr_url_without_protocol(self):
        """Test parsing PR URL without https protocol."""
        url = "github.com/owner/repo/pull/456"
        result = self.tool._parse_pr_url(url)

        self.assertIsNotNone(result)
        self.assertEqual(result["pr_number"], "456")

    @patch('subprocess.run')
    def test_check_gh_cli_available_success(self, mock_run):
        """Test checking for GitHub CLI when available."""
        # Mock successful gh version check
        mock_run.return_value = MagicMock(returncode=0, stdout="gh version 2.0.0")

        result = self.tool._check_gh_cli_available()
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_check_gh_cli_available_not_installed(self, mock_run):
        """Test checking for GitHub CLI when not installed."""
        mock_run.side_effect = FileNotFoundError()

        result = self.tool._check_gh_cli_available()
        self.assertFalse(result)

    @patch('subprocess.run')
    def test_fetch_via_gh_cli_success(self, mock_run):
        """Test fetching PR via GitHub CLI."""
        # Mock gh pr view for metadata
        metadata_response = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "title": "Test PR",
                "body": "Description",
                "author": {"login": "testuser"},
                "state": "OPEN"
            })
        )

        # Mock gh pr diff
        diff_response = MagicMock(
            returncode=0,
            stdout="diff --git a/file.py b/file.py\n+new line"
        )

        # Mock gh pr view for comments
        comments_response = MagicMock(
            returncode=0,
            stdout=json.dumps({"comments": []})
        )

        mock_run.side_effect = [metadata_response, diff_response, comments_response]

        result = self.tool._fetch_via_gh_cli("owner", "repo", "123")

        self.assertIsNotNone(result)
        self.assertIn("metadata", result)
        self.assertIn("diff", result)
        self.assertEqual(result["metadata"]["title"], "Test PR")

    @patch('subprocess.run')
    def test_fetch_via_gh_cli_failure(self, mock_run):
        """Test fetching PR via GitHub CLI when it fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        result = self.tool._fetch_via_gh_cli("owner", "repo", "123")

        self.assertIsNone(result)

    def test_save_pr_data(self):
        """Test saving PR data to files."""
        save_dir = Path(self.temp_dir) / "review"
        pr_data = {
            "metadata": {
                "title": "Test PR",
                "body": "Test description",
                "author": {"login": "testuser"}
            },
            "diff": "diff --git a/file.py b/file.py\n+new line",
            "comments": [{"body": "Test comment"}]
        }
        pr_info = {
            "owner": "owner",
            "repo": "repo",
            "pr_number": "123"
        }

        saved_files = self.tool._save_pr_data(pr_data, save_dir, pr_info)

        self.assertIn("diff", saved_files)
        self.assertIn("metadata", saved_files)
        self.assertIn("description", saved_files)
        self.assertIn("comments", saved_files)

        # Verify files exist
        self.assertTrue(Path(saved_files["diff"]).exists())
        self.assertTrue(Path(saved_files["metadata"]).exists())


class TestPhase32GitHubReviewPosting(unittest.TestCase):
    """Test Phase 3.2: GitHub Review Posting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool = PostGitHubReviewTool()
        self.review_data = {
            "verdict": "REQUEST_CHANGES",
            "summary": "Found several issues",
            "comments": [
                {
                    "file": "api/auth.py",
                    "line": 45,
                    "severity": "CRITICAL",
                    "category": "security",
                    "issue": "SQL injection vulnerability",
                    "suggestion": "Use parameterized queries",
                    "code_example": "cursor.execute('SELECT * FROM users WHERE id = ?', (id,))"
                }
            ],
            "strengths": ["Good test coverage"],
            "recommendations": [
                {"priority": "HIGH", "item": "Fix SQL injection"}
            ]
        }

    def test_parse_pr_url(self):
        """Test parsing PR URL."""
        url = "https://github.com/owner/repo/pull/123"
        result = self.tool._parse_pr_url(url)

        self.assertIsNotNone(result)
        self.assertEqual(result["owner"], "owner")

    def test_load_review_data_from_dict(self):
        """Test loading review data from dictionary."""
        result = self.tool._load_review_data(self.review_data)

        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "REQUEST_CHANGES")

    def test_convert_verdict(self):
        """Test converting verdict to GitHub format."""
        self.assertEqual(self.tool._convert_verdict("APPROVE"), "APPROVE")
        self.assertEqual(self.tool._convert_verdict("REQUEST_CHANGES"), "REQUEST_CHANGES")
        self.assertEqual(self.tool._convert_verdict("COMMENT"), "COMMENT")
        self.assertEqual(self.tool._convert_verdict("INVALID"), "COMMENT")

    def test_build_review_body(self):
        """Test building review body markdown."""
        body = self.tool._build_review_body(self.review_data)

        self.assertIn("Found several issues", body)
        self.assertIn("Strengths", body)
        self.assertIn("Good test coverage", body)
        self.assertIn("Recommendations", body)
        self.assertIn("High Priority", body)
        self.assertIn("CodeReviewAgent", body)

    def test_build_inline_comments(self):
        """Test building inline comments."""
        comments = self.tool._build_inline_comments(self.review_data)

        self.assertEqual(len(comments), 1)
        comment = comments[0]

        self.assertEqual(comment["path"], "api/auth.py")
        self.assertEqual(comment["line"], 45)
        self.assertIn("CRITICAL", comment["body"])
        self.assertIn("security", comment["body"])
        self.assertIn("SQL injection vulnerability", comment["body"])
        self.assertIn("Use parameterized queries", comment["body"])

    def test_build_inline_comments_with_code_example(self):
        """Test inline comments include code examples."""
        comments = self.tool._build_inline_comments(self.review_data)

        self.assertIn("```", comments[0]["body"])
        self.assertIn("cursor.execute", comments[0]["body"])

    @patch('subprocess.run')
    def test_check_gh_cli_available(self, mock_run):
        """Test checking for GitHub CLI."""
        mock_run.return_value = MagicMock(returncode=0)

        result = self.tool._check_gh_cli_available()
        self.assertTrue(result)


class TestPhase33UserProvidedFiles(unittest.TestCase):
    """Test Phase 3.3: User-Provided Files Support."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "project"
        self.project_dir.mkdir()

        # Create mock LLM provider
        self.mock_llm = MockLLMProvider()

        # Create agent
        self.agent = CodeReviewAgent(
            session_id="test_session",
            llm=self.mock_llm,
            project_directory=str(self.project_dir)
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_handle_user_provided_diff_file(self):
        """Test handling user-provided diff file."""
        # Create a test diff file
        diff_file = self.project_dir / "test.diff"
        diff_content = "diff --git a/file.py b/file.py\n+new line\n-old line"
        diff_file.write_text(diff_content)

        # Handle the file
        result = self.agent.handle_user_provided_files(diff_file=str(diff_file))

        self.assertIsNotNone(result["diff_file"])
        self.assertIn("user_provided.diff", result["diff_file"])
        self.assertEqual(len(result["copied_files"]), 1)
        self.assertEqual(len(result["errors"]), 0)

        # Verify file was copied
        copied_file = Path(result["diff_file"])
        self.assertTrue(copied_file.exists())
        self.assertEqual(copied_file.read_text(), diff_content)

        # Verify metadata was updated
        metadata = self.agent._load_metadata()
        self.assertIn("diff", metadata)
        self.assertEqual(metadata["diff"]["source"], "user_provided")

    def test_handle_user_provided_pr_description(self):
        """Test handling user-provided PR description file."""
        # Create a test PR description file
        pr_desc_file = self.project_dir / "pr_desc.md"
        pr_content = "# Test PR\n\nThis is a test PR description."
        pr_desc_file.write_text(pr_content)

        # Handle the file
        result = self.agent.handle_user_provided_files(pr_description_file=str(pr_desc_file))

        self.assertIsNotNone(result["pr_description_file"])
        self.assertIn("user_provided_pr_description.md", result["pr_description_file"])
        self.assertEqual(len(result["copied_files"]), 1)
        self.assertEqual(len(result["errors"]), 0)

        # Verify file was copied
        copied_file = Path(result["pr_description_file"])
        self.assertTrue(copied_file.exists())
        self.assertEqual(copied_file.read_text(), pr_content)

        # Verify metadata was updated
        metadata = self.agent._load_metadata()
        self.assertIn("pr_description", metadata)
        self.assertEqual(metadata["pr_description"]["source"], "user_provided")

    def test_handle_user_provided_both_files(self):
        """Test handling both diff and PR description files."""
        # Create test files
        diff_file = self.project_dir / "test.diff"
        diff_file.write_text("diff --git a/file.py b/file.py\n+new line")

        pr_desc_file = self.project_dir / "pr_desc.md"
        pr_desc_file.write_text("# Test PR")

        # Handle both files
        result = self.agent.handle_user_provided_files(
            diff_file=str(diff_file),
            pr_description_file=str(pr_desc_file)
        )

        self.assertIsNotNone(result["diff_file"])
        self.assertIsNotNone(result["pr_description_file"])
        self.assertEqual(len(result["copied_files"]), 2)
        self.assertEqual(len(result["errors"]), 0)

    def test_handle_user_provided_nonexistent_file(self):
        """Test handling nonexistent file raises error."""
        with self.assertRaises(FileNotFoundError):
            self.agent.handle_user_provided_files(diff_file="nonexistent.diff")

    def test_handle_user_provided_directory_not_file(self):
        """Test handling directory instead of file raises error."""
        # Create a directory
        test_dir = self.project_dir / "testdir"
        test_dir.mkdir()

        with self.assertRaises(ValueError):
            self.agent.handle_user_provided_files(diff_file=str(test_dir))

    def test_handle_user_provided_empty_file(self):
        """Test handling empty file logs warning but doesn't fail."""
        # Create empty file
        empty_file = self.project_dir / "empty.diff"
        empty_file.write_text("")

        # Should not raise, but should log warning
        result = self.agent.handle_user_provided_files(diff_file=str(empty_file))

        # File still gets copied despite being empty
        self.assertIsNotNone(result["diff_file"])


class TestPhase34ExportFormats(unittest.TestCase):
    """Test Phase 3.4: Export Formats (Reviewdog, SARIF)."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "project"
        self.project_dir.mkdir()

        # Create mock LLM provider
        self.mock_llm = MockLLMProvider()

        # Create agent
        self.agent = CodeReviewAgent(
            session_id="test_session",
            llm=self.mock_llm,
            project_directory=str(self.project_dir)
        )

        # Sample review data
        self.review_data = {
            "verdict": "REQUEST_CHANGES",
            "summary": "Found issues",
            "comments": [
                {
                    "file": "api/auth.py",
                    "line": 45,
                    "severity": "CRITICAL",
                    "category": "security",
                    "issue": "SQL injection vulnerability",
                    "suggestion": "Use parameterized queries",
                    "code_example": "cursor.execute('SELECT * FROM users WHERE id = ?', (id,))"
                },
                {
                    "file": "api/users.py",
                    "line": 23,
                    "severity": "MINOR",
                    "category": "code_quality",
                    "issue": "Missing type hints",
                    "suggestion": "Add type annotations"
                }
            ],
            "strengths": ["Good test coverage"],
            "recommendations": []
        }

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_reviewdog_format(self):
        """Test exporting review to Reviewdog format."""
        exports_dir = self.agent.review_dir / "exports"
        export_file = self.agent._export_reviewdog(self.review_data, exports_dir)

        self.assertIsNotNone(export_file)
        self.assertTrue(export_file.exists())

        # Load and validate Reviewdog JSON
        with open(export_file, 'r') as f:
            reviewdog_data = json.load(f)

        self.assertIn("source", reviewdog_data)
        self.assertIn("diagnostics", reviewdog_data)
        self.assertEqual(reviewdog_data["source"]["name"], "CodeReviewAgent")

        # Check diagnostics
        diagnostics = reviewdog_data["diagnostics"]
        self.assertEqual(len(diagnostics), 2)

        # Check first diagnostic (CRITICAL)
        critical_diag = diagnostics[0]
        self.assertEqual(critical_diag["severity"], "ERROR")
        self.assertEqual(critical_diag["location"]["path"], "api/auth.py")
        self.assertEqual(critical_diag["location"]["range"]["start"]["line"], 45)
        self.assertIn("SQL injection", critical_diag["message"])

        # Check second diagnostic (MINOR)
        minor_diag = diagnostics[1]
        self.assertEqual(minor_diag["severity"], "WARNING")

    def test_export_sarif_format(self):
        """Test exporting review to SARIF format."""
        exports_dir = self.agent.review_dir / "exports"
        export_file = self.agent._export_sarif(self.review_data, exports_dir)

        self.assertIsNotNone(export_file)
        self.assertTrue(export_file.exists())

        # Load and validate SARIF JSON
        with open(export_file, 'r') as f:
            sarif_data = json.load(f)

        self.assertEqual(sarif_data["version"], "2.1.0")
        self.assertIn("runs", sarif_data)

        # Check run
        run = sarif_data["runs"][0]
        self.assertIn("tool", run)
        self.assertIn("results", run)
        self.assertEqual(run["tool"]["driver"]["name"], "CodeReviewAgent")

        # Check results
        results = run["results"]
        self.assertEqual(len(results), 2)

        # Check first result (CRITICAL)
        critical_result = results[0]
        self.assertEqual(critical_result["level"], "error")
        self.assertEqual(critical_result["ruleId"], "security/CRITICAL")
        self.assertIn("SQL injection", critical_result["message"]["text"])

        # Check location
        location = critical_result["locations"][0]["physicalLocation"]
        self.assertEqual(location["artifactLocation"]["uri"], "api/auth.py")
        self.assertEqual(location["region"]["startLine"], 45)

    def test_export_sarif_rules(self):
        """Test SARIF rules are built correctly."""
        rules = self.agent._build_sarif_rules(self.review_data)

        self.assertEqual(len(rules), 2)  # 2 unique category/severity combinations

        # Check rules have required fields
        for rule in rules:
            self.assertIn("id", rule)
            self.assertIn("name", rule)
            self.assertIn("shortDescription", rule)
            self.assertIn("fullDescription", rule)
            self.assertIn("properties", rule)

        # Check specific rule IDs
        rule_ids = [r["id"] for r in rules]
        self.assertIn("code_quality/MINOR", rule_ids)
        self.assertIn("security/CRITICAL", rule_ids)

    def test_export_review_all_formats(self):
        """Test exporting to all formats."""
        # Save review data first
        self.agent._save_review_result(self.review_data)

        # Export to all formats
        exported = self.agent.export_review()

        self.assertIn("reviewdog", exported)
        self.assertIn("sarif", exported)

        # Verify both files exist
        self.assertTrue(Path(exported["reviewdog"]).exists())
        self.assertTrue(Path(exported["sarif"]).exists())

    def test_export_review_specific_format(self):
        """Test exporting to specific format only."""
        # Save review data first
        self.agent._save_review_result(self.review_data)

        # Export only Reviewdog
        exported = self.agent.export_review(formats=["reviewdog"])

        self.assertIn("reviewdog", exported)
        self.assertNotIn("sarif", exported)

    def test_export_review_with_provided_data(self):
        """Test exporting with directly provided review data."""
        exported = self.agent.export_review(
            review_data=self.review_data,
            formats=["sarif"]
        )

        self.assertIn("sarif", exported)
        self.assertTrue(Path(exported["sarif"]).exists())

    def test_export_review_no_data(self):
        """Test exporting when no review data exists."""
        # Don't save any review data
        exported = self.agent.export_review()

        # Should return empty dict
        self.assertEqual(exported, {})

    def test_export_reviewdog_with_suggestions(self):
        """Test Reviewdog export includes suggestions."""
        exports_dir = self.agent.review_dir / "exports"
        export_file = self.agent._export_reviewdog(self.review_data, exports_dir)

        with open(export_file, 'r') as f:
            reviewdog_data = json.load(f)

        # First diagnostic should have suggestions (has suggestion and code_example)
        first_diag = reviewdog_data["diagnostics"][0]
        self.assertIn("suggestions", first_diag)
        self.assertGreater(len(first_diag["suggestions"]), 0)
        self.assertIn("parameterized queries", first_diag["suggestions"][0]["text"])

    def test_export_sarif_with_markdown(self):
        """Test SARIF export includes markdown formatting."""
        exports_dir = self.agent.review_dir / "exports"
        export_file = self.agent._export_sarif(self.review_data, exports_dir)

        with open(export_file, 'r') as f:
            sarif_data = json.load(f)

        # First result should have markdown message
        first_result = sarif_data["runs"][0]["results"][0]
        self.assertIn("markdown", first_result["message"])
        self.assertIn("**Suggestion**", first_result["message"]["markdown"])


class TestPhase3Integration(unittest.TestCase):
    """Integration tests for Phase 3 features."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "project"
        self.project_dir.mkdir()

        # Create mock LLM provider
        self.mock_llm = MockLLMProvider()

        # Create agent
        self.agent = CodeReviewAgent(
            session_id="test_session",
            llm=self.mock_llm,
            project_directory=str(self.project_dir)
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_workflow_user_files_and_export(self):
        """Test full workflow: user files → review → export."""
        # Step 1: Create user-provided files
        diff_file = self.project_dir / "changes.diff"
        diff_content = """diff --git a/api/auth.py b/api/auth.py
index 1234567..abcdefg 100644
--- a/api/auth.py
+++ b/api/auth.py
@@ -10,7 +10,7 @@
-    query = f"SELECT * FROM users WHERE id = {user_id}"
+    query = "SELECT * FROM users WHERE id = ?"
"""
        diff_file.write_text(diff_content)

        pr_desc_file = self.project_dir / "pr.md"
        pr_desc_file.write_text("# Fix SQL Injection\n\nFixed SQL injection vulnerability.")

        # Step 2: Handle user-provided files
        result = self.agent.handle_user_provided_files(
            diff_file=str(diff_file),
            pr_description_file=str(pr_desc_file)
        )

        self.assertEqual(len(result["copied_files"]), 2)
        self.assertEqual(len(result["errors"]), 0)

        # Step 3: Create and save a review
        review_data = {
            "verdict": "APPROVE",
            "summary": "Good fix for SQL injection",
            "comments": [],
            "strengths": ["Fixed critical security issue"],
            "recommendations": []
        }

        self.agent._save_review_result(review_data)

        # Step 4: Export to multiple formats
        exported = self.agent.export_review()

        self.assertIn("reviewdog", exported)
        self.assertIn("sarif", exported)

        # Verify exports exist
        self.assertTrue(Path(exported["reviewdog"]).exists())
        self.assertTrue(Path(exported["sarif"]).exists())


if __name__ == '__main__':
    unittest.main()
