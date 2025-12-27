"""
Chat Page for Researcher - Conversation interface.

This page provides the main chat interface for interacting with the LLM,
including automatic search, streaming responses, and feedback collection.
"""

import logging
from typing import Any, Dict
import streamlit as st
from researcher.config import save_feedback
from researcher.agent import QueryAgent
from researcher.utils.page_utils import initialize_session_chat, load_session_helper, start_new_conversation, get_usage_guide_markdown

LOGGER = logging.getLogger(__name__)


def render_minimal_sidebar():
    """最小限のサイドバー（タグ管理と新規セッションボタンのみ）"""
    with st.sidebar:
        st.title("💬 Chat")
        
        # === New Session Button ===
        if st.button("🆕 新規セッション", key="start_new_conversation", type="primary", use_container_width=True):
            if start_new_conversation():
                st.success("✅ 新しい会話を開始しました")
                st.rerun()
            else:
                st.error("新規会話の開始に失敗しました")
        
        st.divider()
        
        # === Tag Management ===
        st.subheader("🏷️ タグ管理")
        
        # 全タグを取得
        all_tags = st.session_state.session_manager.get_all_tags()
        
        # セッションが存在する場合はセッションのタグ、そうでない場合は仮タグを使用
        if st.session_state.current_session_id is not None:
            # 現在のタグを取得
            session_data = st.session_state.session_manager.load_session(st.session_state.current_session_id)
            current_tags = session_data.get("tags", []) if session_data else []
            multiselect_key = f"tag_multiselect_{st.session_state.current_session_id}"
        else:
            # セッション作成前：仮タグを使用
            if "pending_tags" not in st.session_state:
                st.session_state.pending_tags = []
            current_tags = st.session_state.pending_tags
            multiselect_key = "tag_multiselect_pending"
        
        # current_tagsにall_tagsに含まれていない場合、all_tagsに追加（孤立タグ対応）
        options_tags = list(set(all_tags + current_tags))  # 重複除去してマージ
        options_tags.sort()  # ソートして表示
        
        # マルチセレクトでタグを管理
        selected_tags = st.multiselect(
            "タグを選択" + ("" if st.session_state.current_session_id else " (質問送信時に適用)"),
            options=options_tags,
            default=current_tags,
            key=multiselect_key,
            help="複数のタグを選択して整理できます"
        )
        
        # タグが変更された場合の処理
        if set(selected_tags) != set(current_tags):
            if st.session_state.current_session_id is not None:
                # セッションが存在する場合は即座に更新
                if st.session_state.session_manager.update_session_tags(st.session_state.current_session_id, selected_tags):
                    st.success("タグを更新しました")
                    st.rerun()
                else:
                    st.error("タグの更新に失敗しました")
            else:
                # セッション作成前は仮タグとして保存
                st.session_state.pending_tags = selected_tags
        
        # 新規タグ追加UI
        with st.expander("➕ 新しいタグを作成", expanded=False):
            new_tag = st.text_input("新しいタグ名", key="new_tag_input", placeholder="例: AI, Python")
            if st.button("作成して追加", key="create_tag_button", use_container_width=True):
                if new_tag and new_tag.strip():
                    tag_to_add = new_tag.strip()
                    if tag_to_add not in options_tags:
                        updated_tags = current_tags + [tag_to_add]
                        if st.session_state.current_session_id is not None:
                            if st.session_state.session_manager.update_session_tags(st.session_state.current_session_id, updated_tags):
                                st.success(f"タグ '{tag_to_add}' を作成して追加しました")
                                st.rerun()
                            else:
                                st.error("タグの追加に失敗しました")
                        else:
                            # セッション作成前は仮タグに追加
                            st.session_state.pending_tags = updated_tags
                            st.success(f"タグ '{tag_to_add}' を作成しました（質問送信時に適用）")
                            st.rerun()
                    else:
                        st.warning("このタグは既に存在します（上のリストから選択してください）")
                else:
                    st.warning("タグ名を入力してください")
        
        st.divider()
        
        # === Usage Guide ===
        with st.expander("ℹ️ 使い方", expanded=False):
            st.markdown(get_usage_guide_markdown())


