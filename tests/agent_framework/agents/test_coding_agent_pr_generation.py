"""
Tests for CodingAgent LLM-based PR description generation (Phase 1.5).

Tests cover:
- Context gathering for PR description
- LLM-based PR description generation
- Fallback template generation
- Metadata tracking
- File saving
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile
import shutil
import json

from src.agent_framework.agents.coding_agent import CodingAgent  
from src.agent_framework.llm.provider import LLMResponse
from src.agent_framework.llm.mock import MockLLMProvider


class TestCodingAgentPRGeneration(unittest.TestCase):
    """Test suite for PR description generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.mock_llm = MockLLMProvider()
        self.session_id = "test_pr_gen_session"
        
        # Create agent
        self.agent = CodingAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
    
    def tearDown(self):
        """Clean up."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_gather_pr_context_with_draft(self):
        """Test gathering PR context from draft file."""
        # Create draft file
        review_dir = Path(self.test_dir) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        draft_content = """# PR Description (Draft)

## What was requested
Implement rate limiting for API endpoints

## Implementation Progress
Working on it...
"""
        (review_dir / "pr_description.draft.md").write_text(draft_content)
        
        # Gather context
        context = self.agent._gather_pr_context()
        
        self.assertIn("Implement rate limiting", context["original_request"])
        self.assertIn("original_request", context)
        self.assertIn("todos_completed", context)
        self.assertIn("files_changed", context)
    
    def test_gather_pr_context_without_draft(self):
        """Test gathering PR context when no draft exists."""
        context = self.agent._gather_pr_context()
        
        self.assertEqual(context["original_request"], "Task completed")
        self.assertIsInstance(context["todos_completed"], list)
        self.assertIsInstance(context["files_changed"], list)
    
    @patch('subprocess.run')
    def test_gather_pr_context_with_git_changes(self, mock_run):
        """Test gathering file changes from git."""
        # Mock git diff output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "src/api.py\nsrc/middleware.py\n"
        mock_run.return_value = mock_result
        
        context = self.agent._gather_pr_context()
        
        self.assertIn("src/api.py", context["files_changed"])
        self.assertIn("src/middleware.py", context["files_changed"])
    
    def test_format_todos_for_pr_empty(self):
        """Test formatting empty TODO list."""
        result = self.agent._format_todos_for_pr([])
        
        self.assertIn("completed successfully", result)
    
    def test_format_todos_for_pr_with_items(self):
        """Test formatting TODO list with multiple items."""
        todos = ["Create API endpoint", "Add tests", "Update documentation"]
        result = self.agent._format_todos_for_pr(todos)
        
        for todo in todos:
            self.assertIn(todo, result)
        self.assertEqual(result.count("✅"), 3)
    
    def test_generate_fallback_pr_description(self):
        """Test fallback PR description generation."""
        context = {
            "original_request": "Add feature X",
            "todos_completed": ["Task 1", "Task 2"],
            "files_changed": ["file1.py", "file2.py"],
            "implementation_notes": "Notes here"
        }
        
        result = self.agent._generate_fallback_pr_description(context)
        
        self.assertIn("Add feature X", result)
        self.assertIn("Task 1", result)
        self.assertIn("file1.py", result)
        self.assertIn(self.session_id, result)
    
    def test_generate_final_pr_description_creates_file(self):
        """Test that PR description file is created."""
        # Create draft first
        review_dir = Path(self.test_dir) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        draft = """# PR Description (Draft)
## What was requested
Test request"""
        (review_dir / "pr_description.draft.md").write_text(draft)
        
        # Generate final description
        result = self.agent._generate_final_pr_description()
        
        # Check file created
        pr_file = review_dir / "pr_description.md"
        self.assertTrue(pr_file.exists())
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
    
    def test_generate_final_pr_description_updates_metadata(self):
        """Test that metadata is updated with final PR description."""
        # Create draft
        review_dir = Path(self.test_dir) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "pr_description.draft.md").write_text("## What was requested\nTest")
        
        # Generate
        self.agent._generate_final_pr_description()
        
        # Check metadata
        metadata_file = review_dir / "metadata.json"
        self.assertTrue(metadata_file.exists())
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        self.assertEqual(metadata["pr_description"]["file"], "pr_description.md")
        self.assertEqual(metadata["pr_description"]["source"], "llm_generated")
        self.assertEqual(metadata["pr_description"]["generation_strategy"], "hybrid")
        self.assertFalse(metadata["pr_description"]["is_draft"])
    
    @patch.object(MockLLMProvider, 'generate')
    def test_generate_final_pr_description_uses_llm(self, mock_generate):
        """Test that LLM is called with proper prompt."""
        # Setup
        review_dir = Path(self.test_dir) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "pr_description.draft.md").write_text("## What was requested\nTest task")
        
        # Mock LLM response
        mock_response = LLMResponse(content="# Generated PR Description\n\nTest content")
        mock_generate.return_value = mock_response
        
        # Generate
        result = self.agent._generate_final_pr_description()
        
        # Check LLM was called
        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        prompt = call_args[0][0]
        
        self.assertIn("Original User Request", prompt)
        self.assertIn("Completed Work", prompt)
        self.assertIn("Implementation Details", prompt)
    
    @patch.object(MockLLMProvider, 'generate')
    def test_generate_final_pr_description_falls_back_on_error(self, mock_generate):
        """Test fallback when LLM fails."""
        # Setup
        review_dir = Path(self.test_dir) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "pr_description.draft.md").write_text("## What was requested\nTest")
        
        # Mock LLM failure
        mock_generate.side_effect = Exception("LLM Error")
        
        # Generate (should not raise)
        result = self.agent._generate_final_pr_description()
        
        # Should have fallback content
        self.assertIn("Auto-generated", result)
        self.assertIn("fallback", result.lower())
    
    def test_generate_final_pr_description_comprehensive(self):
        """Comprehensive test with realistic scenario."""
        # Setup complete scenario
        review_dir = Path(self.test_dir) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        # Draft with realistic content
        draft = """# PR Description (Draft)

**Created**: 2024-12-09
**Session**: test_session

## What was requested  
Implement rate limiting middleware for API endpoints with Redis backend.
Support different tiers for authenticated and anonymous users.

## Implementation Progress
[Updating...]
"""
        (review_dir / "pr_description.draft.md").write_text(draft)
        
        # Generate
        result = self.agent._generate_final_pr_description()
        
        # Validate result
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 50)  # Should be substantial
        
        # Check file was saved
        pr_file = review_dir / "pr_description.md"
        self.assertTrue(pr_file.exists())
        saved_content = pr_file.read_text()
        self.assertEqual(result, saved_content)


if __name__ == '__main__':
    unittest.main()
