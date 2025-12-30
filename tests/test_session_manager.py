"""
Unit tests for SessionManager (V2 Schema).

Tests cover CRUD operations for sessions and exchanges, tag management,
persistence, error handling, and search functionality.

V2 Schema:
- sessions table: id, name, tags (JSON), created_at, updated_at
- exchanges table: id, session_id (FK), user_message, assistant_message,
                   model, language, search_results (JSON), evaluation_score (JSON),
                   created_at

Removed: session_groups table and all group-related methods
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
    """Create a SessionManager with temporary database.
    
    Note: This fixture expects V2 schema to be initialized.
    Run migrate_db.py first if testing against an existing database.
    """
    # Initialize with migrate_db to ensure V2 schema
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from migrate_db import run_migrations
    run_migrations(temp_db_path)
    
    return SessionManager(db_path=temp_db_path)


# ============================================================================
# V2 Schema: Core CRUD Tests
# ============================================================================

def test_create_session_success(session_manager):
    """Test successful session creation with V2 schema."""
    session_id = session_manager.create_session("Test Session", tags=["python", "ai"])
    
    assert session_id is not None
    assert isinstance(session_id, int)
    
    # Verify in database
    loaded = session_manager.load_session(session_id)
    assert loaded is not None
    assert loaded["name"] == "Test Session"
    assert loaded["tags"] == ["python", "ai"]
    assert loaded["exchanges"] == []


def test_save_and_load_exchanges(session_manager):
    """Test saving and loading exchanges."""
    session_id = session_manager.create_session("Test", tags=["test"])
    
    # Save first exchange
    exchange1_id = session_manager.save_exchange(
        session_id, "Hello", "Hi there!", "test-model", "ja"
    )
    assert exchange1_id is not None
    
    # Save second exchange
    exchange2_id = session_manager.save_exchange(
        session_id, "How are you?", "I'm doing well!", "test-model", "ja"
    )
    assert exchange2_id is not None
    
    # Load and verify
    loaded = session_manager.load_session(session_id)
    assert len(loaded["exchanges"]) == 2
    assert loaded["exchanges"][0]["user_message"] == "Hello"
    assert loaded["exchanges"][0]["assistant_message"] == "Hi there!"
    assert loaded["exchanges"][1]["user_message"] == "How are you?"


def test_exchanges_ordered_by_created_at(session_manager):
    """Test exchanges are returned in chronological order."""
    session_id = session_manager.create_session("Test")
    
    # Save three exchanges
    session_manager.save_exchange(session_id, "Q1", "A1", "test-model", "ja")
    session_manager.save_exchange(session_id, "Q2", "A2", "test-model", "ja")
    session_manager.save_exchange(session_id, "Q3", "A3", "test-model", "ja")
    
    # Load and verify order
    loaded = session_manager.load_session(session_id)
    assert loaded["exchanges"][0]["user_message"] == "Q1"
    assert loaded["exchanges"][1]["user_message"] == "Q2"
    assert loaded["exchanges"][2]["user_message"] == "Q3"


def test_list_sessions_ordered_by_updated_at(session_manager):
    """Test listing sessions in correct order (newest first)."""
    import time
    
    # Create three sessions
    id1 = session_manager.create_session("Session 1")
    time.sleep(0.01)
    id2 = session_manager.create_session("Session 2")
    time.sleep(0.01)
    id3 = session_manager.create_session("Session 3")
    
    # Add exchange to id1 to make it most recent
    time.sleep(0.01)
    session_manager.save_exchange(id1, "Q", "A", "test-model", "ja")
    
    # List sessions
    sessions = session_manager.list_sessions()
    
    # Verify order: id1 should be first (most recently updated)
    assert len(sessions) == 3
    assert sessions[0]["id"] == id1


def test_delete_session(session_manager):
    """Test session deletion (cascades to exchanges)."""
    session_id = session_manager.create_session("To Delete")
    
    # Add exchange
    session_manager.save_exchange(session_id, "Q", "A", "test-model", "ja")
    
    # Verify it exists
    loaded = session_manager.load_session(session_id)
    assert loaded is not None
    assert len(loaded["exchanges"]) == 1
    
    # Delete
    deleted = session_manager.delete_session(session_id)
    assert deleted is True
    
    # Verify it's gone
    loaded = session_manager.load_session(session_id)
    assert loaded is None


def test_foreign_key_constraint_blocks_invalid_session_id(session_manager):
    """Test that foreign key constraint blocks exchanges with invalid session_id."""
    # Attempt to save exchange with non-existent session_id
    exchange_id = session_manager.save_exchange(
        99999, "Q", "A", "test-model", "ja"
    )
    
    # Should fail (return None)
    assert exchange_id is None


def test_search_sessions_by_name(session_manager):
    """Test searching sessions by name."""
    session_manager.create_session("Python Tutorial", tags=["python"])
    session_manager.create_session("JavaScript Guide", tags=["js"])
    session_manager.create_session("Python Advanced", tags=["python"])
    
    results = session_manager.search_sessions("Python")
    assert len(results) == 2
    assert all("Python" in r["name"] for r in results)


def test_search_sessions_by_exchange_content(session_manager):
    """Test searching sessions by exchange message content."""
    session_id = session_manager.create_session("Test Session")
    session_manager.save_exchange(
        session_id, "Tell me about machine learning", 
        "Machine learning is...", "test-model", "ja"
    )
    
    results = session_manager.search_sessions("machine learning")
    assert len(results) >= 1
    assert any(r["id"] == session_id for r in results)


def test_rename_session(session_manager):
    """Test renaming a session."""
    session_id = session_manager.create_session("Old Name")
    renamed = session_manager.rename_session(session_id, "New Name")
    assert renamed is True
    
    loaded = session_manager.load_session(session_id)
    assert loaded["name"] == "New Name"


def test_rename_session_updates_timestamp(session_manager):
    """Test that renaming updates the updated_at timestamp."""
    import time
    session_id = session_manager.create_session("Test")
    loaded1 = session_manager.load_session(session_id)
    timestamp1 = loaded1["updated_at"]
    
    time.sleep(0.1)
    session_manager.rename_session(session_id, "Renamed")
    
    loaded2 = session_manager.load_session(session_id)
    timestamp2 = loaded2["updated_at"]
    assert timestamp2 > timestamp1


# ============================================================================
# V2 Schema: Tag Management Tests
# ============================================================================

def test_update_session_tags(session_manager):
    """Test updating session tags."""
    session_id = session_manager.create_session("Test", tags=["old"])
    result = session_manager.update_session_tags(session_id, ["new", "tags"])
    assert result is True
    
    loaded = session_manager.load_session(session_id)
    assert loaded["tags"] == ["new", "tags"]


def test_get_all_tags_aggregation(session_manager):
    """Test getting all unique tags across sessions."""
    session_manager.create_session("S1", tags=["AI", "Python"])
    session_manager.create_session("S2", tags=["Python", "Web"])
    session_manager.create_session("S3", tags=["AI", "ML"])
    
    all_tags = session_manager.get_all_tags()
    assert set(all_tags) == {"AI", "ML", "Python", "Web"}
    assert all_tags == sorted(all_tags)


def test_list_sessions_with_tag_filter(session_manager):
    """Test filtering sessions by tags (AND logic)."""
    id1 = session_manager.create_session("S1", tags=["AI", "Python"])
    id2 = session_manager.create_session("S2", tags=["Web"])
    id3 = session_manager.create_session("S3", tags=["AI", "ML"])
    
    sessions = session_manager.list_sessions(tags=["AI"])
    assert len(sessions) == 2
    assert set(s["id"] for s in sessions) == {id1, id3}


def test_list_sessions_with_date_range_filter(session_manager):
    """Test filtering sessions by date range."""
    id1 = session_manager.create_session("S1")
    id2 = session_manager.create_session("S2")
    
    with sqlite3.connect(session_manager.db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("UPDATE sessions SET created_at = ? WHERE id = ?", ("2025-01-15", id1))
        conn.execute("UPDATE sessions SET created_at = ? WHERE id = ?", ("2025-02-20", id2))
        conn.commit()
    
    sessions = session_manager.list_sessions(date_from="2025-02-01", date_to="2025-02-28")
    assert len(sessions) == 1
    assert sessions[0]["id"] == id2


def test_list_sessions_returns_exchange_count(session_manager):
    """Test that list_sessions returns exchange_count field."""
    id1 = session_manager.create_session("S1")
    id2 = session_manager.create_session("S2")
    
    session_manager.save_exchange(id1, "Q1", "A1", "test-model", "ja")
    session_manager.save_exchange(id1, "Q2", "A2", "test-model", "ja")
    session_manager.save_exchange(id2, "Q1", "A1", "test-model", "ja")
    
    sessions = session_manager.list_sessions()
    session1 = next(s for s in sessions if s["id"] == id1)
    session2 = next(s for s in sessions if s["id"] == id2)
    
    assert session1["exchange_count"] == 2
    assert session2["exchange_count"] == 1


# ============================================================================
# V2 Schema: Exchange with search_results and evaluation_score
# ============================================================================

def test_save_exchange_with_search_results(session_manager):
    """Test saving exchange with search_results."""
    session_id = session_manager.create_session("Test")
    search_results = [{"title": "Python Tutorial", "url": "https://example.com"}]
    
    exchange_id = session_manager.save_exchange(
        session_id, "Q", "A", "test-model", "ja", search_results=search_results
    )
    assert exchange_id is not None
    
    loaded = session_manager.load_session(session_id)
    assert loaded["exchanges"][0]["search_results"] == search_results


def test_save_exchange_with_evaluation_score(session_manager):
    """Test saving exchange with evaluation_score."""
    session_id = session_manager.create_session("Test")
    eval_score = {"accuracy": 0.9, "overall": 0.875}
    
    exchange_id = session_manager.save_exchange(
        session_id, "Q", "A", "test-model", "ja", evaluation_score=eval_score
    )
    assert exchange_id is not None
    
    loaded = session_manager.load_session(session_id)
    assert loaded["exchanges"][0]["evaluation_score"] == eval_score


def test_save_exchange_updates_session_timestamp(session_manager):
    """Test that saving exchange updates session updated_at."""
    import time
    session_id = session_manager.create_session("Test")
    loaded1 = session_manager.load_session(session_id)
    timestamp1 = loaded1["updated_at"]
    
    time.sleep(0.1)
    session_manager.save_exchange(session_id, "Q", "A", "test-model", "ja")
    
    loaded2 = session_manager.load_session(session_id)
    timestamp2 = loaded2["updated_at"]
    assert timestamp2 > timestamp1


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_error_handling_invalid_session_id(session_manager):
    """Test error handling for non-existent session ID."""
    loaded = session_manager.load_session(99999)
    assert loaded is None
    
    deleted = session_manager.delete_session(99999)
    assert deleted is True


def test_empty_session_list(session_manager):
    """Test listing when no sessions exist."""
    sessions = session_manager.list_sessions()
    assert sessions == []


def test_load_session_with_malformed_tags_json(session_manager):
    """Test loading session with malformed tags JSON."""
    session_id = session_manager.create_session("Test")
    
    with sqlite3.connect(session_manager.db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("UPDATE sessions SET tags = ? WHERE id = ?", ("invalid json", session_id))
        conn.commit()
    
    loaded = session_manager.load_session(session_id)
    assert loaded is not None
    assert loaded["tags"] == []


# ============================================================================
# Schema Version Tests
# ============================================================================

def test_session_manager_requires_v2_schema(temp_db_path):
    """Test that SessionManager raises error for outdated schema."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT NOT NULL
            )
        """)
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.commit()
    
    with pytest.raises(RuntimeError, match="outdated.*version 1"):
        SessionManager(db_path=temp_db_path)


def test_session_manager_requires_schema_version_table(temp_db_path):
    """Test that SessionManager raises error if schema_version table missing."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY)")
        conn.commit()
    
    with pytest.raises(RuntimeError, match="Schema version table not found"):
        SessionManager(db_path=temp_db_path)