def render_feedback_buttons(msg_index: int, user_msg_content: str, assistant_msg_content: str) -> None:
    """
    アシスタントメッセージに対するフィードバックボタンを表示
    
    Args:
        msg_index: メッセージのインデックス
        user_msg_content: 対応するユーザーメッセージ
        assistant_msg_content: アシスタントメッセージの内容
    """
    col1, col2, spacer = st.columns([1, 1, 10])
    with col1:
        if st.button("👍", key=f"feedback_up_{msg_index}", help="この回答が良かった場合はクリック"):
            model = st.session_state.chat_manager.get_current_model()
            success = save_feedback(
                user_msg_content,
                assistant_msg_content,
                "up",
                model,
                st.session_state.current_session_id
            )
            if success:
                st.success("フィードバックを保存しました ✓", icon="✅")
            else:
                st.error("フィードバック保存に失敗しました")
    
    with col2:
        if st.button("👎", key=f"feedback_down_{msg_index}", help="この回答が悪かった場合はクリック"):
            model = st.session_state.chat_manager.get_current_model()
            success = save_feedback(
                user_msg_content,
                assistant_msg_content,
                "down",
                model,
                st.session_state.current_session_id
            )
            if success:
                st.success("フィードバックを保存しました ✓", icon="✅")
            else:
                st.error("フィードバック保存に失敗しました")


def auto_save_session(user_input: str, messages: list, chat_manager: Any, eval_score: Dict = None) -> bool:
    """
    セッションを自動保存（新規作成または会話応酬の追加）
    
    Args:
        user_input: ユーザー入力テキスト
        messages: メッセージ履歴
        chat_manager: ChatManagerインスタンス
        eval_score: 評価スコア（オプション）
    
    Returns:
        bool: 保存成功時True
    """
    try:
        session_manager = st.session_state.session_manager
        
        # 新規セッション作成（初回メッセージ時）
        if st.session_state.current_session_id is None:
            session_name = f"{user_input[:50]}..." if len(user_input) > 50 else user_input
            
            # 仮タグがあれば適用
            pending_tags = st.session_state.get("pending_tags", [])
            
            new_id = session_manager.create_session(session_name, tags=pending_tags)
            if new_id:
                st.session_state.current_session_id = new_id
                st.session_state.current_session_name = session_name
                # 仮タグをクリア
                st.session_state.pending_tags = []
                LOGGER.info(f"Created new session {new_id}: {session_name} with tags: {pending_tags}")
            else:
                LOGGER.error("Failed to create new session")
                return False
        else:
            # セッション名を最新のユーザー入力で更新
            new_session_name = f"{user_input[:50]}..." if len(user_input) > 50 else user_input
            session_manager.rename_session(
                st.session_state.current_session_id,
                new_session_name
            )
            st.session_state.current_session_name = new_session_name
        
        # 最新の会話応酬（Q&A）を保存
        if st.session_state.current_session_id is not None and len(messages) >= 2:
            # 最後のユーザーメッセージとアシスタントメッセージを取得
            last_user_msg = None
            last_assistant_msg = None
            
            for msg in reversed(messages):
                if msg.get("role") == "assistant" and last_assistant_msg is None:
                    last_assistant_msg = msg["content"]
                elif msg.get("role") == "user" and last_user_msg is None:
                    last_user_msg = msg["content"]
                
                if last_user_msg and last_assistant_msg:
                    break
            
            if last_user_msg and last_assistant_msg:
                # 検索結果を抽出
                search_results = []
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and "search_results" in msg:
                        search_results = msg["search_results"]
                        break
                
                # 評価スコアを取得
                if eval_score is None:
                    eval_score = chat_manager.get_last_evaluation_score()
                
                # 会話応酬を保存
                exchange_id = session_manager.save_exchange(
                    st.session_state.current_session_id,
                    last_user_msg,
                    last_assistant_msg,
                    st.session_state.model,
                    st.session_state.language,
                    search_results=search_results,
                    evaluation_score=eval_score
                )
                
                if exchange_id:
                    LOGGER.info(f"Saved exchange {exchange_id} to session {st.session_state.current_session_id}")
                    return True
                else:
                    LOGGER.error("Failed to save exchange")
                    return False
        
        return True
    except Exception as e:
        LOGGER.error(f"Failed to auto-save session: {e}", exc_info=True)
        return False


