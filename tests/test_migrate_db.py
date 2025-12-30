"""
migrate_db.pyのマイグレーション機能をテストするユニットテスト
"""
import json
import pytest
import sqlite3
from pathlib import Path
from migrate_db import (
    run_migrations,
    get_current_schema_version,
    ensure_schema_version_table,
    table_exists,
    column_exists,
)


@pytest.fixture
def temp_migration_db(tmp_path):
    """テスト用の一時データベースパスを提供"""
    db_path = tmp_path / "test_migration.db"
    yield db_path
    # クリーンアップ
    if db_path.exists():
        db_path.unlink()


# ============================================================================
# V0 -> V1 Migration Tests
# ============================================================================

def test_v0_to_v1_migration_on_empty_db(temp_migration_db):
    """空のDBからのマイグレーションテスト（V1→V2が両方適用される）"""
    # 空DBに対してrun_migrationsを実行
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # 最終的にV2スキーマになる（V1, V2両方が適用される）
    with sqlite3.connect(temp_migration_db) as conn:
        # schema_versionが作成されている
        assert table_exists(conn, "schema_version")
        
        # バージョンが2
        version = get_current_schema_version(conn)
        assert version == 2
        
        # V2スキーマ: session_groupsは削除されている
        assert not table_exists(conn, "session_groups")
        
        # V2 sessionsテーブル構造
        assert column_exists(conn, "sessions", "id")
        assert column_exists(conn, "sessions", "name")
        assert column_exists(conn, "sessions", "tags")
        assert column_exists(conn, "sessions", "created_at")
        assert column_exists(conn, "sessions", "updated_at")
        
        # V1カラムは存在しない
        assert not column_exists(conn, "sessions", "history")
        assert not column_exists(conn, "sessions", "group_id")
        
        # exchangesテーブルが存在
        assert table_exists(conn, "exchanges")


def test_v0_to_v1_migration_with_existing_legacy_data(temp_migration_db):
    """既存のV0データがある場合のマイグレーションテスト（V1→V2が適用される）"""
    # V0スキーマを手動作成（旧バージョンのDB）
    with sqlite3.connect(temp_migration_db) as conn:
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # サンプルデータ挿入（完全なexchange）
        history = json.dumps([
            {"role": "user", "content": "test question"},
            {"role": "assistant", "content": "test answer"}
        ])
        conn.execute(
            "INSERT INTO sessions (name, history, model, language) VALUES (?, ?, ?, ?)",
            ("Test Session", history, "test-model", "ja")
        )
        conn.commit()
    
    # マイグレーション実行（V1→V2が適用される）
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # V2スキーマ検証
    with sqlite3.connect(temp_migration_db) as conn:
        # V2スキーマ構造
        assert column_exists(conn, "sessions", "id")
        assert column_exists(conn, "sessions", "name")
        assert column_exists(conn, "sessions", "tags")
        
        # V1カラムは存在しない
        assert not column_exists(conn, "sessions", "group_id")
        assert not column_exists(conn, "sessions", "history")
        
        # 既存データがexchangesに移行されている
        cursor = conn.execute("SELECT COUNT(*) FROM sessions")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE session_id = 1")
        assert cursor.fetchone()[0] == 1
        
        # 移行されたexchangeの内容確認
        cursor = conn.execute("SELECT user_message, assistant_message FROM exchanges WHERE session_id = 1")
        user_msg, asst_msg = cursor.fetchone()
        assert user_msg == "test question"
        assert asst_msg == "test answer"


# ============================================================================
# V1 -> V2 Migration Tests
# ============================================================================

