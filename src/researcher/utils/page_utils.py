"""
Shared utility functions for Streamlit multipage application.

This module provides common functionality used across multiple pages,
including session initialization, session loading, and state synchronization.
"""

import copy
import logging
import streamlit as st
from researcher.chat_manager import ChatManager
from researcher.citation_manager import CitationManager
from researcher.agent import QueryAgent
from researcher.ollama_client import OllamaClient
from researcher.searxng_client import SearXNGClient
from researcher.web_crawler import WebCrawler
from researcher.reranker import EmbeddingReranker
from researcher.session_manager import SessionManager
from researcher.config import (
    get_searxng_url,
    get_embedding_model,
    get_relevance_threshold,
    ensure_ollama_running,
    ensure_searxng_running,
)

LOGGER = logging.getLogger(__name__)


def get_usage_guide_markdown() -> str:
    """
    Get the usage guide markdown content shared across Chat and History pages.
    
    Returns:
        str: Markdown string for usage guide expander
    """
    return """
**履歴閲覧モード**

- 🔍 キーワード、日付、タグでフィルタ
- 🏷️ タグの追加・編集
- 📄 セッション詳細の表示
- 💬 セッションを選択して続行

**新規会話は Chatページで**

- 💬 新しい会話の開始
- 🏷️ タグによる整理
"""


def start_new_conversation() -> bool:
    """
    新規会話を開始（状態をクリア）
    
    Returns:
        bool: 成功時True、失敗時False
    """
    try:
        # Backup for logging
        backup_session_id = st.session_state.get("current_session_id")
        backup_message_count = len(st.session_state.get("messages", []))
        
        LOGGER.info(
            f"Starting new conversation: "
            f"current_session_id={backup_session_id}, "
            f"message_count={backup_message_count}"
        )
        
        # Clear UI state
        st.session_state.messages = []
        st.session_state.current_session_id = None
        st.session_state.current_session_name = None
        st.session_state.message_display_limit = None
        st.session_state.pending_tags = []  # Clear pending tags
        
        # Clear ChatManager state
        if "chat_manager" in st.session_state:
            st.session_state.chat_manager.clear_history(keep_system=True, clear_citations=True)
        
        LOGGER.info("New conversation started successfully")
        return True
    
    except Exception as e:
        LOGGER.error(f"Failed to start new conversation: {e}", exc_info=True)
        return False


def initialize_session_history():
    """
    Initialize session state for History Mode (read-only).
    
    History Mode only requires SessionManager for DB queries.
    No ChatManager, Ollama, or SearXNG initialization needed.
    This provides fast page load times.
    """
    if "history_initialized" in st.session_state and st.session_state.history_initialized:
        # Already initialized, skip
        return
    
    # Initialize SessionManager for persistence
    if "session_manager" not in st.session_state:
        st.session_state.session_manager = SessionManager()
    
    st.session_state.history_initialized = True
    LOGGER.info("History Mode initialized successfully (SessionManager only)")


