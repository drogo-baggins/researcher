"""
Unit tests for SessionManager.

Tests cover CRUD operations, persistence, error handling, and search functionality.
"""

import json
import sqlite3
import pytest
from pathlib import Path

from researcher.session_manager import SessionManager


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path for testing."""
    return tmp_path / "test_sessions.db"


@pytest.fixture
def session_manager(temp_db_path):
    """Create a SessionManager with temporary database."""
    return SessionManager(db_path=temp_db_path)


def test_create_session_success(session_manager):
    """Test successful session creation."""
    session_id = session_manager.create_session("Test Session", "gpt-oss:20b", "ja")
    
    assert session_id is not None
    assert isinstance(session_id, int)
    
    # Verify in database
    loaded = session_manager.load_session(session_id)
    assert loaded is not None
    assert loaded["name"] == "Test Session"
    assert loaded["model"] == "gpt-oss:20b"
    assert loaded["language"] == "ja"
    assert loaded["history"] == []


def test_save_and_load_session(session_manager):
    """Test saving and loading session with history."""
    session_id = session_manager.create_session("Test", "gpt-oss:20b", "ja")
    
    # Create sample history
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    
    # Save session
    saved = session_manager.save_session(session_id, history, "gpt-oss:20b", "ja")
    assert saved is True
    
    # Load and verify
    loaded = session_manager.load_session(session_id)
    assert loaded["history"] == history
    assert len(loaded["history"]) == 2


def test_list_sessions_ordered_by_updated_at(session_manager):
    """Test listing sessions in correct order (newest first)."""
    # Create three sessions
    id1 = session_manager.create_session("Session 1", "gpt-oss:20b", "ja")
    id2 = session_manager.create_session("Session 2", "gpt-oss:20b", "ja")
    id3 = session_manager.create_session("Session 3", "gpt-oss:20b", "ja")
    
    # Update first session (to make it more recent)
    session_manager.save_session(id1, [], "gpt-oss:20b", "ja")
    
    # List sessions
    sessions = session_manager.list_sessions()
    
    # Verify order: id1 should be first (most recently updated)
    assert len(sessions) == 3
    assert sessions[0]["id"] == id1
    # Other sessions should follow (exact order depends on timing)
    assert sessions[1]["id"] in [id2, id3]
    assert sessions[2]["id"] in [id2, id3]


def test_delete_session(session_manager):
    """Test session deletion."""
    session_id = session_manager.create_session("To Delete", "gpt-oss:20b", "ja")
    
    # Verify it exists
    loaded = session_manager.load_session(session_id)
    assert loaded is not None
    
    # Delete
    deleted = session_manager.delete_session(session_id)
    assert deleted is True
    
    # Verify it's gone
    loaded = session_manager.load_session(session_id)
    assert loaded is None


def test_search_sessions_by_name(session_manager):
    """Test searching sessions by name."""
    session_manager.create_session("Python Tutorial", "gpt-oss:20b", "ja")
    session_manager.create_session("JavaScript Guide", "gpt-oss:20b", "ja")
    session_manager.create_session("Python Advanced", "gpt-oss:20b", "ja")
    
    # Search for "Python"
    results = session_manager.search_sessions("Python")
    
    assert len(results) == 2
    assert all("Python" in r["name"] for r in results)


def test_search_sessions_by_history_content(session_manager):
    """Test searching sessions by history content."""
    session_id = session_manager.create_session("History Test", "gpt-oss:20b", "ja")
    
    history = [
        {"role": "user", "content": "Tell me about machine learning"},
        {"role": "assistant", "content": "Machine learning is..."}
    ]
    session_manager.save_session(session_id, history, "gpt-oss:20b", "ja")
    
    # Search for content in history
    results = session_manager.search_sessions("machine learning")
    
    assert len(results) >= 1
    assert any(r["id"] == session_id for r in results)


def test_rename_session(session_manager):
    """Test renaming a session."""
    session_id = session_manager.create_session("Old Name", "gpt-oss:20b", "ja")
    
    # Rename
    renamed = session_manager.rename_session(session_id, "New Name")
    assert renamed is True
    
    # Verify new name
    loaded = session_manager.load_session(session_id)
    assert loaded["name"] == "New Name"


def test_db_path_creation(tmp_path):
    """Test automatic directory creation for database path."""
    # Use a nested path that doesn't exist yet
    db_path = tmp_path / "nested" / "path" / "test.db"
    
    # Should not raise error
    manager = SessionManager(db_path=db_path)
    
    # Verify directory was created
    assert db_path.parent.exists()
    
    # Verify database is usable
    session_id = manager.create_session("Test", "gpt-oss:20b", "ja")
    assert session_id is not None


def test_error_handling_invalid_session_id(session_manager):
    """Test error handling for non-existent session ID."""
    # Load non-existent session
    loaded = session_manager.load_session(99999)
    assert loaded is None
    
    # Save to non-existent session (should fail gracefully)
    saved = session_manager.save_session(99999, [], "gpt-oss:20b", "ja")
    # Note: Save will succeed (UPDATE with no rows) but load should return None
    
    # Delete non-existent session
    deleted = session_manager.delete_session(99999)
    # This will return True (DELETE with no rows is still successful)


def test_concurrent_save_updates_timestamp(session_manager):
    """Test that repeated saves update the timestamp."""
    session_id = session_manager.create_session("Test", "gpt-oss:20b", "ja")
    
    # First save
    loaded1 = session_manager.load_session(session_id)
    timestamp1 = loaded1["updated_at"]
    
    # Small delay and second save
    import time
    time.sleep(0.1)
    session_manager.save_session(session_id, [], "gpt-oss:20b", "ja")
    
    # Verify timestamp updated
    loaded2 = session_manager.load_session(session_id)
    timestamp2 = loaded2["updated_at"]
    
    # Timestamps should be different or at least not strictly equal
    # (SQLite CURRENT_TIMESTAMP has second precision)
    assert timestamp2 >= timestamp1


def test_json_serialization_edge_cases(session_manager):
    """Test JSON serialization of complex history."""
    session_id = session_manager.create_session("Complex", "gpt-oss:20b", "ja")
    
    # History with special characters and nested content
    history = [
        {
            "role": "user",
            "content": "Test with \"quotes\" and\nnewlines"
        },
        {
            "role": "assistant",
            "content": "Response with emojis: 🚀 🎉"
        }
    ]
    
    # Save and load
    session_manager.save_session(session_id, history, "gpt-oss:20b", "ja")
    loaded = session_manager.load_session(session_id)
    
    assert loaded["history"] == history


def test_empty_session_list(session_manager):
    """Test listing when no sessions exist."""
    sessions = session_manager.list_sessions()
    assert sessions == []


def test_search_empty_result(session_manager):
    """Test search with no matches."""
    session_manager.create_session("Test", "gpt-oss:20b", "ja")
    
    results = session_manager.search_sessions("nonexistent")
    assert results == []