def test_v1_to_v2_migration_with_sample_data(temp_migration_db):
    """V1からV2へのマイグレーションテスト（サンプルデータあり）"""
    # V1スキーマを作成
    with sqlite3.connect(temp_migration_db) as conn:
        ensure_schema_version_table(conn)
        
        # session_groupsテーブル作成
        conn.execute("""
            CREATE TABLE session_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL
            )
        """)
        conn.execute("INSERT INTO session_groups (id, title) VALUES (1, 'デフォルト')")
        
        # V1 sessionsテーブル作成
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                group_id INTEGER,
                search_results TEXT,
                last_evaluation_score TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # サンプルデータ挿入
        history = json.dumps([
            {"role": "user", "content": "こんにちは"},
            {"role": "assistant", "content": "はい、こんにちは！"}
        ])
        tags = json.dumps(["AI", "テスト"])
        search_results = json.dumps([{"title": "Test", "url": "https://example.com"}])
        eval_score = json.dumps({"accuracy": 0.9})
        
        conn.execute(
            """INSERT INTO sessions (name, history, model, language, group_id, search_results, last_evaluation_score, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Test Session", history, "test-model", "ja", 1, search_results, eval_score, tags)
        )
        
        # V1としてマーク
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.commit()
    
    # V2へマイグレーション
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # V2スキーマ検証
    with sqlite3.connect(temp_migration_db) as conn:
        # バージョン確認
        assert get_current_schema_version(conn) == 2
        
        # 新しいsessionsテーブル構造
        assert column_exists(conn, "sessions", "id")
        assert column_exists(conn, "sessions", "name")
        assert column_exists(conn, "sessions", "tags")
        assert column_exists(conn, "sessions", "created_at")
        assert column_exists(conn, "sessions", "updated_at")
        
        # 古いカラムが存在しない
        assert not column_exists(conn, "sessions", "history")
        assert not column_exists(conn, "sessions", "group_id")
        
        # exchangesテーブルが作成されている
        assert table_exists(conn, "exchanges")
        assert column_exists(conn, "exchanges", "id")
        assert column_exists(conn, "exchanges", "session_id")
        assert column_exists(conn, "exchanges", "user_message")
        assert column_exists(conn, "exchanges", "assistant_message")
        assert column_exists(conn, "exchanges", "model")
        assert column_exists(conn, "exchanges", "language")
        assert column_exists(conn, "exchanges", "search_results")
        assert column_exists(conn, "exchanges", "evaluation_score")
        assert column_exists(conn, "exchanges", "created_at")
        
        # session_groupsテーブルが削除されている
        assert not table_exists(conn, "session_groups")
        
        # データ移行確認
        cursor = conn.execute("SELECT COUNT(*) FROM sessions")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT COUNT(*) FROM exchanges")
        assert cursor.fetchone()[0] == 1
        
        # 移行されたデータの内容確認
        cursor = conn.execute("SELECT name, tags FROM sessions WHERE id = 1")
        name, tags_json = cursor.fetchone()
        assert name == "Test Session"
        assert json.loads(tags_json) == ["AI", "テスト"]
        
        cursor = conn.execute(
            "SELECT user_message, assistant_message, model, language, search_results, evaluation_score FROM exchanges WHERE session_id = 1"
        )
        user_msg, asst_msg, model, lang, sr_json, eval_json = cursor.fetchone()
        assert user_msg == "こんにちは"
        assert asst_msg == "はい、こんにちは！"
        assert model == "test-model"
        assert lang == "ja"
        assert json.loads(sr_json) == [{"title": "Test", "url": "https://example.com"}]
        assert json.loads(eval_json) == {"accuracy": 0.9}


def test_v1_to_v2_migration_with_multiple_exchanges(temp_migration_db):
    """V1からV2へのマイグレーション（複数exchangeを持つセッション）"""
    # V1スキーマ作成
    with sqlite3.connect(temp_migration_db) as conn:
        ensure_schema_version_table(conn)
        
        conn.execute("CREATE TABLE session_groups (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO session_groups (id, title) VALUES (1, 'デフォルト')")
        
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                group_id INTEGER,
                search_results TEXT,
                last_evaluation_score TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 複数のuser-assistantペアを持つhistory
        history = json.dumps([
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "A3"}
        ])
        
        conn.execute(
            "INSERT INTO sessions (name, history, model, language, group_id, tags) VALUES (?, ?, ?, ?, ?, ?)",
            ("Multi Exchange Session", history, "test-model", "ja", 1, json.dumps(["test"]))
        )
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.commit()
    
    # マイグレーション実行
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # 検証
    with sqlite3.connect(temp_migration_db) as conn:
        # 3つのexchangeが作成されている
        cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE session_id = 1")
        assert cursor.fetchone()[0] == 3
        
        # 各exchangeの内容確認
        cursor = conn.execute("SELECT user_message, assistant_message FROM exchanges WHERE session_id = 1 ORDER BY id")
        exchanges = cursor.fetchall()
        assert exchanges[0] == ("Q1", "A1")
        assert exchanges[1] == ("Q2", "A2")
        assert exchanges[2] == ("Q3", "A3")


def test_v1_to_v2_migration_with_incomplete_exchanges(temp_migration_db):
    """V1からV2へのマイグレーション（不完全なexchangeを含むhistory）"""
    # V1スキーマ作成
    with sqlite3.connect(temp_migration_db) as conn:
        ensure_schema_version_table(conn)
        
        conn.execute("CREATE TABLE session_groups (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO session_groups (id, title) VALUES (1, 'デフォルト')")
        
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                group_id INTEGER,
                search_results TEXT,
                last_evaluation_score TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 不完全なhistory（最後がuserメッセージのみ）
        history = json.dumps([
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"}  # assistantレスポンスがない
        ])
        
        conn.execute(
            "INSERT INTO sessions (name, history, model, language, group_id, tags) VALUES (?, ?, ?, ?, ?, ?)",
            ("Incomplete Session", history, "test-model", "ja", 1, "[]")
        )
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.commit()
    
    # マイグレーション実行
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # 検証: 完全なペアのみが移行される
    with sqlite3.connect(temp_migration_db) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE session_id = 1")
        assert cursor.fetchone()[0] == 1  # Q1-A1ペアのみ


# ============================================================================
# V0 -> V2 Direct Migration Tests
# ============================================================================

def test_v0_to_v2_direct_migration(temp_migration_db):
    """V0からV2への直接マイグレーション（V1をスキップ）"""
    # V0スキーマ作成（schema_versionなし、最小限のsessions）
    with sqlite3.connect(temp_migration_db) as conn:
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        history = json.dumps([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ])
        
        conn.execute(
            "INSERT INTO sessions (name, history, model, language) VALUES (?, ?, ?, ?)",
            ("Legacy Session", history, "test-model", "en")
        )
        conn.commit()
    
    # マイグレーション実行（V1, V2両方が適用されるはず）
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # V2スキーマ検証
    with sqlite3.connect(temp_migration_db) as conn:
        # 最終バージョンがV2
        assert get_current_schema_version(conn) == 2
        
        # V2スキーマ構造
        assert table_exists(conn, "sessions")
        assert table_exists(conn, "exchanges")
        assert not table_exists(conn, "session_groups")
        
        # データ移行確認
        cursor = conn.execute("SELECT COUNT(*) FROM sessions")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT COUNT(*) FROM exchanges")
        assert cursor.fetchone()[0] == 1
        
        # 移行データの内容
        cursor = conn.execute("SELECT user_message, assistant_message FROM exchanges WHERE session_id = 1")
        user_msg, asst_msg = cursor.fetchone()
        assert user_msg == "Hello"
        assert asst_msg == "Hi"


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

def test_migration_on_already_v2_db(temp_migration_db):
    """すでにV2のDBに対してマイグレーション実行（冪等性テスト）"""
    # V2スキーマ作成
    with sqlite3.connect(temp_migration_db) as conn:
        ensure_schema_version_table(conn)
        
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.execute("INSERT INTO schema_version (version, description) VALUES (2, 'V2')")
        conn.commit()
    
    # マイグレーション実行
    success = run_migrations(temp_migration_db)
    assert success is True  # エラーにならない
    
    # バージョンは変わらない
    with sqlite3.connect(temp_migration_db) as conn:
        assert get_current_schema_version(conn) == 2


def test_migration_with_malformed_tags_json(temp_migration_db):
    """不正なタグJSONを持つV1データのV2マイグレーション"""
    # V1スキーマ作成
    with sqlite3.connect(temp_migration_db) as conn:
        ensure_schema_version_table(conn)
        
        conn.execute("CREATE TABLE session_groups (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO session_groups (id, title) VALUES (1, 'デフォルト')")
        
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                group_id INTEGER,
                search_results TEXT,
                last_evaluation_score TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        history = json.dumps([{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}])
        
        # 不正なJSON
        conn.execute(
            "INSERT INTO sessions (name, history, model, language, group_id, tags) VALUES (?, ?, ?, ?, ?, ?)",
            ("Bad Tags Session", history, "test-model", "ja", 1, "invalid json")
        )
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.commit()
    
    # マイグレーション実行（エラーで失敗しない）
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # 空配列にフォールバック
    with sqlite3.connect(temp_migration_db) as conn:
        cursor = conn.execute("SELECT tags FROM sessions WHERE id = 1")
        tags_json = cursor.fetchone()[0]
        assert json.loads(tags_json) == []


def test_migration_with_empty_history(temp_migration_db):
    """空のhistoryを持つセッションのV2マイグレーション"""
    # V1スキーマ作成
    with sqlite3.connect(temp_migration_db) as conn:
        ensure_schema_version_table(conn)
        
        conn.execute("CREATE TABLE session_groups (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO session_groups (id, title) VALUES (1, 'デフォルト')")
        
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                group_id INTEGER,
                search_results TEXT,
                last_evaluation_score TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute(
            "INSERT INTO sessions (name, history, model, language, group_id, tags) VALUES (?, ?, ?, ?, ?, ?)",
            ("Empty History Session", json.dumps([]), "test-model", "ja", 1, "[]")
        )
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.commit()
    
    # マイグレーション実行
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # sessionは作成されるがexchangeは0件
    with sqlite3.connect(temp_migration_db) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM sessions")
        assert cursor.fetchone()[0] == 1
        
        cursor = conn.execute("SELECT COUNT(*) FROM exchanges WHERE session_id = 1")
        assert cursor.fetchone()[0] == 0


# ============================================================================
# SQL Syntax Error Regression Test
# ============================================================================

def test_v2_migration_drop_table_syntax(temp_migration_db):
    """V2マイグレーションのDROP TABLE構文が正しいことをテスト（回帰テスト）"""
    # V1スキーマ作成
    with sqlite3.connect(temp_migration_db) as conn:
        ensure_schema_version_table(conn)
        
        conn.execute("CREATE TABLE session_groups (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO session_groups (id, title) VALUES (1, 'デフォルト')")
        
        conn.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                history TEXT NOT NULL,
                model TEXT NOT NULL,
                language TEXT NOT NULL,
                group_id INTEGER,
                search_results TEXT,
                last_evaluation_score TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        history = json.dumps([{"role": "user", "content": "test"}, {"role": "assistant", "content": "response"}])
        conn.execute(
            "INSERT INTO sessions (name, history, model, language, group_id, tags) VALUES (?, ?, ?, ?, ?, ?)",
            ("Test", history, "test-model", "ja", 1, "[]")
        )
        conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'V1')")
        conn.commit()
    
    # マイグレーション実行（SQL構文エラーが発生しない）
    success = run_migrations(temp_migration_db)
    assert success is True
    
    # session_groupsテーブルが削除されている
    with sqlite3.connect(temp_migration_db) as conn:
        assert not table_exists(conn, "session_groups")
