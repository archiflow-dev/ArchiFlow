"""
Unit tests for CodeReviewAgent.

Tests cover:
- Initialization and configuration
- Review folder structure creation
- Metadata management
- Diff auto-generation
- Diff statistics parsing
- Tool filtering (read-only enforcement)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
import json
import tempfile
import shutil

from src.agent_framework.agents.code_review_agent import CodeReviewAgent
from src.agent_framework.llm.mock import MockLLMProvider


class TestCodeReviewAgent(unittest.TestCase):
    """Test suite for CodeReviewAgent."""
    
    def setUp(self):
        """Set up test fixtures before each test."""
        # Create temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        
        # Use MockLLMProvider instead of Mock for proper behavior
        self.mock_llm = MockLLMProvider()
        
        # Test session ID
        self.session_id = "test_session_123"
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove temp directory
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_initialization_basic(self):
        """Test basic agent initialization."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        self.assertEqual(agent.session_id, self.session_id)
        # project_directory is a Path, compare resolved paths
        self.assertEqual(Path(agent.project_directory), Path(self.test_dir).resolve())
        self.assertEqual(agent.review_depth, "standard")
        self.assertEqual(agent.focus_areas, ['all'])
        self.assertIsNone(agent.diff_file)
        self.assertIsNone(agent.pr_description_file)
    
    def test_initialization_with_parameters(self):
        """Test initialization with custom parameters."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir,
            diff_file="test.diff",
            pr_description_file="pr.md",
            review_depth="thorough",
            focus_areas=["security", "performance"]
        )
        
        self.assertEqual(agent.diff_file, "test.diff")
        self.assertEqual(agent.pr_description_file, "pr.md")
        self.assertEqual(agent.review_depth, "thorough")
        self.assertEqual(agent.focus_areas, ["security", "performance"])
    
    def test_review_folder_creation(self):
        """Test that review folder structure is created on init."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        review_dir = Path(self.test_dir) / ".agent" / "review"
        
        # Check directories exist
        self.assertTrue(review_dir.exists())
        self.assertTrue((review_dir / "results").exists())
        self.assertTrue((review_dir / "results" / "history").exists())
        self.assertTrue((review_dir / "context").exists())
        
        # Check metadata file exists
        metadata_file = review_dir / "metadata.json"
        self.assertTrue(metadata_file.exists())
    
    def test_metadata_initialization(self):
        """Test metadata.json is properly initialized."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        metadata = agent._load_metadata()
        
        self.assertIn("created", metadata)
        self.assertIn("last_updated", metadata)
        self.assertEqual(metadata["current_session"], self.session_id)
        self.assertEqual(metadata["reviews"], [])
    
    def test_metadata_reuses_existing(self):
        """Test that existing metadata is reused, not overwritten."""
        # Create agent once
        agent1 = CodeReviewAgent(
            session_id="session_1",
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        created_time = agent1._load_metadata()["created"]
        
        # Create agent again with different session
        agent2 = CodeReviewAgent(
            session_id="session_2",
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        metadata = agent2._load_metadata()
        
        # Created time should be the same
        self.assertEqual(metadata["created"], created_time)
        # But session should be updated
        self.assertEqual(metadata["current_session"], "session_2")
    
    def test_save_and_load_metadata(self):
        """Test metadata save and load cycle."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        # Add custom data
        metadata = agent._load_metadata()
        metadata["test_key"] = "test_value"
        metadata["reviews"].append({"id": "review_1"})
        agent._save_metadata(metadata)
        
        # Load again
        loaded = agent._load_metadata()
        
        self.assertEqual(loaded["test_key"], "test_value")
        self.assertEqual(len(loaded["reviews"]), 1)
        self.assertEqual(loaded["reviews"][0]["id"], "review_1")
    
    def test_parse_diff_stats_basic(self):
        """Test diff statistics parsing with basic diff."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        diff_content = """diff --git a/file1.py b/file1.py
index abc123..def456 100644
--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,4 @@
+new line
 existing line
-removed line
 another line
"""
        
        stats = agent._parse_diff_stats(diff_content)
        
        self.assertEqual(stats["files_changed"], 1)
        self.assertEqual(stats["insertions"], 1)
        self.assertEqual(stats["deletions"], 1)
    
    def test_parse_diff_stats_multiple_files(self):
        """Test diff parsing with multiple files."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        diff_content = """diff --git a/file1.py b/file1.py
index abc123..def456 100644
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,3 @@
+line1
 line2
diff --git a/file2.py b/file2.py
index 123abc..456def 100644
--- a/file2.py
+++ b/file2.py
@@ -1,2 +1,1 @@
-removed
 kept
