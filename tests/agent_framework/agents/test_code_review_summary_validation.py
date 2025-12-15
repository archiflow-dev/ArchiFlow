"""
Tests for CodeReviewAgent summary validation (Option A implementation).

Tests the ability to detect and replace generic summaries with meaningful ones.
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from src.agent_framework.agents.code_review_agent import CodeReviewAgent
from src.agent_framework.llm.mock import MockLLMProvider


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def review_agent(mock_llm, tmp_path):
    """Create a CodeReviewAgent instance."""
    agent = CodeReviewAgent(
        session_id="test_session",
        llm=mock_llm,
        project_directory=str(tmp_path)
    )
    return agent


# ======================================================================
# Test _is_generic_summary
# ======================================================================

def test_is_generic_summary_detects_generic_phrases(review_agent):
    """Test that generic phrases are detected."""
    generic_summaries = [
        "All 5 review phases completed and todos marked completed. Delivering structured JSON review result",
        "Review complete",
        "All phases done",
        "Task finished",
        "Delivering structured json",
        "Todos marked completed",
        "Review finished successfully"
    ]

    for summary in generic_summaries:
        assert review_agent._is_generic_summary(summary) is True, f"Failed to detect generic: {summary}"


def test_is_generic_summary_accepts_real_summaries(review_agent):
    """Test that real summaries are not flagged as generic."""
    real_summaries = [
        "The authentication module is well-structured with proper error handling. Found 2 minor issues in input validation.",
        "The new API endpoint is well-designed with comprehensive tests. One critical security issue found.",
        "Refactoring improves code clarity significantly. No functional issues found.",
        "The changes introduce a memory leak in the file upload handler. Requires fixing before merge."
    ]

    for summary in real_summaries:
        assert review_agent._is_generic_summary(summary) is False, f"Incorrectly flagged as generic: {summary}"


def test_is_generic_summary_handles_empty(review_agent):
    """Test that empty summaries are flagged as generic."""
    assert review_agent._is_generic_summary("") is True
    assert review_agent._is_generic_summary("   ") is True
    assert review_agent._is_generic_summary(None) is True


# ======================================================================
# Test _generate_summary_from_review
# ======================================================================

def test_generate_summary_approve_with_strengths(review_agent):
    """Test summary generation for APPROVE with strengths."""
    review_data = {
        "verdict": "APPROVE",
        "comments": [],
        "strengths": ["Good error handling", "Well-tested", "Clean code"],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "3 strength(s)" in summary
    assert "No blocking issues" in summary


def test_generate_summary_approve_without_strengths(review_agent):
    """Test summary generation for APPROVE without strengths."""
    review_data = {
        "verdict": "APPROVE",
        "comments": [],
        "strengths": [],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "No issues found" in summary
    assert "Code looks good" in summary


def test_generate_summary_request_changes_with_issues(review_agent):
    """Test summary generation for REQUEST_CHANGES with issues."""
    review_data = {
        "verdict": "REQUEST_CHANGES",
        "comments": [
            {"severity": "CRITICAL", "issue": "SQL injection"},
            {"severity": "CRITICAL", "issue": "XSS vulnerability"},
            {"severity": "MAJOR", "issue": "Performance issue"},
            {"severity": "MINOR", "issue": "Code style"}
        ],
        "strengths": [],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "2 critical" in summary
    assert "1 major" in summary
    assert "1 minor" in summary
    assert "require attention" in summary


def test_generate_summary_request_changes_no_comments(review_agent):
    """Test summary generation for REQUEST_CHANGES without comments."""
    review_data = {
        "verdict": "REQUEST_CHANGES",
        "comments": [],
        "strengths": [],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "requests changes" in summary
    assert "See comments" in summary


def test_generate_summary_comment_with_observations(review_agent):
    """Test summary generation for COMMENT with observations."""
    review_data = {
        "verdict": "COMMENT",
        "comments": [
            {"severity": "MINOR", "issue": "Could be improved"},
            {"severity": "NIT", "issue": "Naming suggestion"}
        ],
        "strengths": [],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "2 observation(s)" in summary
    assert "Minor suggestions" in summary
    assert "no blocking issues" in summary


def test_generate_summary_comment_with_critical_issues(review_agent):
    """Test summary generation for COMMENT with critical issues."""
    review_data = {
        "verdict": "COMMENT",
        "comments": [
            {"severity": "CRITICAL", "issue": "Security concern"},
            {"severity": "MAJOR", "issue": "Performance issue"}
        ],
        "strengths": [],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "2 observation(s)" in summary
    assert "issues need attention" in summary


def test_generate_summary_comment_no_observations(review_agent):
    """Test summary generation for COMMENT with no observations."""
    review_data = {
        "verdict": "COMMENT",
        "comments": [],
        "strengths": [],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "No issues" in summary


def test_generate_summary_comment_with_strengths_no_comments(review_agent):
    """Test summary generation for COMMENT with strengths but no comments."""
    review_data = {
        "verdict": "COMMENT",
        "comments": [],
        "strengths": ["Good design", "Well-tested"],
        "recommendations": []
    }

    summary = review_agent._generate_summary_from_review(review_data)

    assert "2 strength(s)" in summary
    assert "No issues" in summary


# ======================================================================
# Integration Test: _handle_finish_task
# ======================================================================

def test_handle_finish_task_replaces_generic_summary(review_agent, tmp_path, caplog):
    """Test that _handle_finish_task detects and replaces generic summaries."""
    import json
    from unittest.mock import MagicMock

    # Create review directory
    review_dir = tmp_path / ".agent" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    # Create mock tool call with generic summary
    tool_call = MagicMock()
    tool_call.name = "finish_task"
    tool_call.arguments = {
        "result": json.dumps({
            "verdict": "APPROVE",
            "summary": "All 5 review phases completed and todos marked completed. Delivering structured JSON review result",
            "comments": [],
            "strengths": ["Good code", "Well tested"],
            "recommendations": []
        })
    }

    # Mock the parent's _handle_finish_task
    with patch.object(review_agent.__class__.__bases__[0], '_handle_finish_task') as mock_parent:
        mock_parent.return_value = None

        # Call _handle_finish_task
        result = review_agent._handle_finish_task([tool_call])

        # Verify parent was called
        mock_parent.assert_called_once()

    # Check that warning was logged
    assert "Generic summary detected and replaced" in caplog.text

    # Read the saved JSON to verify summary was replaced
    json_file = review_dir / "latest.json"
    if json_file.exists():
        with open(json_file, 'r') as f:
            saved_data = json.load(f)

        # Verify summary was replaced
        assert "All 5 review phases" not in saved_data["summary"]
        assert "2 strength(s)" in saved_data["summary"]
        assert "No blocking issues" in saved_data["summary"]


def test_handle_finish_task_keeps_real_summary(review_agent, tmp_path, caplog):
    """Test that _handle_finish_task keeps real summaries unchanged."""
    import json
    from unittest.mock import MagicMock

    # Create review directory
    review_dir = tmp_path / ".agent" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    real_summary = "The authentication module is well-structured. Found 2 minor issues in input validation."

    # Create mock tool call with real summary
    tool_call = MagicMock()
    tool_call.name = "finish_task"
    tool_call.arguments = {
        "result": json.dumps({
            "verdict": "REQUEST_CHANGES",
            "summary": real_summary,
            "comments": [
                {"severity": "MINOR", "issue": "Missing validation"}
            ],
            "strengths": [],
            "recommendations": []
        })
    }

    # Mock the parent's _handle_finish_task
    with patch.object(review_agent.__class__.__bases__[0], '_handle_finish_task') as mock_parent:
        mock_parent.return_value = None

        # Call _handle_finish_task
        result = review_agent._handle_finish_task([tool_call])

        # Verify parent was called
        mock_parent.assert_called_once()

    # Check that NO warning was logged
    assert "Generic summary detected" not in caplog.text

    # Read the saved JSON to verify summary was NOT changed
    json_file = review_dir / "latest.json"
    if json_file.exists():
        with open(json_file, 'r') as f:
            saved_data = json.load(f)

        # Verify summary remained unchanged
        assert saved_data["summary"] == real_summary
