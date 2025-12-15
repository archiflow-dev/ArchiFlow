"""
Additional tests for CodingAgent PR description functionality.

Tests Phase 1.4 implementation:
- PR description draft creation on first message
- Metadata tracking
- File structure validation
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil
import json

from src.agent_framework.agents.coding_agent import CodingAgent
from src.agent_framework.messages.types import UserMessage
from src.agent_framework.llm.mock import MockLLMProvider


class TestCodingAgentPRDescription(unittest.TestCase):
    """Test suite for CodingAgent PR description functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.mock_llm = MockLLMProvider()
        self.session_id = "test_pr_session"
    
    def tearDown(self):
        """Clean up after tests."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_pr_description_draft_created_on_first_message(self):
        """Test that PR description draft is created on first UserMessage."""
        agent = CodingAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        # Send first user message
        user_request = "Implement rate limiting for API endpoints"
        message = UserMessage(
            session_id=self.session_id,
            sequence=1,
            content=user_request
        )
        
        agent.step(message)
        
        # Check draft file was created
        draft_file = Path(self.test_dir) / ".agent" / "review" / "pr_description.draft.md"
        self.assertTrue(draft_file.exists(), "Draft file should be created")
        
        # Check content
        content = draft_file.read_text()
        self.assertIn(user_request, content)
        self.assertIn("PR Description (Draft)", content)
        self.assertIn(self.session_id, content)
        self.assertIn("CodingAgent", content)
    
    def test_pr_description_not_created_on_second_message(self):
        """Test that PR description is only created once."""
        agent = CodingAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        # Send first message
        msg1 = UserMessage(session_id=self.session_id, sequence=1, content="First request")
        agent.step(msg1)
        
        draft_file = Path(self.test_dir) / ".agent" / "review" / "pr_description.draft.md"
        first_content = draft_file.read_text()
        
        # Send second message
        msg2 = UserMessage(session_id=self.session_id, sequence=2, content="Second request")  
        agent.step(msg2)
        
        # Content should not change (second message doesn't create new draft)
        second_content = draft_file.read_text()
        self.assertEqual(first_content, second_content)
    
    def test_review_folder_structure_created(self):
        """Test that .agent/review folder structure is created."""
        agent = CodingAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        message = UserMessage(
            session_id=self.session_id,
            sequence=1,
            content="Test request"
        )
        agent.step(message)
        
        review_dir = Path(self.test_dir) / ".agent" / "review"
        self.assertTrue(review_dir.exists())
        self.assertTrue(review_dir.is_dir())
    
    def test_metadata_updated_with_pr_description(self):
        """Test that metadata.json is updated with PR description info."""
        agent = CodingAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        message = UserMessage(
            session_id=self.session_id,
            sequence=1,
            content="Implement feature X"
        )
        agent.step(message)
        
        # Check metadata
        metadata_file = Path(self.test_dir) / ".agent" / "review" / "metadata.json"
        self.assertTrue(metadata_file.exists())
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        self.assertIn("pr_description", metadata)
        self.assertEqual(metadata["pr_description"]["file"], "pr_description.draft.md")
        self.assertEqual(metadata["pr_description"]["created_by"], self.session_id)
        self.assertEqual(metadata["pr_description"]["source"], "user_request")
        self.assertTrue(metadata["pr_description"]["is_draft"])
    
    def test_pr_description_with_multiline_request(self):
        """Test PR description handles multiline user requests."""
        agent = CodingAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        multiline_request = """Implement the following features:
1. Add rate limiting
2. Improve error handling
3. Add logging"""
        
        message = UserMessage(
            session_id=self.session_id,
            sequence=1,
            content=multiline_request
        )
        agent.step(message)
        
        draft_file = Path(self.test_dir) / ".agent" / "review" / "pr_description.draft.md"
        content = draft_file.read_text()
        
        # All lines should be preserved
        for line in multiline_request.split('\n'):
            self.assertIn(line, content)
    
    def test_metadata_preserves_existing_data(self):
        """Test that existing metadata is preserved when adding PR description."""
        # Create existing metadata
        review_dir = Path(self.test_dir) / ".agent" / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        existing_metadata = {
            "created": "2024-01-01T00:00:00",
            "reviews": [{"id": "review_1"}],
            "custom_field": "custom_value"
        }
        
        metadata_file = review_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(existing_metadata, f)
        
        # Create agent and send message
        agent = CodingAgent(
            session_id=self.session_id,
            llm=self.mock_llm,
            project_directory=self.test_dir
        )
        
        message = UserMessage(
            session_id=self.session_id,
            sequence=1,
            content="New request"
        )
        agent.step(message)
        
        # Load metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Check existing data preserved
        self.assertEqual(metadata["created"], "2024-01-01T00:00:00")
        self.assertEqual(metadata["reviews"], [{"id": "review_1"}])
        self.assertEqual(metadata["custom_field"], "custom_value")
        
        # Check new data added
        self.assertIn("pr_description", metadata)


if __name__ == '__main__':
    unittest.main()
