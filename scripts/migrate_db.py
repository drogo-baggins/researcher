#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データベースマイグレーションスクリプト（バージョン管理対応）

使用方法:
    python migrate_db.py                    # 通常のマイグレーション実行
    python migrate_db.py --show-version     # 現在のバージョンを表示
    python migrate_db.py --verify-only      # スキーマ検証のみ
    python migrate_db.py --dry-run          # ドライラン
    python migrate_db.py --db-path <path>   # 特定のデータベースパスを指定

スキーマバージョン:
    - Version 1: 初期スキーマ（session_groups, sessions with group_id/search_results/tags）
    - Version 2以降: 次のフェーズで実装予定

新しいマイグレーションの追加方法（開発者向け）:
    1. migrate_to_vN(conn) 関数を作成
    2. verify_schema_vN(conn) 関数を作成（オプション）
    3. run_migrations() 内の MIGRATIONS リストに追加
"""

import argparse
import json
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger(__name__)


def ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """
    schema_versionテーブルを作成（存在しない場合）
    
    Args:
        conn: SQLite接続
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL
        )
    """)


def get_current_schema_version(conn: sqlite3.Connection) -> int:
    """
    現在のスキーマバージョンを取得
    
    Args:
        conn: SQLite接続
    
    Returns:
        現在のバージョン番号（未初期化の場合は0）
    """
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()[0]
        return result if result is not None else 0
    except sqlite3.OperationalError:
        # schema_versionテーブルが存在しない
        return 0


def set_schema_version(conn: sqlite3.Connection, version: int, description: str) -> None:
    """
    スキーマバージョンを記録
    
    Args:
        conn: SQLite接続
        version: バージョン番号
        description: マイグレーションの説明
    """
    conn.execute(
        "INSERT INTO schema_version (version, description) VALUES (?, ?)",
        (version, description)
    )


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """
    カラムが存在するか確認
    
    Args:
        conn: SQLite接続
        table: テーブル名
        column: カラム名
    
    Returns:
        存在する場合True
    """
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    return column in columns


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """
    テーブルが存在するか確認
    
    Args:
        conn: SQLite接続
        table: テーブル名
    
    Returns:
        存在する場合True
    """
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def migrate_to_v1(conn: sqlite3.Connection) -> None:
    """
    バージョン1へのマイグレーション（初期スキーマ確立）
    
    Creates:
        - session_groups table
        - sessions table with group_id, search_results, last_evaluation_score, tags columns
        - Default group (id=1)
    
    Args:
        conn: SQLite接続
    """
    LOGGER.info("Applying migration to version 1...")
    
    # session_groupsテーブル作成
    LOGGER.info("  Creating session_groups table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # sessionsテーブル作成
    LOGGER.info("  Creating sessions table...")
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
    
    # group_idカラム追加（存在しない場合）
    if not column_exists(conn, "sessions", "group_id"):
        LOGGER.info("  Adding group_id column...")
        conn.execute("ALTER TABLE sessions ADD COLUMN group_id INTEGER")
    else:
        LOGGER.info("  group_id column already exists")
    
    # search_resultsカラム追加（存在しない場合）
    if not column_exists(conn, "sessions", "search_results"):
        LOGGER.info("  Adding search_results column...")
        conn.execute("ALTER TABLE sessions ADD COLUMN search_results TEXT")
    else:
        LOGGER.info("  search_results column already exists")
    
    # last_evaluation_scoreカラム追加（存在しない場合）
    if not column_exists(conn, "sessions", "last_evaluation_score"):
        LOGGER.info("  Adding last_evaluation_score column...")
        conn.execute("ALTER TABLE sessions ADD COLUMN last_evaluation_score TEXT")
    else:
        LOGGER.info("  last_evaluation_score column already exists")
    
    # tagsカラム追加（存在しない場合）
    if not column_exists(conn, "sessions", "tags"):
        LOGGER.info("  Adding tags column...")
        conn.execute("ALTER TABLE sessions ADD COLUMN tags TEXT")
    else:
        LOGGER.info("  tags column already exists")
    
    # デフォルトグループ作成
    cursor = conn.execute("SELECT COUNT(*) FROM session_groups WHERE id = 1")
    if cursor.fetchone()[0] == 0:
        LOGGER.info("  Creating default group (id=1)...")
        conn.execute(
            "INSERT INTO session_groups (id, title) VALUES (1, ?)",
            ("デフォルト",)
        )
    else:
        LOGGER.info("  Default group already exists")
    
    # NULL group_idを持つセッションをデフォルトグループに割り当て
    cursor = conn.execute("SELECT COUNT(*) FROM sessions WHERE group_id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        LOGGER.info(f"  Assigning {null_count} sessions to default group...")
        conn.execute("UPDATE sessions SET group_id = 1 WHERE group_id IS NULL")
    
    LOGGER.info("Migration to version 1 completed successfully")


def verify_schema_v1(conn: sqlite3.Connection) -> bool:
    """
    バージョン1のスキーマを検証
    
    Args:
        conn: SQLite接続
    
    Returns:
        検証が成功した場合True
    """
    LOGGER.info("Verifying schema version 1...")
    
    # sessionsテーブルの必須カラム確認
    required_columns = {
        "id", "name", "history", "model", "language", 
        "group_id", "search_results", "last_evaluation_score", "tags",
        "created_at", "updated_at"
    }
    
    cursor = conn.execute("PRAGMA table_info(sessions)")
    sessions_columns = {col[1] for col in cursor.fetchall()}
    
    missing_columns = required_columns - sessions_columns
    if missing_columns:
        LOGGER.error(f"  ❌ Missing columns in sessions table: {missing_columns}")
        return False
    else:
        LOGGER.info(f"  ✅ All required columns present in sessions table")
    
    # session_groupsテーブルの存在確認
    if not table_exists(conn, "session_groups"):
        LOGGER.error(f"  ❌ session_groups table not found")
        return False
    else:
        LOGGER.info(f"  ✅ session_groups table exists")
    
    # デフォルトグループの存在確認
    cursor = conn.execute("SELECT COUNT(*) FROM session_groups WHERE id = 1")
    if cursor.fetchone()[0] == 0:
        LOGGER.error(f"  ❌ Default group (id=1) not found")
        return False
    else:
        LOGGER.info(f"  ✅ Default group exists")
    
    # NULL group_idのセッションがないことを確認
    cursor = conn.execute("SELECT COUNT(*) FROM sessions WHERE group_id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        LOGGER.warning(f"  ⚠️  {null_count} sessions with NULL group_id found")
        return False
    else:
        LOGGER.info(f"  ✅ No sessions with NULL group_id")
    
    LOGGER.info("Schema version 1 verification passed")
    return True


def migrate_to_v2(conn: sqlite3.Connection) -> None:
    """
    バージョン2へのマイグレーション（sessions/exchangesモデルへのリファクタリング）
    
    Changes:
        - Rename existing sessions table to exchanges_temp
        - Create new sessions table (id, name, tags, created_at, updated_at)
        - Create new exchanges table (id, session_id, user_message, assistant_message, ...)
        - Migrate data from exchanges_temp to new sessions and exchanges
        - Drop exchanges_temp and session_groups tables
        - Create indexes
    
    Args:
        conn: SQLite接続
    """
    LOGGER.info("Applying migration to version 2...")
    
    # 1. 既存sessionsテーブルをexchanges_tempにリネーム
    LOGGER.info("  Renaming sessions to exchanges_temp...")
    conn.execute("ALTER TABLE sessions RENAME TO exchanges_temp")
    
    # 2. 新しいsessionsテーブルを作成
    LOGGER.info("  Creating new sessions table...")
    conn.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. 新しいexchangesテーブルを作成
    LOGGER.info("  Creating new exchanges table...")
    conn.execute("""
        CREATE TABLE exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT NOT NULL,
            model TEXT NOT NULL,
            language TEXT NOT NULL,
            search_results TEXT,
            evaluation_score TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 4. データ移行
    LOGGER.info("  Migrating data from exchanges_temp to new schema...")
    cursor = conn.execute("SELECT id, name, history, model, language, tags, search_results, last_evaluation_score, created_at, updated_at FROM exchanges_temp")
    old_sessions = cursor.fetchall()
    
    LOGGER.info(f"  Processing {len(old_sessions)} sessions...")
    
    total_exchanges = 0
    skipped_sessions = 0
    
    for old_id, name, history_json, model, language, tags_json, search_results_json, last_eval_json, created_at, updated_at in old_sessions:
        try:
            # 新sessionsレコード作成
            # tagsの処理（NULLまたは空文字列の場合は空配列）
            if tags_json:
                try:
                    tags_data = json.loads(tags_json)
                    if not isinstance(tags_data, list):
                        tags_data = []
                except (json.JSONDecodeError, TypeError):
                    LOGGER.warning(f"    Invalid tags JSON for session {old_id}, using empty array")
                    tags_data = []
            else:
                tags_data = []
            
            # 新sessionレコード挿入
            cursor = conn.execute(
                "INSERT INTO sessions (name, tags, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, json.dumps(tags_data), created_at, updated_at)
            )
            new_session_id = cursor.lastrowid
            
            # history配列の解析
            try:
                history = json.loads(history_json) if history_json else []
            except (json.JSONDecodeError, TypeError):
                LOGGER.warning(f"    Invalid history JSON for session {old_id}, skipping exchanges")
                history = []
            
            # user-assistantペアの抽出
            i = 0
            session_exchanges = 0
            while i < len(history):
                msg = history[i]
                
                # userメッセージを探す
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    
                    # 次のassistantメッセージを探す
                    if i + 1 < len(history) and history[i + 1].get("role") == "assistant":
                        assistant_msg = history[i + 1]
                        assistant_message = assistant_msg.get("content", "")
                        
                        # search_resultsの取得（assistantメッセージに埋め込まれている場合、または旧sessionのもの）
                        exchange_search_results = assistant_msg.get("search_results")
                        if exchange_search_results is None and search_results_json:
                            # 最後のexchangeのみ旧sessionのsearch_resultsを使用
                            if i + 2 >= len(history):  # これが最後のペアの場合
                                try:
                                    exchange_search_results = json.loads(search_results_json) if search_results_json else None
                                except (json.JSONDecodeError, TypeError):
                                    LOGGER.warning(f"    Invalid search_results JSON for session {old_id}, using None")
                                    exchange_search_results = None
                        
                        # evaluation_scoreの取得
                        evaluation = assistant_msg.get("evaluation")
                        if evaluation is None and last_eval_json:
                            # 最後のexchangeのみ旧sessionのlast_evaluation_scoreを使用
                            if i + 2 >= len(history):
                                try:
                                    evaluation = json.loads(last_eval_json) if last_eval_json else None
                                except (json.JSONDecodeError, TypeError):
                                    evaluation = None
                        
                        # exchangeレコード挿入
                        conn.execute(
                            """INSERT INTO exchanges 
                               (session_id, user_message, assistant_message, model, language, 
                                search_results, evaluation_score, created_at) 
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                new_session_id,
                                user_message,
                                assistant_message,
                                model,
                                language,
                                json.dumps(exchange_search_results) if exchange_search_results is not None else None,
                                json.dumps(evaluation) if evaluation is not None else None,
                                created_at
                            )
                        )
                        session_exchanges += 1
                        i += 2  # user + assistant をスキップ
                    else:
                        # 不完全なペア（assistantがない）はスキップ
                        LOGGER.warning(f"    Incomplete exchange in session {old_id} at index {i}, skipping")
                        i += 1
                else:
                    # userメッセージでない場合はスキップ
                    i += 1
            
            total_exchanges += session_exchanges
            if session_exchanges == 0 and len(history) > 0:
                skipped_sessions += 1
                LOGGER.warning(f"    Session {old_id} has history but no complete exchanges")
            
        except Exception as e:
            LOGGER.error(f"    Failed to migrate session {old_id}: {e}", exc_info=True)
            raise
    
    LOGGER.info(f"  Created {len(old_sessions)} sessions and {total_exchanges} exchanges")
    if skipped_sessions > 0:
        LOGGER.warning(f"  {skipped_sessions} sessions had history but no complete exchanges")
    
    # 5. クリーンアップ
    LOGGER.info("  Dropping exchanges_temp table...")
    conn.execute("DROP TABLE exchanges_temp")
    
    LOGGER.info("  Dropping session_groups table...")
    conn.execute("DROP TABLE IF EXISTS session_groups")
    
    # 6. インデックス作成
    LOGGER.info("  Creating indexes...")
    conn.execute("CREATE INDEX idx_exchanges_session_id ON exchanges(session_id)")
    conn.execute("CREATE INDEX idx_sessions_tags ON sessions(tags)")
    
    LOGGER.info("Migration to version 2 completed successfully")


def verify_schema_v2(conn: sqlite3.Connection) -> bool:
    """
    バージョン2のスキーマを検証
    
    Args:
        conn: SQLite接続
    
    Returns:
        検証が成功した場合True
    """
    LOGGER.info("Verifying schema version 2...")
    
    # 2.1 スキーマ検証
    
    # sessionsテーブルの必須カラム確認
    required_sessions_columns = {"id", "name", "tags", "created_at", "updated_at"}
    cursor = conn.execute("PRAGMA table_info(sessions)")
    sessions_columns = {col[1] for col in cursor.fetchall()}
    
    missing_columns = required_sessions_columns - sessions_columns
    if missing_columns:
        LOGGER.error(f"  ❌ Missing columns in sessions table: {missing_columns}")
        return False
    else:
        LOGGER.info(f"  ✅ All required columns present in sessions table")
    
    # exchangesテーブルの必須カラム確認
    required_exchanges_columns = {
        "id", "session_id", "user_message", "assistant_message", 
        "model", "language", "search_results", "evaluation_score", "created_at"
    }
    cursor = conn.execute("PRAGMA table_info(exchanges)")
    exchanges_columns = {col[1] for col in cursor.fetchall()}
    
    missing_columns = required_exchanges_columns - exchanges_columns
    if missing_columns:
        LOGGER.error(f"  ❌ Missing columns in exchanges table: {missing_columns}")
        return False
    else:
        LOGGER.info(f"  ✅ All required columns present in exchanges table")
    
    # session_groupsテーブルが存在しないことを確認
    if table_exists(conn, "session_groups"):
        LOGGER.error(f"  ❌ session_groups table should not exist in v2")
        return False
    else:
        LOGGER.info(f"  ✅ session_groups table removed")
    
    # 2.2 データ整合性検証
    
    # 外部キー制約の確認（全exchangesのsession_idが有効か）
    cursor = conn.execute("""
        SELECT COUNT(*) FROM exchanges e
        LEFT JOIN sessions s ON e.session_id = s.id
        WHERE s.id IS NULL
    """)
    orphaned_exchanges = cursor.fetchone()[0]
    if orphaned_exchanges > 0:
        LOGGER.error(f"  ❌ {orphaned_exchanges} exchanges have invalid session_id")
        return False
    else:
        LOGGER.info(f"  ✅ All exchanges have valid session_id")
    
    # 孤立したsessions（exchangeが0件）のカウント
    cursor = conn.execute("""
        SELECT COUNT(*) FROM sessions s
        LEFT JOIN exchanges e ON s.id = e.session_id
        WHERE e.id IS NULL
    """)
    orphaned_sessions = cursor.fetchone()[0]
    if orphaned_sessions > 0:
        LOGGER.warning(f"  ⚠️  {orphaned_sessions} sessions have no exchanges")
    else:
        LOGGER.info(f"  ✅ All sessions have at least one exchange")
    
    # JSON形式の検証（サンプル）
    cursor = conn.execute("SELECT COUNT(*) FROM sessions WHERE tags IS NOT NULL")
    total_sessions_with_tags = cursor.fetchone()[0]
    
    invalid_tags_count = 0
    if total_sessions_with_tags > 0:
        cursor = conn.execute("SELECT id, tags FROM sessions WHERE tags IS NOT NULL LIMIT 100")
        for session_id, tags_json in cursor.fetchall():
            try:
                tags = json.loads(tags_json)
                if not isinstance(tags, list):
                    invalid_tags_count += 1
            except (json.JSONDecodeError, TypeError):
                invalid_tags_count += 1
        
        if invalid_tags_count > 0:
            LOGGER.warning(f"  ⚠️  Found {invalid_tags_count} sessions with invalid tags JSON (sampled 100)")
        else:
            LOGGER.info(f"  ✅ Tags JSON format valid (sampled)")
    
    # search_results JSON検証（サンプル）
    cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE search_results IS NOT NULL")
    total_exchanges_with_search = cursor.fetchone()[0]
    
    invalid_search_count = 0
    if total_exchanges_with_search > 0:
        sample_size = min(100, total_exchanges_with_search)
        cursor = conn.execute(f"SELECT id, search_results FROM exchanges WHERE search_results IS NOT NULL LIMIT {sample_size}")
        for exchange_id, search_json in cursor.fetchall():
            try:
                json.loads(search_json)
            except (json.JSONDecodeError, TypeError):
                invalid_search_count += 1
        
        if invalid_search_count > 0:
            LOGGER.warning(f"  ⚠️  Found {invalid_search_count} exchanges with invalid search_results JSON (sampled {sample_size})")
        else:
            LOGGER.info(f"  ✅ Search results JSON format valid (sampled)")
    
    # evaluation_score JSON検証（サンプル）
    cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE evaluation_score IS NOT NULL")
    total_exchanges_with_eval = cursor.fetchone()[0]
    
    invalid_eval_count = 0
    if total_exchanges_with_eval > 0:
        sample_size = min(100, total_exchanges_with_eval)
        cursor = conn.execute(f"SELECT id, evaluation_score FROM exchanges WHERE evaluation_score IS NOT NULL LIMIT {sample_size}")
        for exchange_id, eval_json in cursor.fetchall():
            try:
                json.loads(eval_json)
            except (json.JSONDecodeError, TypeError):
                invalid_eval_count += 1
        
        if invalid_eval_count > 0:
            LOGGER.warning(f"  ⚠️  Found {invalid_eval_count} exchanges with invalid evaluation_score JSON (sampled {sample_size})")
        else:
            LOGGER.info(f"  ✅ Evaluation score JSON format valid (sampled)")
    
    # 2.3 統計情報表示
    cursor = conn.execute("SELECT COUNT(*) FROM sessions")
    sessions_count = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM exchanges")
    exchanges_count = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM sessions WHERE tags IS NOT NULL AND tags != '[]'")
    sessions_with_tags = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE search_results IS NOT NULL")
    exchanges_with_search = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE evaluation_score IS NOT NULL")
    exchanges_with_eval = cursor.fetchone()[0]
    
    LOGGER.info(f"\n  📊 Statistics:")
    LOGGER.info(f"     Total sessions: {sessions_count}")
    LOGGER.info(f"     Total exchanges: {exchanges_count}")
    LOGGER.info(f"     Sessions with tags: {sessions_with_tags}")
    LOGGER.info(f"     Exchanges with search results: {exchanges_with_search}")
    LOGGER.info(f"     Exchanges with evaluation scores: {exchanges_with_eval}")
    
    if orphaned_sessions > 0:
        LOGGER.info(f"     Sessions with no exchanges: {orphaned_sessions}")
    
    LOGGER.info("Schema version 2 verification passed")
    return True


def create_backup(db_path: Path, current_version: int) -> Optional[Path]:
    """
    データベースのバックアップを作成
    
    Args:
        db_path: データベースパス
        current_version: 現在のバージョン
    
    Returns:
        バックアップファイルのパス（失敗時はNone）
    """
    try:
        # バックアップディレクトリの作成
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # バックアップファイル名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"sessions.db.backup_v{current_version}_{timestamp}"
        
        # コピー
        shutil.copy2(db_path, backup_path)
        LOGGER.info(f"Backup created: {backup_path}")
        
        return backup_path
    except Exception as e:
        LOGGER.error(f"Failed to create backup: {e}")
        return None


def run_migrations(db_path: Path, dry_run: bool = False) -> bool:
    """
    マイグレーションを実行
    
    Args:
        db_path: データベースパス
        dry_run: ドライランモード（実際には変更しない）
    
    Returns:
        成功時True
    """
    # データベースが存在しない場合は新規作成
    is_new_db = not db_path.exists()
    backup_path_for_rollback = None
    
    try:
        with sqlite3.connect(db_path) as conn:
            # schema_versionテーブルを確保
            ensure_schema_version_table(conn)
            
            # 現在のバージョン取得
            current_version = get_current_schema_version(conn)
            LOGGER.info(f"Current schema version: {current_version}")
            
            # バックアップ作成（新規DBでない場合）
            if not is_new_db and not dry_run and current_version < 1:
                backup_path_for_rollback = create_backup(db_path, current_version)
                if backup_path_for_rollback is None:
                    LOGGER.error("Backup creation failed. Aborting migration.")
                    return False
            
            # マイグレーション定義
            MIGRATIONS = [
                (1, "Initial schema with session_groups and sessions", migrate_to_v1, verify_schema_v1),
                (2, "Refactor to sessions/exchanges model, remove session_groups", migrate_to_v2, verify_schema_v2),
            ]
            
            # 未適用のマイグレーションを実行
            migrations_applied = 0
            for version, description, migrate_func, verify_func in MIGRATIONS:
                if version > current_version:
                    LOGGER.info(f"Applying migration: Version {version} - {description}")
                    
                    # Version 2への移行時に追加のバックアップを作成（破壊的変更のため）
                    # current_versionを追跡しているため、v0→v2一括適用でも正しく動作
                    if not is_new_db and not dry_run and version == 2 and current_version < 2:
                        backup_path_for_rollback = create_backup(db_path, current_version)
                        if backup_path_for_rollback is None:
                            LOGGER.error("Backup creation failed. Aborting migration to v2.")
                            return False
                        LOGGER.info(f"Created backup before destructive migration to v2: {backup_path_for_rollback}")
                    
                    if dry_run:
                        LOGGER.info(f"  [DRY RUN] Would apply migration to version {version}")
                        
                        # Version 2のドライランで詳細情報を表示
                        if version == 2 and table_exists(conn, "sessions"):
                            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
                            session_count = cursor.fetchone()[0]
                            
                            cursor = conn.execute("""
                                SELECT COUNT(*) FROM sessions 
                                WHERE tags IS NOT NULL AND tags != '' AND tags != '[]'
                            """)
                            tagged_sessions = cursor.fetchone()[0]
                            
                            # 生成される予定のexchange数を推定
                            cursor = conn.execute("SELECT history FROM sessions")
                            total_estimated_exchanges = 0
                            for (history_json,) in cursor.fetchall():
                                try:
                                    history = json.loads(history_json) if history_json else []
                                    # user-assistantペアをカウント
                                    pairs = 0
                                    i = 0
                                    while i < len(history):
                                        if history[i].get("role") == "user" and i + 1 < len(history) and history[i + 1].get("role") == "assistant":
                                            pairs += 1
                                            i += 2
                                        else:
                                            i += 1
                                    total_estimated_exchanges += pairs
                                except:
                                    pass
                            
                            cursor = conn.execute("SELECT COUNT(*) FROM session_groups")
                            group_count = cursor.fetchone()[0]
                            
                            LOGGER.info(f"  [DRY RUN] Migration details for v2:")
                            LOGGER.info(f"    - Sessions to migrate: {session_count}")
                            LOGGER.info(f"    - Estimated exchanges to create: {total_estimated_exchanges}")
                            LOGGER.info(f"    - Sessions with tags: {tagged_sessions}")
                            LOGGER.info(f"    - Session groups to delete: {group_count}")
                            
                            # 推定実行時間（1セッションあたり約10ms）
                            estimated_time = (session_count * 10) / 1000
                            LOGGER.info(f"    - Estimated execution time: ~{estimated_time:.1f} seconds")
                    else:
                        try:
                            # トランザクション開始
                            conn.execute("BEGIN")
                            
                            # マイグレーション実行
                            migrate_func(conn)
                            
                            # バージョン記録
                            set_schema_version(conn, version, description)
                            
                            # 検証（オプション）
                            if verify_func and not verify_func(conn):
                                LOGGER.error(f"Schema verification failed for version {version}")
                                conn.execute("ROLLBACK")
                                if backup_path_for_rollback:
                                    LOGGER.error(f"You can restore from backup: {backup_path_for_rollback}")
                                return False
                            
                            # コミット
                            conn.execute("COMMIT")
                            LOGGER.info(f"Successfully applied migration to version {version}")
                            migrations_applied += 1
                            
                            # 現在のバージョンを更新（次のマイグレーションで参照される）
                            current_version = version
                            
                        except Exception as e:
                            LOGGER.error(f"Migration to version {version} failed: {e}", exc_info=True)
                            conn.execute("ROLLBACK")
                            if backup_path_for_rollback:
                                LOGGER.error(f"Migration rolled back. You can restore from backup: {backup_path_for_rollback}")
                            return False
            
            # 結果レポート
            if migrations_applied == 0:
                LOGGER.info("✅ Database is already up to date (no migrations needed)")
            else:
                LOGGER.info(f"✅ Successfully applied {migrations_applied} migration(s)")
            
            # 統計情報表示
            if table_exists(conn, "sessions"):
                cursor = conn.execute("SELECT COUNT(*) FROM sessions")
                session_count = cursor.fetchone()[0]
                LOGGER.info(f"   Total sessions: {session_count}")
            
            if table_exists(conn, "exchanges"):
                cursor = conn.execute("SELECT COUNT(*) FROM exchanges")
                exchange_count = cursor.fetchone()[0]
                LOGGER.info(f"   Total exchanges: {exchange_count}")
            
            if table_exists(conn, "session_groups"):
                cursor = conn.execute("SELECT COUNT(*) FROM session_groups")
                group_count = cursor.fetchone()[0]
                LOGGER.info(f"   Total groups: {group_count}")
            
            return True
            
    except Exception as e:
        LOGGER.error(f"Migration failed: {e}", exc_info=True)
        return False


def show_version(db_path: Path) -> None:
    """
    現在のスキーマバージョンを表示
    
    Args:
        db_path: データベースパス
    """
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            ensure_schema_version_table(conn)
            version = get_current_schema_version(conn)
            
            print(f"Database: {db_path}")
            print(f"Current schema version: {version}")
            
            # バージョン履歴表示
            cursor = conn.execute(
                "SELECT version, applied_at, description FROM schema_version ORDER BY version"
            )
            rows = cursor.fetchall()
            
            if rows:
                print("\nMigration history:")
                for ver, applied_at, desc in rows:
                    print(f"  Version {ver}: {desc} (applied at {applied_at})")
            else:
                print("\nNo migrations applied yet")
                
    except Exception as e:
        LOGGER.error(f"Failed to show version: {e}")


def verify_only(db_path: Path) -> bool:
    """
    スキーマ検証のみ実行
    
    Args:
        db_path: データベースパス
    
    Returns:
        検証が成功した場合True
    """
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            ensure_schema_version_table(conn)
            version = get_current_schema_version(conn)
            
            print(f"Current schema version: {version}")
            
            # バージョンに応じた検証
            if version == 1:
                return verify_schema_v1(conn)
            elif version == 2:
                return verify_schema_v2(conn)
            elif version == 0:
                print("Schema not initialized (version 0)")
                return False
            else:
                print(f"Unknown schema version: {version}")
                return False
                
    except Exception as e:
        LOGGER.error(f"Verification failed: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Database migration tool with version control"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path.home() / ".researcher" / "sessions.db",
        help="Path to database file (default: ~/.researcher/sessions.db)"
    )
    parser.add_argument(
        "--show-version",
        action="store_true",
        help="Show current schema version"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify schema without applying migrations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    # コマンド実行
    if args.show_version:
        show_version(args.db_path)
    elif args.verify_only:
        success = verify_only(args.db_path)
        sys.exit(0 if success else 1)
    else:
        success = run_migrations(args.db_path, dry_run=args.dry_run)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
