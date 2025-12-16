"""
Streamlit WebUI for Researcher - A local AI research assistant powered by Ollama and SearXNG.

This module provides a web-based interface for the Researcher application,
leveraging the same backend components (ChatManager, OllamaClient, SearXNGClient, etc.)
as the CLI interface.
"""

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
    save_feedback,
    get_feedback_stats,
)

LOGGER = logging.getLogger(__name__)


def initialize_session():
    """Initialize session state with all required components on first access."""
    if "initialized" not in st.session_state:
        # Initialize SessionManager for persistence
        st.session_state.session_manager = SessionManager()
        st.session_state.current_session_id = None
        
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
        
        # Get available models for dynamic selection (Phase 3)
        available_models = ollama_client.list_models()
        st.session_state.available_models = available_models if available_models else []
        
        # Initialize SearXNG client (optional)
        searxng_client = None
        try:
            searxng_url = get_searxng_url(None)
            candidate = SearXNGClient(searxng_url)
            if candidate.test_connection():
                searxng_client = candidate
        except Exception as e:
            st.warning(f"⚠️ SearXNG接続失敗: {e}")
        
        # Initialize other components
        embedding_model = get_embedding_model(None)
        threshold = get_relevance_threshold(None)
        reranker = EmbeddingReranker(ollama_client, model=embedding_model, threshold=threshold)
        
        citation_manager = CitationManager()
        web_crawler = WebCrawler() if searxng_client else None
        
        language = st.session_state.get("language", "ja")
        agent = QueryAgent(ollama_client, language=language) if searxng_client else None
        
        # Create ChatManager
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
        
        # Store in session state
        st.session_state.chat_manager = chat_manager
        st.session_state.messages = []
        st.session_state.model = model
        st.session_state.language = language
        st.session_state.auto_search = st.session_state.get("auto_search", True)
        st.session_state.initialized = True


