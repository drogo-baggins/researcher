"""
SQLite-based session management for Researcher WebUI.

This module provides persistent storage of chat sessions using SQLite.
Sessions store conversation history, model settings, and language preferences.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

LOGGER = logging.getLogger(__name__)


class SessionManager:
    """Manage persistent chat sessions using SQLite."""

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
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        history TEXT NOT NULL,
                        model TEXT NOT NULL,
                        language TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to initialize database: {e}")

    def create_session(self, name: str, model: str, language: str) -> Optional[int]:
        """Create a new session.

        Args:
            name: Session name
            model: Ollama model name
            language: Language setting ('ja' or 'en')

        Returns:
            Session ID if successful, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO sessions (name, history, model, language)
                    VALUES (?, ?, ?, ?)
                    """,
                    (name, json.dumps([]), model, language),
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to create session: {e}")
            return None

    def save_session(
        self, session_id: int, history: List[Dict], model: str, language: str
    ) -> bool:
        """Save session with updated history and settings.

        Args:
            session_id: Session ID to update
            history: List of message dicts
            model: Ollama model name
            language: Language setting

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE sessions
                    SET history = ?, model = ?, language = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(history), model, language, session_id),
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to save session {session_id}: {e}")
            return False

    def load_session(self, session_id: int) -> Optional[Dict]:
        """Load a session by ID.

        Args:
            session_id: Session ID to load

        Returns:
            Session dict with parsed history, or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    return None
                
                # Parse history JSON
                try:
                    history = json.loads(row["history"])
                except json.JSONDecodeError:
                    LOGGER.warning(f"Failed to parse history for session {session_id}")
                    history = []
                
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "history": history,
                    "model": row["model"],
                    "language": row["language"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to load session {session_id}: {e}")
            return None

    def list_sessions(self) -> List[Dict]:
        """List all sessions ordered by updated_at (newest first).

        Returns:
            List of session dicts (without history for brevity)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT id, name, model, language, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
                )
                return [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "model": row["model"],
                        "language": row["language"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to list sessions: {e}")
            return []

    def delete_session(self, session_id: int) -> bool:
        """Delete a session by ID.

        Args:
            session_id: Session ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to delete session {session_id}: {e}")
            return False

    def search_sessions(self, query: str) -> List[Dict]:
        """Search sessions by name or history content.

        Args:
            query: Search query string

        Returns:
            List of matching session dicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                # Search in name or history (case-insensitive)
                cursor = conn.execute(
                    """
                    SELECT id, name, model, language, created_at, updated_at
                    FROM sessions
                    WHERE LOWER(name) LIKE LOWER(?) OR LOWER(history) LIKE LOWER(?)
                    ORDER BY updated_at DESC
                    """,
                    (f"%{query}%", f"%{query}%"),
                )
                return [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "model": row["model"],
                        "language": row["language"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to search sessions: {e}")
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
                conn.execute(
                    "UPDATE sessions SET name = ? WHERE id = ?",
                    (new_name, session_id),
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            LOGGER.warning(f"Failed to rename session {session_id}: {e}")
            return False
