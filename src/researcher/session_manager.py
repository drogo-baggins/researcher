"""
SQLite-based session management for Researcher WebUI.

This module provides persistent storage of chat sessions using SQLite.
Sessions are organized with exchanges (Q&A pairs) following the v2 schema.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

LOGGER = logging.getLogger(__name__)

# Maximum number of sessions to return per query (pagination support)
MAX_SESSIONS_PER_QUERY = 500


class SessionManager:
    """Manage persistent chat sessions using SQLite (v2 schema)."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize SessionManager with SQLite database.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.researcher/sessions.db
        """
        if db_path is None:
            db_path = Path.home() / ".researcher" / "sessions.db"
        
        self.db_path = Path(db_path)
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                # Check schema version
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
                )
                if cursor.fetchone() is None:
                    raise RuntimeError(
                        "Schema version table not found. "
                        "Please run migrate_db.py to initialize the database."
                    )
                
                cursor = conn.execute("SELECT MAX(version) FROM schema_version")
                current_version = cursor.fetchone()[0]
                if current_version is None or current_version < 2:
                    raise RuntimeError(
                        f"Database schema is outdated (version {current_version}). "
                        "Please run migrate_db.py to update to version 2."
                    )
                
                # Verify required tables exist
                required_tables = ["sessions", "exchanges"]
                for table in required_tables:
                    cursor = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError(
                            f"Required table '{table}' not found. "
                            "Please run migrate_db.py to initialize the database."
                        )
                
                LOGGER.info("Database schema verified (version 2)")
        except sqlite3.Error as e:
            LOGGER.error(f"Failed to initialize database: {e}")
            raise

    def create_session(self, name: str, tags: Optional[List[str]] = None) -> Optional[int]:
        """Create a new session.

        Args:
            name: Session name
            tags: Optional list of tag strings

        Returns:
            Session ID if successful, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                tags_json = json.dumps(tags if tags else [])
                cursor = conn.execute(
                    "INSERT INTO sessions (name, tags) VALUES (?, ?)",
                    (name, tags_json),
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to create session: {e}")
            return None

    def save_exchange(
        self,
        session_id: int,
        user_message: str,
        assistant_message: str,
        model: str,
        language: str,
        search_results: Optional[List[Dict]] = None,
        evaluation_score: Optional[Dict] = None
    ) -> Optional[int]:
        """Save a single exchange (Q&A) to a session.
        
        Args:
            session_id: Session ID to add exchange to
            user_message: User's question/message
            assistant_message: Assistant's response
            model: Ollama model name used
            language: Language setting ('ja' or 'en')
            search_results: Optional list of search results
            evaluation_score: Optional evaluation score dict
        
        Returns:
            Exchange ID if successful, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                # Begin transaction
                conn.execute("BEGIN")
                
                # Serialize JSON fields
                search_results_json = json.dumps(search_results) if search_results is not None else None
                evaluation_score_json = json.dumps(evaluation_score) if evaluation_score is not None else None
                
                # Insert exchange
                cursor = conn.execute(
                    """INSERT INTO exchanges 
                       (session_id, user_message, assistant_message, model, language, 
                        search_results, evaluation_score) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, user_message, assistant_message, model, language,
                     search_results_json, evaluation_score_json)
                )
                exchange_id = cursor.lastrowid
                
                # Update session's updated_at timestamp
                conn.execute(
                    "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (session_id,)
                )
                
                conn.commit()
                return exchange_id
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to save exchange for session {session_id}: {e}")
            return None

    def load_session(self, session_id: int) -> Optional[Dict]:
        """Load a session with all its exchanges.

        Args:
            session_id: Session ID to load

        Returns:
            Session dict with exchanges, or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.row_factory = sqlite3.Row
                
                # Load session
                cursor = conn.execute(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                )
                session_row = cursor.fetchone()
                
                if session_row is None:
                    return None
                
                # Parse tags
                tags = []
                if session_row["tags"]:
                    try:
                        tags = json.loads(session_row["tags"])
                    except json.JSONDecodeError:
                        LOGGER.warning(f"Failed to parse tags for session {session_id}")
                
                # Load exchanges
                cursor = conn.execute(
                    """SELECT * FROM exchanges 
                       WHERE session_id = ? 
                       ORDER BY created_at ASC""",
                    (session_id,)
                )
                exchange_rows = cursor.fetchall()
                
                exchanges = []
                for row in exchange_rows:
                    # Parse search_results
                    search_results = None
                    if row["search_results"]:
                        try:
                            search_results = json.loads(row["search_results"])
                        except json.JSONDecodeError:
                            LOGGER.warning(f"Failed to parse search_results for exchange {row['id']}")
                    
                    # Parse evaluation_score
                    evaluation_score = None
                    if row["evaluation_score"]:
                        try:
                            evaluation_score = json.loads(row["evaluation_score"])
                        except json.JSONDecodeError:
                            LOGGER.warning(f"Failed to parse evaluation_score for exchange {row['id']}")
                    
                    exchanges.append({
                        "id": row["id"],
                        "user_message": row["user_message"],
                        "assistant_message": row["assistant_message"],
                        "model": row["model"],
                        "language": row["language"],
                        "search_results": search_results,
                        "evaluation_score": evaluation_score,
                        "created_at": row["created_at"],
                    })
                
                return {
                    "id": session_row["id"],
                    "name": session_row["name"],
                    "tags": tags,
                    "exchanges": exchanges,
                    "created_at": session_row["created_at"],
                    "updated_at": session_row["updated_at"],
                }
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to load session {session_id}: {e}")
            return None

    def list_sessions(
        self, 
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict]:
        """List all sessions ordered by updated_at (newest first).

        Args:
            date_from: Optional start date for filtering (ISO format: "2025-01-01")
            date_to: Optional end date for filtering (ISO format: "2025-12-31")
            tags: Optional list of tags to filter by (AND logic)
            limit: Optional maximum number of sessions to return (default: MAX_SESSIONS_PER_QUERY)
            offset: Optional offset for pagination (default: 0)

        Returns:
            List of session dicts with exchange counts
        """
        if limit is None:
            limit = MAX_SESSIONS_PER_QUERY
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.row_factory = sqlite3.Row
                
                # Build dynamic WHERE clause
                where_clauses = []
                params = []
                
                if date_from is not None:
                    where_clauses.append("s.created_at >= ?")
                    params.append(date_from)
                
                if date_to is not None:
                    where_clauses.append("DATE(s.created_at) <= ?")
                    params.append(date_to)
                
                if tags:
                    for tag in tags:
                        where_clauses.append("s.tags LIKE ?")
                        params.append(f'%"{tag}"%')
                
                # Construct query with LEFT JOIN to get exchange counts
                query = """
                    SELECT 
                        s.id, 
                        s.name, 
                        s.tags, 
                        s.created_at, 
                        s.updated_at,
                        COUNT(e.id) as exchange_count
                    FROM sessions s
                    LEFT JOIN exchanges e ON s.id = e.session_id
                """
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                query += """
                    GROUP BY s.id, s.name, s.tags, s.created_at, s.updated_at
                    ORDER BY s.updated_at DESC
                    LIMIT ? OFFSET ?
                """
                
                params.extend([limit, offset])
                
                cursor = conn.execute(query, params)
                
                sessions = []
                for row in cursor.fetchall():
                    # Parse tags
                    tags_list = []
                    if row["tags"]:
                        try:
                            tags_list = json.loads(row["tags"])
                        except json.JSONDecodeError:
                            LOGGER.warning(f"Failed to parse tags for session {row['id']}")
                    
                    sessions.append({
                        "id": row["id"],
                        "name": row["name"],
                        "tags": tags_list,
                        "exchange_count": row["exchange_count"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    })
                
                return sessions
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to list sessions: {e}")
            return []

    def delete_session(self, session_id: int) -> bool:
        """Delete a session by ID.
        
        Note: Related exchanges will be automatically deleted if the database
        has ON DELETE CASCADE constraint on the exchanges.session_id foreign key.

        Args:
            session_id: Session ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to delete session {session_id}: {e}")
            return False

    def search_sessions(self, query: str) -> List[Dict]:
        """Search sessions by name, tags, or exchange message content.

        Args:
            query: Search query string

        Returns:
            List of matching session dicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.row_factory = sqlite3.Row
                # Search in session name, tags, and exchange messages (case-insensitive)
                cursor = conn.execute(
                    """
                    SELECT DISTINCT 
                        s.id, 
                        s.name, 
                        s.tags, 
                        s.created_at, 
                        s.updated_at
                    FROM sessions s
                    LEFT JOIN exchanges e ON s.id = e.session_id
                    WHERE LOWER(s.name) LIKE LOWER(?) 
                       OR LOWER(s.tags) LIKE LOWER(?)
                       OR LOWER(e.user_message) LIKE LOWER(?)
                       OR LOWER(e.assistant_message) LIKE LOWER(?)
                    ORDER BY s.updated_at DESC
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"),
                )
                
                sessions = []
                for row in cursor.fetchall():
                    # Parse tags
                    tags_list = []
                    if row["tags"]:
                        try:
                            tags_list = json.loads(row["tags"])
                        except json.JSONDecodeError:
                            LOGGER.warning(f"Failed to parse tags for session {row['id']}")
                    
                    sessions.append({
                        "id": row["id"],
                        "name": row["name"],
                        "tags": tags_list,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    })
                
                return sessions
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to search sessions: {e}")
            return []

    def update_session_tags(self, session_id: int, tags: List[str]) -> bool:
        """Update tags for a session.
        
        Args:
            session_id: Session ID to update
            tags: List of tag strings
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                tags_json = json.dumps(tags)
                conn.execute(
                    """UPDATE sessions 
                       SET tags = ?, updated_at = CURRENT_TIMESTAMP 
                       WHERE id = ?""",
                    (tags_json, session_id)
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to update tags for session {session_id}: {e}")
            return False

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all sessions.
        
        Returns:
            List of unique tag strings, sorted alphabetically
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                cursor = conn.execute(
                    "SELECT DISTINCT tags FROM sessions WHERE tags IS NOT NULL AND tags != '[]'"
                )
                
                # Parse tags from JSON arrays
                all_tags = set()
                for row in cursor.fetchall():
                    tags_str = row[0]
                    if tags_str:
                        try:
                            tags_list = json.loads(tags_str)
                            if isinstance(tags_list, list):
                                all_tags.update(tags_list)
                        except json.JSONDecodeError:
                            LOGGER.warning(f"Failed to parse tags: {tags_str}")
                
                return sorted(all_tags)
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to get all tags: {e}")
            return []

    def rename_session(self, session_id: int, new_name: str) -> bool:
        """Rename a session.

        Args:
            session_id: Session ID to rename
            new_name: New session name

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute(
                    "UPDATE sessions SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_name, session_id),
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to rename session {session_id}: {e}")
            return False