def render_sidebar():
    """Render the configuration sidebar with session management."""
    with st.sidebar:
        st.title("⚙️ 設定")
        
        # === Session Management Section ===
        st.subheader("💾 セッション")
        
        # Get current session state
        sessions = st.session_state.session_manager.list_sessions()
        session_options = {s["id"]: f"{s['name']} ({s['updated_at'][:10]})" for s in sessions}
        
        current_id = st.session_state.get("current_session_id")
        
        # Keep widget state in sync with current_session_id (Comment 1 step 1)
        if current_id is not None and current_id not in st.session_state.get("_widget_sync_done", {}):
            st.session_state["session_selector"] = current_id
            _widget_sync_done = st.session_state.get("_widget_sync_done", {})
            _widget_sync_done[current_id] = True
            st.session_state["_widget_sync_done"] = _widget_sync_done
        
        # Session selector
        session_ids = [None] + list(session_options.keys())
        session_labels = ["新規セッション"] + [session_options[sid] for sid in session_ids[1:]]
        
        current_index = 0
        if current_id is not None and current_id in session_options:
            try:
                current_index = session_ids.index(current_id)
            except ValueError:
                current_index = 0
        
        selected_id = st.selectbox(
            "セッション選択",
            options=session_ids,
            format_func=lambda x: session_labels[session_ids.index(x)],
            index=current_index,
            key="session_selector"
        )
        
        # Track the last loaded session to avoid unnecessary reloads (Comment 1 step 2)
        last_loaded_id = st.session_state.get("_last_loaded_session_id")
        
        # Handle session switch: load session if different from last loaded (Comment 1 step 2)
        if selected_id is not None and selected_id != last_loaded_id:
            # Load existing session
            session_data = st.session_state.session_manager.load_session(selected_id)
            if session_data:
                st.session_state.current_session_id = selected_id
                st.session_state.messages = session_data["history"]
                st.session_state.model = session_data["model"]
                st.session_state.language = session_data["language"]
                st.session_state["_last_loaded_session_id"] = selected_id
                
                # Sync ChatManager with loaded session configuration
                st.session_state.chat_manager.messages = session_data["history"]
                st.session_state.chat_manager.language = session_data["language"]
                st.session_state.chat_manager.ollama_client.model = session_data["model"]
                st.session_state.chat_manager.reranker.ollama_client.model = session_data["model"]
                
                # Recreate agent with loaded language if it exists
                if st.session_state.chat_manager.agent:
                    st.session_state.chat_manager.agent = QueryAgent(
                        st.session_state.chat_manager.ollama_client,
                        language=session_data["language"]
                    )
                
                st.rerun()
        elif selected_id is None and last_loaded_id is not None:
            # New session selected
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.session_state.chat_manager.clear_history(keep_system=True, clear_citations=True)
            st.session_state["_last_loaded_session_id"] = None
            st.rerun()
        
        # Session action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 新規", key="new_session_btn"):
                name = f"Session {len(sessions) + 1}"
                new_id = st.session_state.session_manager.create_session(
                    name, st.session_state.model, st.session_state.language
                )
                if new_id:
                    st.session_state.current_session_id = new_id
                    st.session_state.messages = []
                    # Clear ChatManager history while keeping system messages (Comment 2)
                    st.session_state.chat_manager.clear_history(keep_system=True, clear_citations=True)
                    st.rerun()
        
        with col2:
            if st.button("🗑️ 削除", disabled=(current_id is None), key="delete_session_btn"):
                # Capture deletion result and handle errors (Comment 3)
                deleted = st.session_state.session_manager.delete_session(current_id)
                if deleted:
                    st.session_state.current_session_id = None
                    st.session_state.messages = []
                    # Clear ChatManager history while keeping system messages (Comment 2)
                    st.session_state.chat_manager.clear_history(keep_system=True, clear_citations=True)
                    st.rerun()
                else:
                    # Show error if deletion failed (Comment 3)
                    st.error(f"セッション削除に失敗しました (ID: {current_id})")
                    LOGGER.warning(f"Failed to delete session {current_id}")
        
        # Session search
        search_query = st.text_input("🔍 セッション検索", placeholder="キーワードで検索...", key="session_search")
        if search_query:
            search_results = st.session_state.session_manager.search_sessions(search_query)
            if search_results:
                st.write(f"{len(search_results)}件見つかりました")
                for result in search_results[:5]:  # Show top 5
                    if st.button(f"📄 {result['name']}", key=f"search_{result['id']}"):
                        # Sync both current_session_id and session_selector widget (Comment 1 step 3)
                        st.session_state.current_session_id = result["id"]
                        st.session_state["session_selector"] = result["id"]
                        st.session_state["_last_loaded_session_id"] = None  # Force reload
                        st.rerun()
            else:
                st.info("検索結果なし")
        
        st.divider()
        
        # === Configuration Section ===
        st.subheader("🤖 モデル設定")
        
        # Dynamic model selection (Phase 3)
        available_models = st.session_state.get("available_models", [])
        current_model = st.session_state.get("model", "gpt-oss:20b")
        
        if available_models:
            # Add current model to list if not present (for custom/restored models)
            if current_model not in available_models:
                available_models = [current_model] + available_models
            
            model = st.selectbox(
                "Ollamaモデル",
                options=available_models,
                index=available_models.index(current_model),
                help="実行するOllamaモデルを選択",
                key="model_selector"
            )
        else:
            # Fallback to text input if model list retrieval failed
            st.warning("⚠️ モデル一覧の取得に失敗しました。手動入力してください。")
            model = st.text_input(
                "Ollamaモデル",
                value=current_model,
                help="実行するOllamaモデル名",
                key="model_input"
            )
        
        if model != st.session_state.get("model"):
            st.session_state.model = model
            st.session_state.chat_manager.ollama_client.model = model
            st.session_state.chat_manager.reranker.ollama_client.model = model
            st.rerun()
        
        # Language selection
        st.subheader("🌍 言語設定")
        language_option = st.selectbox(
            "言語 / Language",
            ["ja", "en"],
            index=0 if st.session_state.get("language", "ja") == "ja" else 1,
            format_func=lambda x: "日本語" if x == "ja" else "English",
            key="language_selector"
        )
        if language_option != st.session_state.get("language"):
            st.session_state.language = language_option
            st.session_state.chat_manager.language = language_option
            if st.session_state.chat_manager.agent:
                st.session_state.chat_manager.agent = QueryAgent(
                    st.session_state.chat_manager.ollama_client,
                    language=language_option
                )
            st.rerun()
        
        # Auto-search toggle
        st.subheader("🔍 検索設定")
        auto_search = st.checkbox(
            "自動検索を有効化",
            value=st.session_state.get("auto_search", True),
            help="最新情報が必要な質問を自動的に検索",
            key="auto_search_checkbox"
        )
        st.session_state.auto_search = auto_search and bool(st.session_state.chat_manager.searxng_client)
        
        # Connection status
        st.divider()
        st.subheader("🔌 接続ステータス")
        
        try:
            ollama_ok = st.session_state.chat_manager.ollama_client.test_connection()
            if ollama_ok:
                st.success("✓ Ollama接続OK")
            else:
                st.error("✗ Ollama接続失敗")
        except Exception:
            st.error("✗ Ollama接続失敗")
        
        if st.session_state.chat_manager.searxng_client:
            try:
                searxng_ok = st.session_state.chat_manager.searxng_client.test_connection()
                if searxng_ok:
                    st.success("✓ SearXNG接続OK")
                else:
                    st.error("✗ SearXNG接続失敗")
            except Exception:
                st.error("✗ SearXNG接続失敗")
        else:
            st.warning("- SearXNG未設定")
        
        # Feedback statistics
        st.divider()
        st.subheader("📊 品質指標")
        
        try:
            # Get overall stats
            stats = get_feedback_stats()
            if stats.get("total_count", 0) > 0:
                st.metric("👎率 (全モデル)", f"{stats.get('thumbs_down_rate', 0):.1%}")
                
                # Get current model stats
                current_model = st.session_state.chat_manager.get_current_model()
                if current_model in stats.get("by_model", {}):
                    model_stats = stats["by_model"][current_model]
                    st.metric(
                        f"👎率 ({current_model})",
                        f"{model_stats.get('thumbs_down_rate', 0):.1%}"
                    )
            else:
                st.info("フィードバックがまだありません")
            
            # Display last evaluation score if available
            st.divider()
            eval_score = st.session_state.chat_manager.get_last_evaluation_score()
            if eval_score:
                st.subheader("🤖 最後の評価スコア")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("正確性", f"{eval_score.get('accuracy_score', 0):.2f}")
                with col2:
                    st.metric("最新性", f"{eval_score.get('freshness_score', 0):.2f}")
                with col3:
                    st.metric("総合", f"{eval_score.get('overall_score', 0):.2f}")
                if eval_score.get('reasoning'):
                    st.caption(f"理由: {eval_score['reasoning']}")
        
        except Exception as e:
            st.warning(f"統計情報の読み込みに失敗: {e}")