"""
        
        stats = agent._parse_diff_stats(diff_content)
        
        self.assertEqual(stats["files_changed"], 2)
        self.assertEqual(stats["insertions"], 1)
        self.assertEqual(stats["deletions"], 1)
    
    def test_parse_diff_stats_ignores_headers(self):
        """Test that +++ and --- lines are not counted."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        diff_content = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,1 +1,1 @@
+added line
"""
        
        stats = agent._parse_diff_stats(diff_content)
        
        # Should only count the +added line, not +++
        self.assertEqual(stats["insertions"], 1)
        self.assertEqual(stats["deletions"], 0)
    
    @patch('subprocess.run')
    def test_auto_generate_diff_from_staged(self, mock_run):
        """Test diff generation from staged changes."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        # Mock git diff --cached returning content
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """diff --git a/test.py b/test.py
+added line
"""
        mock_run.return_value = mock_result
        
        diff_file = agent._auto_generate_diff()
        
        # Should call git diff --cached (first call)
        mock_run.assert_called()
        first_call = mock_run.call_args_list[0]
        self.assertEqual(first_call[0][0], ["git", "diff", "--cached"])
        
        # Should save diff file
        self.assertTrue(Path(diff_file).exists())
        
        # Should update metadata
        metadata = agent._load_metadata()
        self.assertEqual(metadata["diff"]["source"], "staged")
        self.assertEqual(metadata["diff"]["stats"]["insertions"], 1)
    
    @patch('subprocess.run')
    def test_auto_generate_diff_fallback_to_working_dir(self, mock_run):
        """Test fallback to working directory when no staged changes."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        # Mock responses
        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            result = Mock()
            result.returncode = 0
            
            if "--cached" in cmd:
                # No staged changes
                result.stdout = ""
            else:
                # Working directory has changes
                result.stdout = """diff --git a/test.py b/test.py
+working dir change
"""
            return result
        
        mock_run.side_effect = run_side_effect
        
        diff_file = agent._auto_generate_diff()
        
        # Should have tried both commands
        self.assertEqual(mock_run.call_count, 2)
        
        # Metadata should show working_directory source
        metadata = agent._load_metadata()
        self.assertEqual(metadata["diff"]["source"], "working_directory")
    
    @patch('subprocess.run')
    def test_auto_generate_diff_no_changes_raises_error(self, mock_run):
        """Test that error is raised when no changes found."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        # Mock all git commands returning empty
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result
        
        with self.assertRaises(ValueError) as context:
            agent._auto_generate_diff()
        
        self.assertIn("No changes detected", str(context.exception))
    
    def test_allowed_tools_read_only(self):
        """Test that only read-only tools are allowed."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        # Check allowed tools list
        read_only_tools = ["read", "list", "glob", "grep"]
        for tool in read_only_tools:
            self.assertIn(tool, agent.allowed_tools)
        
        # Write tools should not be included
        write_tools = ["edit", "write", "bash"]
        for tool in write_tools:
            self.assertNotIn(tool, agent.allowed_tools)
        
        # Progress tracking should be allowed
        self.assertIn("todo_write", agent.allowed_tools)
        self.assertIn("todo_read", agent.allowed_tools)
        self.assertIn("finish_task", agent.allowed_tools)
    
    def test_get_system_message(self):
        """Test system message generation."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir,
            diff_file="test.diff",
            pr_description_file="pr.md"
        )
        
        system_msg = agent.get_system_message()
        
        # Should contain key workflow steps
        self.assertIn("UNDERSTAND", system_msg)
        self.assertIn("EXAMINE", system_msg)
        self.assertIn("ANALYZE", system_msg)
        self.assertIn("FEEDBACK", system_msg)
        self.assertIn("RECOMMEND", system_msg)
        
        # Should mention severity levels
        self.assertIn("CRITICAL", system_msg)
        self.assertIn("MAJOR", system_msg)
        self.assertIn("MINOR", system_msg)
        self.assertIn("NIT", system_msg)
        
        # Should mention JSON output format
        self.assertIn("JSON", system_msg)
        self.assertIn("verdict", system_msg)
    
    def test_format_finish_message(self):
        """Test finish message formatting."""
        agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        reason = "Review complete"
        result = '{"verdict": "APPROVE", "comments": []}'
        
        formatted = agent._format_finish_message(reason, result)
        
        self.assertIn(reason, formatted)
        self.assertIn(result, formatted)
        self.assertIn("\n\n", formatted)  # Proper separation


