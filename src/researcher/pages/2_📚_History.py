"""
History Mode for Researcher - Read-only session browsing and management.

This page provides a fast, read-only interface for browsing past sessions.
No ChatManager initialization, no conversation functionality.
Optimized for quick session lookup and viewing.
"""

import json
import logging
from collections import Counter
from typing import List, Dict, Optional

import streamlit as st
from researcher.utils.page_utils import initialize_session_history, get_usage_guide_markdown

LOGGER = logging.getLogger(__name__)


def render_readonly_sidebar():
    """読み取り専用サイドバー（セッション続行ボタンと使い方）"""
    with st.sidebar:
        st.title("📚 履歴閲覧")
        
        st.divider()
        
        # セッション続行ボタン
        selected_session_id = st.session_state.get("selected_session_id")
        
        if selected_session_id:
            if st.button("💬 セッションを続行する", key="continue_session", type="primary", use_container_width=True):
                # セッション情報を設定
                session_data = st.session_state.session_manager.load_session(selected_session_id)
                if session_data:
                    st.session_state.load_session_id = selected_session_id
                    st.session_state.load_session_name = session_data.get("name", "セッション")
                    st.switch_page("pages/1_💬_Chat.py")
                else:
                    st.error("セッションのロードに失敗しました")
        
        st.divider()
        
        # 使い方のヒント
        with st.expander("ℹ️ 使い方", expanded=False):
            st.markdown(get_usage_guide_markdown())


def extract_unique_tags() -> List[str]:
    """セッション一覧からユニークなタグを抽出"""
    try:
        if hasattr(st.session_state, 'session_manager'):
            return st.session_state.session_manager.get_all_tags()
    except Exception as e:
        LOGGER.warning(f"Failed to get tags from SessionManager: {e}")
    
    return []


def render_horizontal_filters():
    """水平フィルタUI（検索・タグ・日付トグル・日付範囲を1行に配置）"""
    # Column layout: [4, 3, 1, 2, 2] for search, tags, date toggle, date from, date to
    col_search, col_tags, col_date_toggle, col_date_from, col_date_to = st.columns([4, 3, 1, 2, 2])
    
    # Keyword search
    with col_search:
        search_query = st.text_input(
            "キーワード検索",
            key="session_search",
            placeholder="セッション名、履歴、タグで検索...",
            label_visibility="collapsed"
        )
    
    # Tag filter
    with col_tags:
        try:
            # Use efficient tag extraction without loading all sessions
            unique_tags = extract_unique_tags()
            
            if unique_tags:
                selected_tags = st.multiselect(
                    "タグフィルタ",
                    options=unique_tags,
                    key="tag_filter",
                    help="複数選択でAND条件",
                    label_visibility="collapsed"
                )
            else:
                selected_tags = None
        except Exception as e:
            LOGGER.error(f"Tag filter error: {e}")
            selected_tags = None
    
    # Date filter toggle
    with col_date_toggle:
        st.write("")  # Spacing
        date_filter_enabled = st.checkbox(
            "Date",
            key="date_filter_enabled",
            value=st.session_state.get("date_filter_enabled", False)
        )
    
    # Date range inputs (conditional)
    date_from = None
    date_to = None
    if date_filter_enabled:
        with col_date_from:
            date_from = st.date_input("開始日", key="date_from")
        with col_date_to:
            date_to = st.date_input("終了日", key="date_to")
    
    # Convert dates to ISO format
    date_from_str = date_from.isoformat() if date_from else None
    date_to_str = date_to.isoformat() if date_to else None
    
    return search_query, date_from_str, date_to_str, selected_tags


