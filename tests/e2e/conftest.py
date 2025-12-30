"""
Playwright E2Eテスト用の共通フィクスチャ
"""
import pytest
import subprocess
import time
import logging
import sys
from pathlib import Path

# src/とscripts/をインポートパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "scripts"))
from migrate_db import run_migrations

LOGGER = logging.getLogger(__name__)

# Test constants
TEST_MODEL = "test-model"


def seed_test_database(db_path: Path):
    """テストデータベースにサンプルデータをシード"""
    from researcher.session_manager import SessionManager
    
    # マイグレーションを実行してスキーマを作成
    run_migrations(db_path)
    
    # SessionManagerを初期化
    session_manager = SessionManager(db_path=db_path)
    
    # セッションを作成（V2スキーマ: sessions/exchanges）
    session1_id = session_manager.create_session(
        name="Test Session 1",
        tags=["AI", "ニュース"]
    )
    
    # exchangeを保存
    session_manager.save_exchange(
        session_id=session1_id,
        user_message="最新のAIニュースは？",
        assistant_message="最新のAIニュースには以下のようなものがあります...",
        model=TEST_MODEL,
        language="ja",
        search_results=[
            {
                "title": "AI News Daily",
                "url": "https://ainewsdaily.com/article1",
                "snippet": "Latest developments in AI technology...",
                "citation_id": 1,
                "relevance_score": 0.92
            },
            {
                "title": "TechCrunch AI",
                "url": "https://techcrunch.com/ai/article2",
                "snippet": "New breakthrough in machine learning...",
                "citation_id": 2,
                "relevance_score": 0.89
            }
        ]
    )
    
    # 2つ目のセッションを作成（検索結果なし）
    session2_id = session_manager.create_session(
        name="Test Session 2",
        tags=["テスト"]
    )
    
    session_manager.save_exchange(
        session_id=session2_id,
        user_message="Hello",
        assistant_message="Hi there!",
        model=TEST_MODEL,
        language="en"
    )
    
    # 3つ目のセッションを作成
    session3_id = session_manager.create_session(
        name="Session 3",
        tags=["テスト"]
    )
    
    session_manager.save_exchange(
        session_id=session3_id,
        user_message="テスト",
        assistant_message="テストです",
        model=TEST_MODEL,
        language="ja"
    )
    
    LOGGER.info(f"Seeded test database with 3 sessions across 2 groups")


@pytest.fixture(scope="session")
def streamlit_app():
    """Streamlit WebUIを起動し、テスト終了後に停止"""
    # テスト用の一時データベースパスを設定
    test_db_path = Path(__file__).parent / "test_sessions.db"
    
    # 既存のテストDBをクリーンアップ
    if test_db_path.exists():
        test_db_path.unlink()
    
    # テストデータをシード
    seed_test_database(test_db_path)
    
    # Streamlit起動（Multipage構造: Home.pyがエントリーポイント）
    process = subprocess.Popen(
        [
            "streamlit", "run",
            "src/researcher/Home.py",
            "--server.port=8501",
            "--server.headless=true",
            "--",
            f"--db-path={test_db_path}"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # 起動待機（最大30秒）
    for _ in range(30):
        try:
            import requests
            response = requests.get("http://localhost:8501/_stcore/health")
            if response.status_code == 200:
                LOGGER.info("Streamlit app started successfully")
                break
        except:
            time.sleep(1)
    else:
        process.kill()
        raise RuntimeError("Streamlit app failed to start within 30 seconds")
    
    yield "http://localhost:8501"
    
    # 終了処理
    process.terminate()
    process.wait(timeout=5)
    
    # テストデータベースのクリーンアップ
    if test_db_path.exists():
        test_db_path.unlink()

@pytest.fixture
def page_with_db(playwright, streamlit_app):
    """Playwrightページオブジェクトを提供（テストDB使用版）"""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    # Streamlitアプリにアクセス
    page.goto(streamlit_app)
    
    # 初期ロード待機（ホームページのタイトルを待つ）
    page.wait_for_selector("text=🔍 Researcher", timeout=15000)
    
    yield page
    
    context.close()
    browser.close()

@pytest.fixture(scope="session")
def base_url():
    """実行中のStreamlitアプリのURLを提供（手動起動版）"""
    return "http://localhost:8501"

@pytest.fixture
def page(playwright, base_url):
    """Playwrightページオブジェクトを提供（手動起動版）"""
    browser = playwright.chromium.launch(headless=False)  # headless=False で動作確認
    context = browser.new_context()
    page_obj = context.new_page()
    
    # Streamlitアプリにアクセス
    page_obj.goto(base_url)
    
    # 初期ロード待機
    page_obj.wait_for_selector("text=🔍 Researcher", timeout=15000)
    
    yield page_obj
    
    context.close()
    browser.close()