def initialize_session_chat():
    """
    Initialize session state for Chat Mode (interactive).
    
    Chat Mode requires full initialization including ChatManager,
    Ollama, and SearXNG for conversation functionality.
    
    Optimized: Heavy connection tests only run on first initialization.
    Subsequent page switches reuse existing clients for faster loading.
    """
    if "chat_initialized" in st.session_state and st.session_state.chat_initialized:
        # Already initialized, skip
        return
    
    # Initialize SessionManager for persistence
    if "session_manager" not in st.session_state:
        st.session_state.session_manager = SessionManager()
    
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    
    # Check if this is the first initialization
    is_first_init = not st.session_state.get("chat_first_init", False)
    
    if is_first_init:
        # First initialization: Run heavy connection tests
        LOGGER.info("First Chat initialization: Running full connection tests")
        
        # Ensure services are running
        try:
            if not ensure_ollama_running():
                st.error("❌ Ollamaサーバーを起動できません。`ollama serve` を実行してください。")
                st.stop()
        except Exception as e:
            st.error(f"❌ Ollamaサーバーに接続できません: {e}")
            st.stop()
        
        # Initialize SearXNG (optional)
        try:
            ensure_searxng_running()
        except Exception as e:
            st.warning(f"⚠️ SearXNGの起動に失敗しました: {e}")
        
        # Initialize Ollama client
        model = st.session_state.get("model", "gpt-oss:20b")
        try:
            ollama_client = OllamaClient(model=model)
            if not ollama_client.test_connection():
                st.error("❌ Ollamaモデルが正しく応答しません。モデル名を確認してください。")
                st.stop()
        except Exception as e:
            st.error(f"❌ Ollama初期化エラー: {e}")
            st.stop()
        
        # Cache available models
        try:
            available_models = ollama_client.list_models()
            st.session_state.available_models = available_models if available_models else []
        except Exception as e:
            st.warning(f"⚠️ モデルリスト取得失敗: {e}")
            st.session_state.available_models = []
        
        # Initialize SearXNG client (optional)
        searxng_client = None
        try:
            searxng_url = get_searxng_url(None)
            candidate = SearXNGClient(searxng_url)
            if candidate.test_connection():
                searxng_client = candidate
                st.session_state._searxng_available = True
            else:
                st.session_state._searxng_available = False
        except Exception as e:
            st.warning(f"⚠️ SearXNG接続失敗: {e}")
            st.session_state._searxng_available = False
        
        # Set first init flag
        st.session_state.chat_first_init = True
        LOGGER.info("First Chat initialization completed")
    else:
        # Subsequent initializations: Reuse existing clients (fast path)
        LOGGER.info("Chat re-initialization: Reusing existing clients (skipping connection tests)")
        
        # Reuse existing Ollama client from ChatManager
        if "chat_manager" in st.session_state:
            ollama_client = st.session_state.chat_manager.ollama_client
            searxng_client = st.session_state.chat_manager.searxng_client
        else:
            # Fallback: Create new clients without connection tests
            model = st.session_state.get("model", "gpt-oss:20b")
            ollama_client = OllamaClient(model=model)
            
            searxng_client = None
            if st.session_state.get("_searxng_available", False):
                try:
                    searxng_url = get_searxng_url(None)
                    searxng_client = SearXNGClient(searxng_url)
                except Exception as e:
                    LOGGER.warning(f"SearXNG client creation failed: {e}")
                    searxng_client = None
    
    # Initialize other components
    embedding_model = get_embedding_model(None)
    threshold = get_relevance_threshold(None)
    reranker = EmbeddingReranker(ollama_client, model=embedding_model, threshold=threshold)
    
    citation_manager = CitationManager()
    web_crawler = WebCrawler() if searxng_client else None
    
    language = st.session_state.get("language", "ja")
    agent = QueryAgent(ollama_client, language=language) if searxng_client else None
    
    # Create ChatManager
    if "chat_manager" not in st.session_state:
        chat_manager = ChatManager(
            ollama_client=ollama_client,
            searxng_client=searxng_client,
            agent=agent,
            reranker=reranker,
            mcp_client=None,
            citation_manager=citation_manager,
            web_crawler=web_crawler,
            language=language,
            enable_self_evaluation=True,
        )
        chat_manager.add_system_message("You are a helpful assistant.")
        st.session_state.chat_manager = chat_manager
    
    # Store in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "model" not in st.session_state:
        st.session_state.model = model
    
    if "language" not in st.session_state:
        st.session_state.language = language
    
    if "auto_search" not in st.session_state:
        st.session_state.auto_search = True
    
    st.session_state.chat_initialized = True
    LOGGER.info("Chat Mode initialized successfully")


def initialize_session():
    """
    Legacy initialization function for backward compatibility.
    Defaults to Chat Mode initialization.
    
    Deprecated: Use initialize_session_chat() or initialize_session_history() instead.
    """
    initialize_session_chat()