def get_filtered_sessions(
    search_query: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    tags: Optional[List[str]]
) -> List[Dict]:
    """フィルタ条件に基づいてセッションを取得"""
    try:
        # Get base sessions
        if search_query:
            sessions = st.session_state.session_manager.search_sessions(search_query)
            # Cap search results to 500 sessions (same as non-search path)
            sessions = sessions[:500]
        else:
            # Use list_sessions with filters (limit to 500 for performance)
            sessions = st.session_state.session_manager.list_sessions(
                date_from=date_from,
                date_to=date_to,
                tags=tags,
                limit=500,
                offset=0
            )
        
        # Apply additional filters when search query is present
        if search_query:
            # Apply date filter using single session_date (updated_at or created_at)
            if date_from or date_to:
                filtered = []
                for s in sessions:
                    # Derive session_date from updated_at or fallback to created_at
                    updated_at = s.get('updated_at', '')
                    created_at = s.get('created_at', '')
                    session_date = (updated_at[:10] if updated_at else created_at[:10]) if (updated_at or created_at) else ''
                    
                    # Apply AND semantics for date range
                    if date_from and session_date < date_from:
                        continue
                    if date_to and session_date > date_to:
                        continue
                    
                    filtered.append(s)
                sessions = filtered
            
            # Apply tag filter (AND condition - all tags must be present)
            if tags:
                def session_has_all_tags(session, required_tags):
                    session_tags_json = session.get('tags', '[]')
                    try:
                        session_tags = json.loads(session_tags_json) if isinstance(session_tags_json, str) else session_tags_json
                        if not isinstance(session_tags, list):
                            session_tags = []
                    except (json.JSONDecodeError, TypeError):
                        session_tags = []
                    
                    return all(tag in session_tags for tag in required_tags)
                
                sessions = [s for s in sessions if session_has_all_tags(s, tags)]
        
        # Sessions already limited to max 500
        return sessions
    except Exception as e:
        LOGGER.error(f"Failed to get filtered sessions: {e}")
        st.error(f"セッション取得に失敗しました: {e}")
        return []


def handle_session_selection():
    """Handle single row selection by resetting all other checkboxes"""
    if "session_list_df" in st.session_state:
        df = st.session_state.session_list_df
        
        # Find the row with Select=True
        selected_rows = df[df["選択"] == True]
        
        if len(selected_rows) > 1:
            # Multiple selections detected - keep only the last one
            # Reset all selections first
            df["選択"] = False
            # Set the last selected row (assume last in filtered set)
            last_selected_idx = selected_rows.index[-1]
            df.loc[last_selected_idx, "選択"] = True
            st.session_state.session_list_df = df
        
        # Update selected_session_id based on the selection
        selected_rows = df[df["選択"] == True]
        if len(selected_rows) == 1:
            st.session_state.selected_session_id = int(selected_rows.iloc[0]["ID"])
        else:
            st.session_state.selected_session_id = None


def render_compact_session_list(sessions: List[Dict]) -> Optional[int]:
    """コンパクトなセッション選択UI（高さ制限付き、チェックボックスで単一選択）"""
    if not sessions:
        st.info("セッションがありません")
        return None
    
    st.write(f"**{len(sessions)}件** のセッション（行をクリックして選択）")
    
    # Build dataframe for session list with height constraint and selection column
    import pandas as pd
    
    session_data = []
    current_session_id = st.session_state.get("selected_session_id")
    
    for session in sessions:
        updated_at = session.get('updated_at', '')
        updated_at_display = updated_at[:10] if updated_at and len(updated_at) >= 10 else 'N/A'
        
        # タグ表示を追加（最大2個まで）
        tags = session.get('tags', [])
        tags_display = ','.join(tags[:2]) if tags else ""
        
        # Check if this session is currently selected
        is_selected = (session['id'] == current_session_id)
        
        session_data.append({
            "選択": is_selected,
            "ID": session['id'],
            "セッション名": session['name'],
            "更新日": updated_at_display,
            "タグ": tags_display
        })
    
    df = pd.DataFrame(session_data)
    
    # Initialize or update session_list_df in session state
    if "session_list_df" not in st.session_state or len(st.session_state.session_list_df) != len(df):
        st.session_state.session_list_df = df
    
    # Display sessions with editable selection column
    edited_df = st.data_editor(
        st.session_state.session_list_df,
        hide_index=True,
        column_config={
            "選択": st.column_config.CheckboxColumn(
                "選択",
                width="small",
                help="セッションを選択",
                default=False
            ),
            "ID": st.column_config.NumberColumn("ID", width="small", disabled=True),
            "セッション名": st.column_config.TextColumn("セッション名", width="large", disabled=True),
            "更新日": st.column_config.TextColumn("更新日", width="small", disabled=True),
            "タグ": st.column_config.TextColumn("タグ", width="medium", disabled=True)
        },
        key="session_list_editor",
        height=200,
        use_container_width=True,
        on_change=handle_session_selection,
        disabled=["ID", "セッション名", "更新日", "タグ"]
    )
    
    # Update session state with edited dataframe
    st.session_state.session_list_df = edited_df
    
    # Handle selection enforcement (ensure only one checkbox is selected)
    handle_session_selection()
    
    # Return the selected session ID
    return st.session_state.get("selected_session_id")


