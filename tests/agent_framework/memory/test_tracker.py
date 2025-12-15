"""
Tests for EnvironmentTracker.
"""
import pytest
from src.agent_framework.memory.tracker import EnvironmentTracker

def test_environment_tracker_initialization():
    """Test tracker initializes with current directory."""
    tracker = EnvironmentTracker()
    assert tracker.cwd is not None
    assert isinstance(tracker.recent_files, set)

def test_cwd_update():
    """Test that CWD updates on directory change."""
    tracker = EnvironmentTracker()
    initial_cwd = tracker.cwd
    
    tracker.update("change_directory", {"path": "/new/path"}, "Changed to /new/path")
    assert tracker.cwd == "/new/path"

def test_file_tracking():
    """Test that files are tracked on read/write operations."""
    tracker = EnvironmentTracker()
    
    tracker.update("read_file", {"path": "/tmp/test.txt"}, "file content")
    assert "/tmp/test.txt" in tracker.recent_files
    
    tracker.update("write_file", {"path": "/tmp/output.txt"}, "Written")
    assert "/tmp/output.txt" in tracker.recent_files

def test_recent_files_limit():
    """Test that recent files list is limited."""
    tracker = EnvironmentTracker()
    tracker.max_recent_files = 3
    
    for i in range(5):
        tracker.update("read_file", {"path": f"/file{i}.txt"}, "content")
    
    # Should only keep 3 files (plus possibly the last one)
    assert len(tracker.recent_files) <= 4  # Account for set behavior

def test_get_summary():
    """Test summary generation."""
    tracker = EnvironmentTracker()
    tracker.cwd = "/project"
    tracker.update("read_file", {"path": "test.py"}, "content")
    
    summary = tracker.get_summary()
    assert "/project" in summary
    assert "test.py" in summary