def load_session_helper(session_id: int, session_name: str, trigger_rerun: bool = True) -> None:
    """
    セッションをロードしてUI状態を更新する共有ヘルパー関数
    
    Args:
        session_id: ロードするセッションID
        session_name: ロードするセッション名
        trigger_rerun: セッションロード後にst.rerun()を発火するか (デフォルト: True)
    """
    # Step 1: Function start trace
    current_session_id = st.session_state.get("current_session_id")
    current_messages_count = len(st.session_state.get("messages", []))
    LOGGER.info(
        f"[TRACE] load_session_helper started: session_id={session_id}, "
        f"session_name={session_name}, trigger_rerun={trigger_rerun}, "
        f"current_state=(session_id={current_session_id}, messages={current_messages_count})"
    )
    
    # Step 2: Backup current state before clearing
    try:
        backup_messages = copy.deepcopy(st.session_state.get("messages", []))
        backup_chat_messages = copy.deepcopy(st.session_state.chat_manager.messages)
        backup_session_id = st.session_state.get("current_session_id")
        backup_session_name = st.session_state.get("current_session_name")
        LOGGER.debug(
            f"[TRACE] Creating backup: messages={len(backup_messages)}, "
            f"chat_messages={len(backup_chat_messages)}"
        )
    except Exception as e:
        LOGGER.warning(f"[TRACE] deepcopy failed for backup, using shallow copy: {e}")
        backup_messages = list(st.session_state.get("messages", []))
        backup_chat_messages = list(st.session_state.chat_manager.messages)
        backup_session_id = st.session_state.get("current_session_id")
        backup_session_name = st.session_state.get("current_session_name")
    
    # Step 3: Clear ChatManager state before loading to avoid stale data
    LOGGER.info(f"[TRACE] Clearing ChatManager state before load")
    try:
        st.session_state.chat_manager.clear_history(keep_system=True, clear_citations=True)
        LOGGER.info(f"[TRACE] ChatManager cleared successfully")
    except Exception as e:
        LOGGER.error(f"[TRACE] ChatManager clear failed: {e}", exc_info=True)
        st.error("セッションロード前の状態クリアに失敗しました")
        # Restore backup
        st.session_state.messages = backup_messages
        st.session_state.chat_manager.messages = backup_chat_messages
        return
    
    # Step 4: Load session with enhanced error handling
    LOGGER.info(f"[TRACE] Loading session from database: session_id={session_id}")
    try:
        session_data = st.session_state.session_manager.load_session(session_id)
        LOGGER.info(f"[TRACE] Session loaded successfully: session_id={session_id}")
    except Exception as e:
        LOGGER.error(f"[TRACE] Session load exception: {e}", exc_info=True)
        st.error(f"セッションのロードに失敗しました (ID: {session_id}): {e}")
        # Restore backup to keep UI and ChatManager consistent
        st.session_state.messages = backup_messages
        st.session_state.chat_manager.messages = backup_chat_messages
        st.session_state.current_session_id = backup_session_id
        st.session_state.current_session_name = backup_session_name
        return
    
    if session_data is None:
        LOGGER.error(f"[TRACE] Session load returned None: session_id={session_id}")
        st.error(f"セッションが見つかりません (ID: {session_id})")
        # Restore backup to keep UI and ChatManager consistent
        st.session_state.messages = backup_messages
        st.session_state.chat_manager.messages = backup_chat_messages
        st.session_state.current_session_id = backup_session_id
        st.session_state.current_session_name = backup_session_name
        return
    
    # Step 5: Extract data from V2 schema (exchanges-based)
    LOGGER.info(f"[TRACE] Extracting session data: session_id={session_id}")
    try:
        # Extract session metadata
        tags = session_data.get("tags", [])
        exchanges = session_data.get("exchanges", [])
        
        # Reconstruct messages from exchanges (alternating user/assistant)
        messages = []
        model = None  # Will be set from first exchange
        language = None  # Will be set from first exchange
        last_evaluation_score = None  # Will be set from last exchange
        
        for exchange in exchanges:
            # User message
            messages.append({
                "role": "user",
                "content": exchange["user_message"]
            })
            
            # Assistant message with search_results and evaluation_score
            assistant_msg = {
                "role": "assistant",
                "content": exchange["assistant_message"]
            }
            
            # Attach search_results if present
            if exchange.get("search_results") is not None:
                assistant_msg["search_results"] = exchange["search_results"]
            
            # Attach evaluation_score if present (set both keys for compatibility)
            if exchange.get("evaluation_score") is not None:
                assistant_msg["evaluation_score"] = exchange["evaluation_score"]
                assistant_msg["evaluation"] = exchange["evaluation_score"]  # For display compatibility
                last_evaluation_score = exchange["evaluation_score"]
            
            messages.append(assistant_msg)
            
            # Set model/language from first exchange (fallback to defaults)
            if model is None:
                model = exchange.get("model", "gpt-oss:20b")
            if language is None:
                language = exchange.get("language", "ja")
        
        # Fallback to defaults if no exchanges
        if model is None:
            model = "gpt-oss:20b"
        if language is None:
            language = "ja"
        
        # Log extracted data details
        LOGGER.debug(f"[TRACE] exchanges: {len(exchanges)} exchanges")
        LOGGER.debug(f"[TRACE] reconstructed messages: {len(messages)} messages")
        LOGGER.debug(f"[TRACE] tags: {tags if tags else 'None'}")
        LOGGER.debug(f"[TRACE] model: {model}, language: {language}")
        
        LOGGER.info(
            f"Loaded session {session_id}: {len(exchanges)} exchanges, "
            f"{len(messages)} messages"
        )
    except Exception as e:
        LOGGER.error(f"[TRACE] Failed to extract session data: {e}", exc_info=True)
        # Dump session_data for debugging
        try:
            import json
            session_data_dump = json.dumps(session_data, indent=2, default=str)
            LOGGER.error(f"[DEBUG] Session data dump:\n{session_data_dump}")
        except Exception as dump_error:
            LOGGER.error(f"[DEBUG] Failed to dump session_data: {dump_error}")
            LOGGER.error(
                f"[DEBUG] Session data keys: "
                f"{list(session_data.keys()) if session_data else 'None'}"
            )
        
        st.error(f"セッションデータの解析に失敗しました: {e}")
        # Restore backup to keep UI and ChatManager consistent
        st.session_state.messages = backup_messages
        st.session_state.chat_manager.messages = backup_chat_messages
        st.session_state.current_session_id = backup_session_id
        st.session_state.current_session_name = backup_session_name
        return
    
    # Step 7: Update session state
    LOGGER.info(
        f"[TRACE] Updating session_state: session_id={session_id}, "
        f"messages={len(messages)}"
    )
    st.session_state.current_session_id = session_id
    st.session_state.current_session_name = session_name
    st.session_state.messages = messages
    st.session_state.model = model
    st.session_state.language = language
    
    # Step 8: Sync ChatManager with deep-copied messages
    LOGGER.info(f"[TRACE] Syncing ChatManager with session data")
    try:
        # Try deepcopy first, fall back to direct assignment on failure
        try:
            st.session_state.chat_manager.messages = copy.deepcopy(messages)
            LOGGER.debug(f"[TRACE] deepcopy successful for ChatManager messages")
        except Exception as e:
            LOGGER.warning(
                f"[TRACE] deepcopy failed for ChatManager, using direct assignment: {e}"
            )
            st.session_state.chat_manager.messages = messages
        
        st.session_state.chat_manager.language = language
        st.session_state.chat_manager.ollama_client.model = model
        st.session_state.chat_manager.reranker.ollama_client.model = model
        
        # Restore evaluation score
        if last_evaluation_score:
            st.session_state.chat_manager.last_evaluation_score = last_evaluation_score
        else:
            st.session_state.chat_manager.last_evaluation_score = None
        
        # Update agent language if available
        if st.session_state.chat_manager.agent:
            st.session_state.chat_manager.agent.language = language
        
        LOGGER.info(f"[TRACE] ChatManager synced successfully: {len(messages)} messages")
    except Exception as e:
        LOGGER.error(f"[TRACE] Failed to sync ChatManager: {e}", exc_info=True)
        # Dump relevant state for debugging
        try:
            import json
            debug_info = {
                "session_id": session_id,
                "messages_count": len(messages),
                "chat_manager_messages_count": len(st.session_state.chat_manager.messages),
                "model": model,
                "language": language
            }
            LOGGER.error(f"[DEBUG] ChatManager sync debug info:\n{json.dumps(debug_info, indent=2)}")
        except Exception as dump_error:
            LOGGER.error(f"[DEBUG] Failed to dump debug info: {dump_error}")
        
        st.error(f"ChatManagerの同期に失敗しました: {e}")
        # Restore backup to keep UI and ChatManager consistent
        st.session_state.messages = backup_messages
        st.session_state.chat_manager.messages = backup_chat_messages
        st.session_state.current_session_id = backup_session_id
        st.session_state.current_session_name = backup_session_name
        return
    
    # Step 9: Completion
    LOGGER.info(f"[TRACE] load_session_helper completed successfully: session_id={session_id}")
    
    if trigger_rerun:
        st.rerun()