def format_search_results_table(search_results: List[Dict]) -> Optional[List[Dict]]:
    """検索結果をテーブル形式に変換"""
    if not search_results:
        return None
    
    formatted_results = []
    for result in search_results:
        formatted_results.append({
            "タイトル": result.get("title", "N/A"),
            "URL": result.get("url", "N/A"),
            "スニペット": result.get("snippet", "")[:100] + "..." if len(result.get("snippet", "")) > 100 else result.get("snippet", ""),
            "日付": result.get("date", "N/A"),
            "スコア": result.get("score", "N/A")
        })
    
    return formatted_results


def render_session_detail(session_id: int):
    """セッション詳細を表示（タグ編集可能）"""
    try:
        # Load session data
        session_data = st.session_state.session_manager.load_session(session_id)
        
        if not session_data:
            st.error("セッションが見つかりません")
            return
        
        # Extract session components from V2 schema
        exchanges = session_data.get("exchanges", [])
        tags = session_data.get("tags", [])
        
        # Session header information
        st.subheader(f"📄 {session_data.get('name', 'Untitled Session')}")
        
        # Safe datetime formatting
        created_at = session_data.get('created_at', '')
        updated_at = session_data.get('updated_at', '')
        created_at_display = created_at[:16] if created_at and len(created_at) >= 16 else 'N/A'
        updated_at_display = updated_at[:16] if updated_at and len(updated_at) >= 16 else 'N/A'
        
        # Extract model/language from first exchange or use defaults
        model = 'N/A'
        language = 'ja'
        if exchanges:
            model = exchanges[0].get('model', 'N/A')
            language = exchanges[0].get('language', 'ja')
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("作成日時", created_at_display)
        with col2:
            st.metric("更新日時", updated_at_display)
        with col3:
            st.metric("モデル", model)
        with col4:
            st.metric("言語", language)
        
        # タグ編集UI（エクスパンダー内）
        with st.expander("🏷️ タグ管理", expanded=False):
            # タグ表示
            if tags:
                st.markdown("**現在のタグ:**")
                tags_html = " ".join([
                    f'<span style="background-color: #e0e0e0; padding: 4px 12px; border-radius: 6px; margin-right: 6px; font-size: 0.9em;">🏷️ {tag}</span>'
                    for tag in tags
                ])
                st.markdown(tags_html, unsafe_allow_html=True)
            else:
                st.info("タグが設定されていません")
            
            st.markdown("---")
            
            # 既存タグの削除UI
            if tags:
                st.markdown("**タグを削除:**")
                cols = st.columns(len(tags))
                for idx, tag in enumerate(tags):
                    with cols[idx]:
                        if st.button(f"❌ {tag}", key=f"remove_tag_{session_id}_{idx}"):
                            new_tags = [t for t in tags if t != tag]
                            if st.session_state.session_manager.update_session_tags(session_id, new_tags):
                                st.success(f"タグ '{tag}' を削除しました")
                                st.rerun()
                            else:
                                st.error("タグの削除に失敗しました")
            
            # 新しいタグの追加UI
            st.markdown("**新しいタグを追加:**")
            col_input, col_add = st.columns([3, 1])
            with col_input:
                new_tag = st.text_input(
                    "タグ名",
                    key=f"new_tag_input_{session_id}",
                    placeholder="例: 重要, 調査中, レビュー済み"
                )
            with col_add:
                st.write("")  # Spacing
                if st.button("➕ 追加", key=f"add_tag_{session_id}"):
                    if new_tag and new_tag.strip():
                        new_tags = tags + [new_tag.strip()]
                        if st.session_state.session_manager.update_session_tags(session_id, new_tags):
                            st.success(f"タグ '{new_tag}' を追加しました")
                            st.rerun()
                        else:
                            st.error("タグの追加に失敗しました")
                    else:
                        st.warning("タグ名を入力してください")
            
            # 既存タグから選択して追加
            all_tags = st.session_state.session_manager.get_all_tags()
            available_tags = [t for t in all_tags if t not in tags]
            if available_tags:
                st.markdown("**既存のタグから選択:**")
                selected_existing_tag = st.selectbox(
                    "タグを選択",
                    options=[""] + available_tags,
                    key=f"select_existing_tag_{session_id}"
                )
                if selected_existing_tag:
                    if st.button("➕ 追加", key=f"add_existing_tag_{session_id}"):
                        new_tags = tags + [selected_existing_tag]
                        if st.session_state.session_manager.update_session_tags(session_id, new_tags):
                            st.success(f"タグ '{selected_existing_tag}' を追加しました")
                            st.rerun()
                        else:
                            st.error("タグの追加に失敗しました")
        
        st.divider()
        
        # Display conversation history from exchanges
        st.subheader("💬 会話履歴")
        if exchanges:
            for exchange in exchanges:
                # Display user message
                with st.chat_message("user"):
                    st.markdown(exchange.get("user_message", ""))
                
                # Display assistant message
                with st.chat_message("assistant"):
                    st.markdown(exchange.get("assistant_message", ""))
                    
                    # Display evaluation score if available
                    eval_score = exchange.get("evaluation_score")
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
                    search_results = exchange.get("search_results")
                    if search_results:
                        with st.expander("🔍 検索結果", expanded=False):
                            # Format search results as table
                            table_data = format_search_results_table(search_results)
                
                            if table_data:
                                # Create clickable links for URLs using markdown in dataframe
                                import pandas as pd
                                df = pd.DataFrame(table_data)
                                
                                # Convert URL column to clickable markdown links
                                def make_clickable(url):
                                    if url and url != "N/A":
                                        return f'<a href="{url}" target="_blank">{url}</a>'
                                    return url
                                
                                if "URL" in df.columns:
                                    df["URL"] = df["URL"].apply(make_clickable)
                                
                                # Display as HTML table with clickable links
                                st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                            else:
                                st.info("検索結果がありません")
        else:
            st.info("会話履歴がありません")
    
    except json.JSONDecodeError as e:
        LOGGER.error(f"Failed to parse session {session_id}: {e}")
        st.warning("古いセッション形式です。データの解析に失敗しました。")
    except Exception as e:
        LOGGER.error(f"Failed to load session {session_id}: {e}")
        st.error(f"セッションの読み込みに失敗しました: {e}")