def render_chat():
    """Render the main chat interface."""
    st.title("🔍 Researcher")
    st.markdown("*ローカルAIリサーチャー - Ollama + SearXNG*")
    
    # Display message history with feedback buttons for assistant messages
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # Add feedback buttons for assistant messages
            if msg["role"] == "assistant":
                # Find corresponding user message (previous message)
                user_msg_content = ""
                for prev_msg in reversed(st.session_state.messages[:idx]):
                    if prev_msg["role"] == "user":
                        user_msg_content = prev_msg["content"]
                        break
                
                # Create feedback button columns
                col1, col2, spacer = st.columns([1, 1, 10])
                with col1:
                    if st.button("👍", key=f"feedback_up_{idx}", help="この回答が良かった場合はクリック"):
                        model = st.session_state.chat_manager.get_current_model()
                        success = save_feedback(
                            user_msg_content,
                            msg["content"],
                            "up",
                            model,
                            st.session_state.current_session_id
                        )
                        if success:
                            st.success("フィードバックを保存しました ✓", icon="✅")
                        else:
                            st.error("フィードバック保存に失敗しました")
                
                with col2:
                    if st.button("👎", key=f"feedback_down_{idx}", help="この回答が悪かった場合はクリック"):
                        model = st.session_state.chat_manager.get_current_model()
                        success = save_feedback(
                            user_msg_content,
                            msg["content"],
                            "down",
                            model,
                            st.session_state.current_session_id
                        )
                        if success:
                            st.success("フィードバックを保存しました ✓", icon="✅")
                        else:
                            st.error("フィードバック保存に失敗しました")
    
    # User input
    if user_input := st.chat_input("質問を入力してください...", key="chat_input"):
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Auto-search if enabled
        if st.session_state.auto_search and st.session_state.chat_manager.searxng_client:
            with st.spinner("🔍 検索中..."):
                try:
                    auto_result = st.session_state.chat_manager.auto_search(user_input)
                    if auto_result.get("searched"):
                        with st.expander("📚 検索結果", expanded=False):
                            st.text(auto_result["formatted"])
                except Exception as e:
                    st.warning(f"自動検索に失敗: {e}")
        
        # Add user message to ChatManager
        st.session_state.chat_manager.add_user_message(user_input)
        
        # Generate response with streaming
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                for chunk in st.session_state.chat_manager.get_response_stream():
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
            except Exception as e:
                st.error(f"応答生成エラー: {e}")
                full_response = f"エラーが発生しました: {e}"
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        
        # Auto-save session
        if st.session_state.current_session_id is None:
            # Create new session on first message
            session_name = f"Session {user_input[:20]}..." if len(user_input) > 20 else user_input
            new_id = st.session_state.session_manager.create_session(
                session_name, st.session_state.model, st.session_state.language
            )
            if new_id:
                st.session_state.current_session_id = new_id
        
        # Save session
        if st.session_state.current_session_id is not None:
            st.session_state.session_manager.save_session(
                st.session_state.current_session_id,
                st.session_state.messages,
                st.session_state.model,
                st.session_state.language
            )


def render_citations():
    """Render citations in the sidebar if any exist."""
    chat_manager = st.session_state.chat_manager
    citation_ids = getattr(chat_manager, "current_citation_ids", [])
    
    if citation_ids:
        with st.sidebar:
            st.divider()
            st.subheader("📖 参照")
            
            for cid in citation_ids:
                citation = chat_manager.citation_manager.get_citation(cid)
                if citation:
                    with st.expander(f"[{cid}] {citation['title'][:50]}..."):
                        st.markdown(f"**URL**: {citation['url']}")
                        st.markdown(f"**信頼性**: {citation['credibility_score']:.2f}")
                        st.markdown(f"**スニペット**: {citation['snippet'][:200]}...")


def main():
    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="Researcher - Local AI Research Assistant",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling
    st.markdown("""
        <style>
        .stChatMessage {
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session
    initialize_session()
    
    # Render components
    render_sidebar()
    render_chat()
    render_citations()


if __name__ == "__main__":
    main()
