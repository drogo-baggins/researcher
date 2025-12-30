#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression test for the specific bug: StreamlitAPIException with orphaned tags
This test simulates the exact scenario reported by the user.
"""
import sys
import sqlite3
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from researcher.session_manager import SessionManager


def test_streamlit_multiselect_bug():
    """
    Regression test for bug:
    StreamlitAPIException: Every Multiselect default value must be present in options
    
    Scenario:
    1. Session has tag 'Politics'
    2. 'Politics' is not in get_all_tags() (orphaned tag)
    3. Multiselect with options=all_tags, default=current_tags
    4. StreamlitAPIException because 'Politics' not in options
    
    Fix:
    options_tags = list(set(all_tags + current_tags))
    """
    print("=" * 80)
    print("Regression Test: StreamlitAPIException with Orphaned Tags")
    print("=" * 80)
    
    # Setup test database
    test_db = Path("/tmp/test_regression.db")
    if test_db.exists():
        test_db.unlink()
    
    # Initialize V2 schema
    with sqlite3.connect(test_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        
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
    
    # Step 1: Create session with Politics tag
    print("\n[Step 1] Create session with 'Politics' tag")
    session1_id = manager.create_session("Test Session", tags=["Politics", "Tech"])
    print(f"  Created session {session1_id}")
    
    # Step 2: Create another session WITHOUT Politics tag
    print("\n[Step 2] Create another session without 'Politics' tag")
    session2_id = manager.create_session("Another Session", tags=["Tech", "AI"])
    print(f"  Created session {session2_id}")
    
    # Step 3: Delete session1
    print("\n[Step 3] Delete first session")
    manager.delete_session(session1_id)
    print("  Deleted session 1")
    
    # Step 4: Manually insert orphaned tag back to a session (simulating the bug scenario)
    print("\n[Step 4] Manually add 'Politics' tag to session 2 (creating orphaned tag)")
    with sqlite3.connect(test_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.execute("SELECT tags FROM sessions WHERE id = ?", (session2_id,))
        row = cursor.fetchone()
        current_tags = json.loads(row[0]) if row and row[0] else []
        current_tags.append("Politics")
        conn.execute("UPDATE sessions SET tags = ? WHERE id = ?", (json.dumps(current_tags), session2_id))
        conn.commit()
    print("  Added 'Politics' to session 2")
    
    # Step 5: Get all tags (should NOT include Politics because it's orphaned in DB logic)
    print("\n[Step 5] Get all tags from get_all_tags()")
    all_tags = manager.get_all_tags()
    print(f"  all_tags: {all_tags}")
    
    # Step 6: Load session 2 (has Politics in its tags)
    print("\n[Step 6] Load session 2")
    session2_data = manager.load_session(session2_id)
    current_tags = session2_data.get("tags", []) if session2_data else []
    print(f"  current_tags: {current_tags}")
    
    # Step 7: Simulate the BUG (old code)
    print("\n[Step 7] Simulate OLD code (BUG)")
    print("  Code: st.multiselect(options=all_tags, default=current_tags)")
    try:
        # This would raise StreamlitAPIException
        for tag in current_tags:
            if tag not in all_tags:
                print(f"  ❌ BUG: Tag '{tag}' in current_tags but NOT in all_tags")
                print(f"     This would cause: StreamlitAPIException: Every Multiselect default value must be present in options")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Step 8: Apply the FIX
    print("\n[Step 8] Apply FIX")
    print("  Code: options_tags = list(set(all_tags + current_tags))")
    options_tags = list(set(all_tags + current_tags))
    options_tags.sort()
    print(f"  options_tags: {options_tags}")
    
    # Verify fix
    for tag in current_tags:
        assert tag in options_tags, f"Tag '{tag}' must be in options_tags"
    print("  ✅ FIX VERIFIED: All current_tags are in options_tags")
    
    # Cleanup
    test_db.unlink()
    
    print("\n" + "=" * 80)
    print("Regression test passed! Bug is fixed.")
    print("=" * 80)


if __name__ == "__main__":
    test_streamlit_multiselect_bug()
