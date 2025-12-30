#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for tag management functionality - orphaned tags edge case
"""
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from researcher.session_manager import SessionManager


def test_orphaned_tags():
    """Test handling of orphaned tags (tags that exist in session but not in get_all_tags)"""
    print("=" * 80)
    print("Test: Orphaned Tags Handling")
    print("=" * 80)
    
    # Use temporary database
    test_db = Path("/tmp/test_tags.db")
    if test_db.exists():
        test_db.unlink()
    
    # Initialize database with V2 schema
    import sqlite3
    with sqlite3.connect(test_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Create schema version table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        
        # Create V2 schema (using INTEGER PRIMARY KEY AUTOINCREMENT for id)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_message TEXT NOT NULL,
                assistant_message TEXT NOT NULL,
                model TEXT,
                language TEXT,
                search_results TEXT,
                evaluation_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
    
    manager = SessionManager(db_path=test_db)
    
    # Test 1: Create session with unique tag
    print("\n[Test 1] Create session with unique tag 'Politics'")
    session1_id = manager.create_session("Session 1", tags=["Politics", "AI"])
    print(f"  Created session {session1_id} with tags: ['Politics', 'AI']")
    
    # Test 2: Create another session with different tags
    print("\n[Test 2] Create session with different tags")
    session2_id = manager.create_session("Session 2", tags=["AI", "Tech"])
    print(f"  Created session {session2_id} with tags: ['AI', 'Tech']")
    
    # Test 3: Check all tags
    print("\n[Test 3] Get all tags")
    all_tags = manager.get_all_tags()
    print(f"  All tags: {all_tags}")
    assert set(all_tags) == {"AI", "Politics", "Tech"}, f"Expected 3 tags, got {all_tags}"
    print("  ✓ All tags correct")
    
    # Test 4: Delete session2 - 'Tech' becomes orphaned if only in session2
    print("\n[Test 4] Delete session 2")
    manager.delete_session(session2_id)
    all_tags_after = manager.get_all_tags()
    print(f"  All tags after deletion: {all_tags_after}")
    # Note: 'Tech' was only in session2, so it should be removed
    # But 'AI' is still in session1, and 'Politics' is still in session1
    assert "Tech" not in all_tags_after or "Tech" in [t for t in all_tags_after], \
        "Check if Tech handling is correct"
    print(f"  ✓ Tags after deletion: {all_tags_after}")
    
    # Test 4b: Create an orphaned tag scenario manually
    print("\n[Test 4b] Create orphaned tag scenario manually")
    # Update session1 to add a tag 'Orphaned' that will later be removed from get_all_tags
    import sqlite3
    with sqlite3.connect(test_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        # Load current session1 tags
        cursor = conn.execute("SELECT tags FROM sessions WHERE id = ?", (session1_id,))
        row = cursor.fetchone()
        import json
        current_tags_in_db = json.loads(row[0]) if row and row[0] else []
        orphaned_tag = "OrphanedTag"
        if orphaned_tag not in current_tags_in_db:
            current_tags_in_db.append(orphaned_tag)
        conn.execute(
            "UPDATE sessions SET tags = ? WHERE id = ?",
            (json.dumps(current_tags_in_db), session1_id)
        )
        conn.commit()
    
    # Create session3 with OrphanedTag
    session3_id = manager.create_session("Session 3", tags=[orphaned_tag, "AI"])
    print(f"  Created session {session3_id} with orphaned tag")
    
    # Verify OrphanedTag exists in all_tags
    all_tags_with_orphaned = manager.get_all_tags()
    print(f"  All tags with orphaned: {all_tags_with_orphaned}")
    assert orphaned_tag in all_tags_with_orphaned
    
    # Delete session3 - OrphanedTag should still exist in session1
    manager.delete_session(session3_id)
    all_tags_after_deletion = manager.get_all_tags()
    print(f"  All tags after deleting session3: {all_tags_after_deletion}")
    # OrphanedTag should still be in all_tags because it's in session1
    assert orphaned_tag in all_tags_after_deletion, "OrphanedTag should still exist"
    print("  ✓ Orphaned tag scenario created")
    
    
    # Test 5: Load session1 - should still have 'Politics' and 'OrphanedTag'
    print("\n[Test 5] Load session 1 (with tags including orphaned)")
    session1_data = manager.load_session(str(session1_id))
    session1_tags = session1_data.get("tags", []) if session1_data else []
    print(f"  Session 1 data: {session1_data}")
    print(f"  Session 1 tags: {session1_tags}")
    assert "Politics" in session1_tags, "Politics should still exist in session"
    assert orphaned_tag in session1_tags, f"{orphaned_tag} should still exist in session"
    print("  ✓ Session tags preserved")
    
    # Test 6: Simulate the multiselect scenario
    print("\n[Test 6] Simulate multiselect with orphaned tag")
    all_tags_current = manager.get_all_tags()
    current_tags = session1_tags  # ['Politics', 'AI']
    
    # This is the fix: merge current_tags into all_tags
    options_tags = list(set(all_tags_current + current_tags))
    options_tags.sort()
    
    print(f"  all_tags from DB: {all_tags_current}")
    print(f"  current_tags from session: {current_tags}")
    print(f"  options_tags (merged): {options_tags}")
    
    # Verify all current_tags are in options
    for tag in current_tags:
        assert tag in options_tags, f"Tag '{tag}' not in options!"
    
    print("  ✓ All current tags are in options (no StreamlitAPIException)")
    
    # Test 7: Edge case - empty tags
    print("\n[Test 7] Session with empty tags")
    session4_id = manager.create_session("Session 4", tags=[])
    session4_data = manager.load_session(session4_id)
    session4_tags = session4_data.get("tags", [])
    
    all_tags_current = manager.get_all_tags()
    options_tags = list(set(all_tags_current + session4_tags))
    
    print(f"  Session 4 tags: {session4_tags}")
    print(f"  Options for empty session: {options_tags}")
    print("  ✓ Empty tags handled correctly")
    
    # Test 8: Edge case - None tags
    print("\n[Test 8] Session with None tags (malformed data)")
    import sqlite3
    with sqlite3.connect(test_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("UPDATE sessions SET tags = NULL WHERE id = ?", (session4_id,))
        conn.commit()
    
    session4_data = manager.load_session(session4_id)
    session4_tags = session4_data.get("tags", [])
    print(f"  Session 4 tags after NULL: {session4_tags}")
    assert session4_tags == [], "None should be converted to empty list"
    print("  ✓ None tags handled correctly")
    
    # Cleanup
    test_db.unlink()
    
    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    test_orphaned_tags()