class TestPhase2ReviewOutput(unittest.TestCase):
    """Test Phase 2.1-2.3: Review output formatting and saving."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.mock_llm = MockLLMProvider()
        self.session_id = "test_phase2"

        self.agent = CodeReviewAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )

        # Sample review data
        self.sample_review = {
            "verdict": "REQUEST_CHANGES",
            "summary": "Found several security and performance issues that need attention.",
            "comments": [
                {
                    "file": "auth/login.py",
                    "line": 45,
                    "severity": "CRITICAL",
                    "category": "security",
                    "issue": "SQL injection vulnerability",
                    "suggestion": "Use parameterized queries",
                    "code_example": "cursor.execute('SELECT * FROM users WHERE name = ?', (name,))"
                },
                {
                    "file": "api/users.py",
                    "line": 23,
                    "severity": "MAJOR",
                    "category": "performance",
                    "issue": "N+1 query problem in loop",
                    "suggestion": "Use eager loading with join"
                },
                {
                    "file": "utils/helpers.py",
                    "line": 12,
                    "severity": "MINOR",
                    "category": "code_quality",
                    "issue": "Complex nested logic hard to read",
                    "suggestion": "Extract into separate functions"
                },
                {
                    "file": "models/user.py",
                    "line": 67,
                    "severity": "NIT",
                    "category": "code_quality",
                    "issue": "Variable name 'x' is not descriptive",
                    "suggestion": "Use 'user_count' instead"
                }
            ],
            "strengths": [
                "Good test coverage",
                "Clear naming conventions",
                "Proper error handling"
            ],
            "recommendations": [
                {"priority": "HIGH", "item": "Fix SQL injection vulnerability immediately"},
                {"priority": "MEDIUM", "item": "Optimize database queries"},
                {"priority": "LOW", "item": "Refactor complex functions"}
            ]
        }

    def tearDown(self):
        """Clean up."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    # ========================================================================
    # Phase 2.1 Tests: JSON Review Output
    # ========================================================================

    def test_validate_review_result_valid(self):
        """Test validation of valid review result."""
        is_valid = self.agent._validate_review_result(self.sample_review)
        self.assertTrue(is_valid)

    def test_validate_review_result_missing_verdict(self):
        """Test validation fails when verdict is missing."""
        invalid_review = self.sample_review.copy()
        del invalid_review["verdict"]

        is_valid = self.agent._validate_review_result(invalid_review)
        self.assertFalse(is_valid)

    def test_validate_review_result_invalid_verdict(self):
        """Test validation fails with invalid verdict."""
        invalid_review = self.sample_review.copy()
        invalid_review["verdict"] = "INVALID"

        is_valid = self.agent._validate_review_result(invalid_review)
        self.assertFalse(is_valid)

    def test_validate_review_result_invalid_severity(self):
        """Test validation fails with invalid severity."""
        invalid_review = self.sample_review.copy()
        invalid_review["comments"][0]["severity"] = "SUPER_CRITICAL"

        is_valid = self.agent._validate_review_result(invalid_review)
        self.assertFalse(is_valid)

    def test_save_review_result_creates_files(self):
        """Test saving review result creates JSON files."""
        result_file = self.agent._save_review_result(self.sample_review)

        # Check latest.json exists
        self.assertTrue(result_file.exists())
        self.assertEqual(result_file.name, "latest.json")

        # Check content
        with open(result_file, 'r') as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data["verdict"], "REQUEST_CHANGES")
        self.assertEqual(len(saved_data["comments"]), 4)
        self.assertIn("metadata", saved_data)
        self.assertEqual(saved_data["metadata"]["session_id"], self.session_id)

    def test_save_review_result_archives_to_history(self):
        """Test review is archived to history folder."""
        self.agent._save_review_result(self.sample_review)

        # Check history folder exists
        history_dir = Path(self.test_dir) / ".agent" / "review" / "results" / "history"
        self.assertTrue(history_dir.exists())

        # Check at least one file in history
        history_files = list(history_dir.glob("review_*.json"))
        self.assertEqual(len(history_files), 1)

        # Verify content
        with open(history_files[0], 'r') as f:
            archived_data = json.load(f)

        self.assertEqual(archived_data["verdict"], "REQUEST_CHANGES")

    def test_save_review_result_updates_metadata(self):
        """Test metadata is updated with review history."""
        self.agent._save_review_result(self.sample_review)

        metadata = self.agent._load_metadata()

        self.assertIn("reviews", metadata)
        self.assertEqual(len(metadata["reviews"]), 1)

        review_entry = metadata["reviews"][0]
        self.assertEqual(review_entry["verdict"], "REQUEST_CHANGES")
        self.assertEqual(review_entry["comments_count"], 4)
        self.assertEqual(review_entry["session_id"], self.session_id)
        self.assertIn("history/review_", review_entry["file"])

    # ========================================================================
    # Phase 2.3 Tests: Markdown Output
    # ========================================================================

    def test_convert_review_to_markdown(self):
        """Test conversion of review JSON to markdown."""
        markdown = self.agent._convert_review_to_markdown(self.sample_review)

        # Check header
        self.assertIn("# Code Review Report", markdown)
        self.assertIn("**Verdict**: REQUEST_CHANGES", markdown)

        # Check summary
        self.assertIn("## Summary", markdown)
        self.assertIn("Found several security", markdown)

        # Check comments section
        self.assertIn("## Review Comments", markdown)

        # Check severity grouping
        self.assertIn("### 🔴 CRITICAL", markdown)
        self.assertIn("### 🟠 MAJOR", markdown)
        self.assertIn("### 🟡 MINOR", markdown)
        self.assertIn("### ⚪ NIT", markdown)

        # Check specific comments
        self.assertIn("auth/login.py", markdown)
        self.assertIn("Line 45", markdown)
        self.assertIn("SQL injection vulnerability", markdown)

        # Check strengths
        self.assertIn("## Strengths", markdown)
        self.assertIn("Good test coverage", markdown)

        # Check recommendations
        self.assertIn("## Recommendations", markdown)
        self.assertIn("### 🔴 HIGH Priority", markdown)
        self.assertIn("Fix SQL injection", markdown)

    def test_convert_review_to_markdown_no_comments(self):
        """Test markdown generation when no issues found."""
        clean_review = {
            "verdict": "APPROVE",
            "summary": "All good!",
            "comments": [],
            "strengths": ["Everything looks great"],
            "recommendations": []
        }

        markdown = self.agent._convert_review_to_markdown(clean_review)

        self.assertIn("No issues found", markdown)
        self.assertIn("## Strengths", markdown)

    def test_save_markdown_review(self):
        """Test saving markdown review to file."""
        md_file = self.agent._save_markdown_review(self.sample_review)

        # Check file exists
        self.assertTrue(md_file.exists())
        self.assertEqual(md_file.name, "latest.md")

        # Check content
        content = md_file.read_text(encoding='utf-8')
        self.assertIn("# Code Review Report", content)
        self.assertIn("REQUEST_CHANGES", content)
        self.assertIn("SQL injection", content)

        # Check history
        history_dir = Path(self.test_dir) / ".agent" / "review" / "results" / "history"
        history_md_files = list(history_dir.glob("review_*.md"))
        self.assertEqual(len(history_md_files), 1)

    def test_markdown_severity_grouping(self):
        """Test that markdown groups comments by severity correctly."""
        markdown = self.agent._convert_review_to_markdown(self.sample_review)

        # Find positions of severity headers
        critical_pos = markdown.find("### 🔴 CRITICAL")
        major_pos = markdown.find("### 🟠 MAJOR")
        minor_pos = markdown.find("### 🟡 MINOR")
        nit_pos = markdown.find("### ⚪ NIT")

        # Verify order: CRITICAL -> MAJOR -> MINOR -> NIT
        self.assertLess(critical_pos, major_pos)
        self.assertLess(major_pos, minor_pos)
        self.assertLess(minor_pos, nit_pos)

    # ========================================================================
    # Integration Tests: finish_task with review output
    # ========================================================================

    def test_handle_finish_task_with_review_json(self):
        """Test finish_task processing with review JSON."""
        # Create mock tool call
        class MockToolCall:
            def __init__(self):
                self.name = "finish_task"
                self.arguments = {
                    "reason": "Review complete",
                    "result": json.dumps({
                        "verdict": "APPROVE",
                        "summary": "Looks good",
                        "comments": [],
                        "strengths": ["Clean code"],
                        "recommendations": []
                    })
                }

        tool_calls = [MockToolCall()]

        # Process finish_task
        result = self.agent._handle_finish_task(tool_calls)

        # Check agent finished
        self.assertIsNotNone(result)
        self.assertFalse(self.agent.is_running)

        # Check JSON file created
        json_file = Path(self.test_dir) / ".agent" / "review" / "results" / "latest.json"
        self.assertTrue(json_file.exists())

        # Check markdown file created
        md_file = Path(self.test_dir) / ".agent" / "review" / "results" / "latest.md"
        self.assertTrue(md_file.exists())

        # Verify content
        with open(json_file, 'r') as f:
            saved_review = json.load(f)

        self.assertEqual(saved_review["verdict"], "APPROVE")
        self.assertIn("metadata", saved_review)

    def test_handle_finish_task_without_review_json(self):
        """Test finish_task without review JSON creates minimal review."""
        class MockToolCall:
            def __init__(self):
                self.name = "finish_task"
                self.arguments = {
                    "reason": "Review done",
                    "result": ""
                }

        tool_calls = [MockToolCall()]

        result = self.agent._handle_finish_task(tool_calls)

        # Should still create files
        json_file = Path(self.test_dir) / ".agent" / "review" / "results" / "latest.json"
        self.assertTrue(json_file.exists())

        # Check minimal structure
        with open(json_file, 'r') as f:
            saved_review = json.load(f)

        self.assertEqual(saved_review["verdict"], "COMMENT")
        self.assertEqual(saved_review["summary"], "Review done")
        self.assertEqual(saved_review["comments"], [])


if __name__ == '__main__':
    unittest.main()