def render_chat():
    """メインチャットインターフェース"""
    st.title("🔍 Researcher")
    st.markdown("*ローカルAIリサーチャー - Ollama + SearXNG*")
    
    # Initialize message display limit for virtualization
    if "message_display_limit" not in st.session_state:
        st.session_state.message_display_limit = None  # None = show all
    
    # Message virtualization: show limited messages if history is large
    total_messages = len(st.session_state.messages)
    if total_messages > 50 and st.session_state.message_display_limit is None:
        # Show button to load all messages
        if st.button("📜 過去のメッセージを表示 ({}件)".format(total_messages - 30)):
            st.session_state.message_display_limit = total_messages
            st.rerun()
        display_messages = st.session_state.messages[-30:]  # Show latest 30
        start_idx = total_messages - 30
    else:
        display_messages = st.session_state.messages
        start_idx = 0
    
    # Display message history with feedback buttons for assistant messages
    for relative_idx, msg in enumerate(display_messages):
        idx = start_idx + relative_idx  # Calculate absolute index
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # Display evaluation score for assistant messages
            if msg["role"] == "assistant":
                # メッセージに埋め込まれた評価を優先、なければlast_evaluation_scoreを使用（最後のメッセージのみ）
                eval_score = msg.get("evaluation")
                if not eval_score and idx == len(st.session_state.messages) - 1:
                    # 最後のメッセージの場合、chat_managerから取得
                    eval_score = st.session_state.chat_manager.get_last_evaluation_score()
                
                if eval_score:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        acc_score = float(eval_score.get('accuracy_score', 0)) if eval_score.get('accuracy_score') is not None else 0.0
                        st.metric("正確性", f"{acc_score:.2f}")
                    with col2:
                        fresh_score = float(eval_score.get('freshness_score', 0)) if eval_score.get('freshness_score') is not None else 0.0
                        st.metric("最新性", f"{fresh_score:.2f}")
                    with col3:
                        overall_score = float(eval_score.get('overall_score', 0)) if eval_score.get('overall_score') is not None else 0.0
                        st.metric("総合", f"{overall_score:.2f}")
                    if eval_score.get('reasoning'):
                        with st.expander("📊 評価理由"):
                            st.write(eval_score['reasoning'])
                
                # Display search results if available
                search_results = msg.get("search_results", [])
                if search_results:
                    with st.expander(f"🔍 検索結果 ({len(search_results)}件)", expanded=False):
                        # Delayed loading for large result sets
                        show_all_key = f"show_all_results_{idx}"
                        if len(search_results) > 10:
                            if not st.session_state.get(show_all_key, False):
                                if st.button("さらに表示 (+{}件)".format(len(search_results) - 5), key=f"load_more_{idx}"):
                                    st.session_state[show_all_key] = True
                                    st.rerun()
                                display_results = search_results[:5]
                            else:
                                display_results = search_results
                        else:
                            display_results = search_results
                        
                        # テーブルヘッダー
                        st.markdown("| タイトル | URL | スニペット | 日付 | 関連性 | 信頼性 |")
                        st.markdown("|---------|-----|----------|------|--------|--------|")
                        
                        # 各検索結果を行として表示
                        for result in display_results:
                            title = result.get("title", "N/A")
                            url = result.get("url", "")
                            snippet = result.get("snippet", "")
                            snippet_display = snippet[:100] + ("..." if len(snippet) > 100 else "")
                            date = result.get("date", "N/A")
                            relevance = result.get("relevance_score", 0.0)
                            credibility = result.get("credibility_score", 0.0)
                            
                            # リンク化されたタイトル
                            title_display = title[:50] + ("..." if len(title) > 50 else "")
                            title_link = f"[{title_display}]({url})" if url else title_display
                            
                            # URL短縮表示
                            url_display = url[:30] + "..." if len(url) > 30 else url
                            
                            # スコアの色分け
                            relevance_color = "🟢" if relevance >= 0.7 else "🟡" if relevance >= 0.5 else "🔴"
                            credibility_color = "🟢" if credibility >= 0.7 else "🟡" if credibility >= 0.5 else "🔴"
                            
                            st.markdown(f"| {title_link} | {url_display} | {snippet_display} | {date} | {relevance_color} {relevance:.2f} | {credibility_color} {credibility:.2f} |")
            
            # Add feedback buttons for assistant messages
            if msg["role"] == "assistant":
                # Find corresponding user message (previous message)
                user_msg_content = ""
                for prev_msg in reversed(st.session_state.messages[:idx]):
                    if prev_msg["role"] == "user":
                        user_msg_content = prev_msg["content"]
                        break
                
                # Render feedback buttons using helper function
                render_feedback_buttons(idx, user_msg_content, msg["content"])
    
    # User input
    if user_input := st.chat_input("質問を入力してください...", key="chat_input"):
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Auto-search if enabled
        if st.session_state.auto_search and st.session_state.chat_manager.searxng_client:
            progress_placeholder = st.empty()
            
            def create_search_progress_callback(placeholder):
                """検索リトライの進行状況を表示するコールバックを生成"""
                def callback(event: str, data: Dict[str, Any]) -> None:
                    if event == "retry_start":
                        placeholder.info(f"🔄 検索失敗（試行 {data['retry_count']}/{data['max_retries']}）: {data.get('error', '')[:100]}")
                    elif event == "query_generated":
                        placeholder.info(f"🔍 代替クエリで再試行（{data['retry_count']}/{data.get('max_retries', 3)}）: {data['new_query'][:100]}")
                    elif event == "retry_attempt":
                        placeholder.info(f"⏳ 検索中（試行 {data['retry_count']}）...")
                    elif event == "all_retries_failed":
                        placeholder.error(f"❌ 検索失敗: すべてのリトライが失敗しました（{data['max_retries']}回試行）")
                return callback
            
            progress_callback = create_search_progress_callback(progress_placeholder)
            
            with st.spinner("🔍 検索中..."):
                try:
                    auto_result = st.session_state.chat_manager.auto_search(
                        user_input, 
                        progress_callback=progress_callback
                    )
                    st.session_state.chat_manager.pending_search_results = auto_result.get("all_search_results", [])
                    if auto_result.get("searched"):
                        with st.expander("📚 検索結果", expanded=False):
                            st.text(auto_result["formatted"])
                    
                    # 検索失敗時の明確なメッセージ
                    if auto_result.get("search_failed"):
                        st.error("❌ 検索に失敗しました。検索エンジンが応答していない可能性があります。")
                except Exception as e:
                    st.error(f"❌ 自動検索に失敗: {e}")
                finally:
                    # プログレス表示をクリア
                    progress_placeholder.empty()
        
        # Add user message to ChatManager
        st.session_state.chat_manager.add_user_message(user_input)
        
        # Display search results if available (折りたたみ方式)
        try:
            search_content = st.session_state.chat_manager.last_search_content
            search_turns = st.session_state.chat_manager.last_search_turns_remaining
            if search_content and isinstance(search_turns, int) and search_turns > 0:
                with st.expander("📚 検索結果・クロール済みコンテンツ", expanded=False):
                    st.markdown(search_content)
        except (AttributeError, TypeError):
            # Skip search result display if attributes don't exist or aren't properly typed
            pass
        
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
        
        # Copy search_results from ChatManager to UI messages for display and persistence
        if st.session_state.chat_manager.messages:
            last_chat_msg = st.session_state.chat_manager.messages[-1]
            if last_chat_msg.get("role") == "assistant" and "search_results" in last_chat_msg:
                st.session_state.messages[-1]["search_results"] = last_chat_msg["search_results"]
        
        # 評価スコアの取得と埋め込み（ジェネレータ完全消費後なので確実に取得可能）
        eval_score = st.session_state.chat_manager.get_last_evaluation_score()
        
        if eval_score:
            st.session_state.messages[-1]["evaluation"] = eval_score
            LOGGER.debug(f"Evaluation embedded: {eval_score}")
        else:
            LOGGER.warning("Evaluation score not available after streaming")
        
        # Auto-save session using helper function
        save_success = auto_save_session(
            user_input,
            st.session_state.messages,
            st.session_state.chat_manager,
            eval_score
        )
        
        if not save_success:
            st.warning("⚠️ セッションの保存に失敗しました。後で再試行してください。")


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
    """Chat page main entry point."""
    st.set_page_config(
        page_title="Chat - Researcher",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session if not already done (idempotent, safe for deep-links)
    initialize_session_chat()
    
    # Handle session loading from History page
    if "load_session_id" in st.session_state:
        session_id = st.session_state.pop("load_session_id")
        session_name = st.session_state.pop("load_session_name", "セッション")
        LOGGER.info(f"[CHAT] Loading session {session_id}: {session_name}")
        load_session_helper(session_id, session_name, trigger_rerun=True)
    
    # Verification logic (runs on every render after session load)
    if st.session_state.get("current_session_id") is not None:
        # Verify message count consistency
        ui_message_count = len(st.session_state.get("messages", []))
        chat_manager_message_count = len(st.session_state.chat_manager.messages)
        
        if ui_message_count != chat_manager_message_count:
            LOGGER.warning(
                f"[CHAT] Message count mismatch detected: "
                f"UI={ui_message_count}, ChatManager={chat_manager_message_count}"
            )
            st.warning(
                f"⚠️ メッセージ数の不一致を検出しました（UI: {ui_message_count}件、内部: {chat_manager_message_count}件）。"
                "表示に問題がある場合は、セッションを再読み込みしてください。"
            )
        
        # Verify old session format (missing search_results)
        if ui_message_count > 0:
            has_search_results = any(
                msg.get("role") == "assistant" and "search_results" in msg
                for msg in st.session_state.messages
            )
            
            if not has_search_results and ui_message_count > 2:  # Ignore very short sessions
                LOGGER.info(
                    f"[CHAT] Old session format detected (no search_results): "
                    f"session_id={st.session_state.current_session_id}"
                )
                st.info(
                    "ℹ️ このセッションは古い形式です。検索結果の表示機能は利用できません。"
                )
    
    render_minimal_sidebar()
    render_chat()
    render_citations()


if __name__ == "__main__":
    main()