def render_calendar_visualization(sessions: List[Dict]):
    """カレンダー可視化（日付ごとのセッション数をMarkdownテーブルで表示）"""
    if not sessions:
        return
    
    st.subheader("📊 セッション作成カレンダー")
    
    # 日付ごとのセッション数を集計
    date_counts = Counter()
    for session in sessions:
        created_at = session.get("created_at", "")
        if created_at:
            date = created_at[:10]  # YYYY-MM-DD形式
            date_counts[date] += 1
    
    if not date_counts:
        st.info("セッションデータがありません")
        return
    
    # 最近30日分を表示
    sorted_dates = sorted(date_counts.keys(), reverse=True)[:30]
    
    # Markdownテーブルで表示
    st.markdown("| 日付 | セッション数 | バー |")
    st.markdown("|------|------------|------|")
    max_count = max(date_counts.values())
    for date in sorted_dates:
        count = date_counts[date]
        bar = "█" * int((count / max_count) * 20)  # 最大20文字のバー
        st.markdown(f"| {date} | {count}件 | {bar} |")


def main():
    """History Mode main entry point."""
    st.set_page_config(
        page_title="History - Researcher",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply text size CSS from settings
    from researcher.config import load_settings
    from researcher.utils.page_utils import apply_text_size_css
    
    settings = load_settings()
    text_size = settings.get('ui_text_size', 'medium')
    apply_text_size_css(text_size)
    
    # Initialize History Mode (SessionManager only, no ChatManager)
    initialize_session_history()
    
    # Initialize date filter enabled state
    if "date_filter_enabled" not in st.session_state:
        st.session_state.date_filter_enabled = False
    
    st.title("📚 履歴閲覧 (History Mode)")
    st.markdown("*過去のセッションを検索・表示します（読み取り専用）*")
    st.markdown("---")
    
    # Sidebar: Read-only display
    render_readonly_sidebar()
    
    # Main content layout - Vertical 3-row layout
    # Row 1: Horizontal filter bar
    search_query, date_from, date_to, selected_tags = render_horizontal_filters()
    
    st.divider()
    
    # Row 2: Compact session list
    # Get filtered sessions
    filtered_sessions = get_filtered_sessions(
        search_query,
        date_from,
        date_to,
        selected_tags
    )
    
    # Session selector (compact)
    selected_session_id = render_compact_session_list(filtered_sessions)
    
    st.divider()
    
    # Row 3: Full-width session details
    if selected_session_id:
        # Render session detail with tag editing
        render_session_detail(selected_session_id)
    else:
        st.info("上のリストからセッションを選択してください")


if __name__ == "__main__":
    main()
