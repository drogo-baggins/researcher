# -*- coding: utf-8 -*-
"""
Settings Page - Configure LLM models and SearXNG search parameters
"""
import streamlit as st
from researcher.config import load_settings, save_settings, DEFAULT_SETTINGS
from researcher.ollama_client import OllamaClient


def render_sidebar():
    """Render minimal sidebar with navigation links"""
    with st.sidebar:
        st.title("⚙️ 設定")
        
        st.divider()
        
        # Navigation links
        st.page_link("Home.py", label="🏠 ホーム")
        st.page_link("pages/1_💬_Chat.py", label="💬 Chat")
        st.page_link("pages/2_📚_History.py", label="📚 History")


def get_available_models():
    """Get list of available Ollama models
    
    Returns:
        List of model names, or empty list if error
    """
    try:
        ollama_client = OllamaClient()
        models = ollama_client.list_models()
        return models if models else []
    except Exception as e:
        st.warning(f"⚠️ Ollamaサーバーに接続できません: {e}")
        return []


def render_llm_settings(settings, available_models):
    """Render LLM model configuration section
    
    Args:
        settings: Current settings dictionary
        available_models: List of available model names
    
    Returns:
        Dictionary with selected model values
    """
    st.subheader("🤖 LLMモデル設定")
    
    # Show warning if no models available
    if not available_models:
        st.warning("Ollamaサーバーに接続できません。モデル一覧を取得できませんでした。")
    
    # Current settings info
    st.info(f"""
    **現在の設定**:
    - 検索語生成: {settings.get('search_model', 'llama3.2')}
    - 回答生成: {settings.get('response_model', 'llama3')}
    - 品質検証: {settings.get('eval_model', 'llama3.2:3b')}
    """)
    
    # Build model options (include current settings for backward compatibility)
    model_options = list(available_models)
    for key in ['search_model', 'response_model', 'eval_model']:
        current_value = settings.get(key)
        if current_value and current_value not in model_options:
            model_options.append(current_value)
    
    # Sort model options
    model_options = sorted(set(model_options))
    
    # If no models available, use current settings as options
    if not model_options:
        model_options = [
            settings.get('search_model', 'llama3.2'),
            settings.get('response_model', 'llama3'),
            settings.get('eval_model', 'llama3.2:3b')
        ]
        model_options = sorted(set(model_options))
    
    # Search model selectbox
    search_model_default = settings.get('search_model', 'llama3.2')
    search_model_index = model_options.index(search_model_default) if search_model_default in model_options else 0
    
    selected_search_model = st.selectbox(
        "検索語生成モデル",
        options=model_options,
        index=search_model_index,
        help="Web検索のキーワード生成に使用するモデル",
        key="search_model_select"
    )
    
    # Response model selectbox
    response_model_default = settings.get('response_model', 'llama3')
    response_model_index = model_options.index(response_model_default) if response_model_default in model_options else 0
    
    selected_response_model = st.selectbox(
        "回答生成モデル",
        options=model_options,
        index=response_model_index,
        help="ユーザーへの回答生成に使用するモデル",
        key="response_model_select"
    )
    
    # Evaluation model selectbox
    eval_model_default = settings.get('eval_model', 'llama3.2:3b')
    eval_model_index = model_options.index(eval_model_default) if eval_model_default in model_options else 0
    
    selected_eval_model = st.selectbox(
        "品質検証モデル",
        options=model_options,
        index=eval_model_index,
        help="回答の品質評価に使用するモデル（軽量モデル推奨）",
        key="eval_model_select"
    )
    
    # Validation warnings
    if available_models:
        if selected_search_model not in available_models:
            st.warning(f"⚠️ 検索語生成モデル '{selected_search_model}' が見つかりません。実行時エラーの可能性があります。")
        if selected_response_model not in available_models:
            st.warning(f"⚠️ 回答生成モデル '{selected_response_model}' が見つかりません。実行時エラーの可能性があります。")
        if selected_eval_model not in available_models:
            st.warning(f"⚠️ 品質検証モデル '{selected_eval_model}' が見つかりません。実行時エラーの可能性があります。")
    
    return {
        'search_model': selected_search_model,
        'response_model': selected_response_model,
        'eval_model': selected_eval_model
    }


def render_searxng_settings(settings):
    """Render SearXNG search configuration section
    
    Args:
        settings: Current settings dictionary
    
    Returns:
        Dictionary with selected SearXNG values
    """
    st.subheader("🔍 SearXNG検索設定")
    
    # Current settings info
    st.info(f"""
    **現在の設定**:
    - 検索エンジン: {settings.get('searxng_engine', 'general')}
    - 言語: {settings.get('searxng_lang', 'ja')}
    - セーフサーチ: {settings.get('searxng_safesearch', 'off')}
    """)
    
    # Search engine selectbox
    engine_options = ["general", "news", "science", "images", "カスタム"]
    current_engine = settings.get('searxng_engine', 'general')
    
    # Check if current engine is custom
    is_custom = current_engine not in ["general", "news", "science", "images"]
    if is_custom:
        engine_index = engine_options.index("カスタム")
    else:
        engine_index = engine_options.index(current_engine)
    
    selected_engine_option = st.selectbox(
        "検索エンジン",
        options=engine_options,
        index=engine_index,
        help="SearXNGで使用する検索エンジンカテゴリ",
        key="searxng_engine_select"
    )
    
    # Custom engine input
    selected_engine = selected_engine_option
    if selected_engine_option == "カスタム":
        custom_engine = st.text_input(
            "カスタムエンジン名",
            value=current_engine if is_custom else "",
            placeholder="例: duckduckgo, google, bing",
            help="SearXNGでサポートされているエンジン名を入力",
            key="custom_engine_input"
        )
        selected_engine = custom_engine
    
    # Language selectbox
    lang_options = ["ja", "en"]
    current_lang = settings.get('searxng_lang', 'ja')
    lang_index = lang_options.index(current_lang) if current_lang in lang_options else 0
    
    selected_lang = st.selectbox(
        "検索言語",
        options=lang_options,
        index=lang_index,
        help="検索結果の言語フィルタ",
        key="searxng_lang_select"
    )
    
    # Safesearch selectbox
    safesearch_options = ["off", "moderate", "on"]
    current_safesearch = settings.get('searxng_safesearch', 'off')
    safesearch_index = safesearch_options.index(current_safesearch) if current_safesearch in safesearch_options else 0
    
    selected_safesearch = st.selectbox(
        "セーフサーチ",
        options=safesearch_options,
        index=safesearch_index,
        help="検索結果のフィルタリングレベル",
        key="searxng_safesearch_select"
    )
    
    return {
        'searxng_engine': selected_engine,
        'searxng_lang': selected_lang,
        'searxng_safesearch': selected_safesearch,
        'is_custom_engine': selected_engine_option == "カスタム"
    }


def main():
    """Main entry point for Settings page"""
    st.set_page_config(
        page_title="Settings - Researcher",
        page_icon="⚙️",
        layout="wide"
    )
    
    # Render sidebar
    render_sidebar()
    
    # Page header
    st.title("⚙️ 設定")
    st.markdown("""
    このページでは、Researcherアプリケーションの設定を管理できます。
    設定は `~/.researcher/settings.json` に保存され、次回のChat/History初期化時に適用されます。
    """)
    
    st.divider()
    
    # Initialize settings in session state
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()
    
    settings = st.session_state.settings
    
    # Get available models
    available_models = get_available_models()
    
    # Render LLM settings section
    llm_selections = render_llm_settings(settings, available_models)
    
    st.divider()
    
    # Render SearXNG settings section
    searxng_selections = render_searxng_settings(settings)
    
    st.divider()
    
    # Action buttons
    col1, col2 = st.columns(2)
    
    with col1:
        save_button = st.button(
            "💾 設定を保存",
            type="primary",
            use_container_width=True,
            key="save_settings_button"
        )
    
    with col2:
        reset_button = st.button(
            "🔄 デフォルトに戻す",
            use_container_width=True,
            key="reset_settings_button"
        )
    
    # Handle save button
    if save_button:
        # Validate custom engine
        if searxng_selections['is_custom_engine'] and not searxng_selections['searxng_engine'].strip():
            st.warning("カスタムエンジン名を入力してください")
        else:
            # Build new settings
            new_settings = {
                'search_model': llm_selections['search_model'],
                'response_model': llm_selections['response_model'],
                'eval_model': llm_selections['eval_model'],
                'searxng_engine': searxng_selections['searxng_engine'],
                'searxng_lang': searxng_selections['searxng_lang'],
                'searxng_safesearch': searxng_selections['searxng_safesearch']
            }
            
            # Save settings
            success = save_settings(new_settings)
            
            if success:
                # Update session state immediately
                st.session_state.settings = new_settings
                
                # Force Chat to reinitialize with new settings
                if "chat_initialized" in st.session_state:
                    del st.session_state.chat_initialized
                if "chat_manager" in st.session_state:
                    del st.session_state.chat_manager
                
                st.success("✅ 設定を保存しました")
                st.rerun()
            else:
                st.error("❌ 設定の保存に失敗しました")
    
    # Handle reset button
    if reset_button:
        success = save_settings(DEFAULT_SETTINGS)
        if success:
            st.session_state.settings = DEFAULT_SETTINGS
            
            # Force Chat to reinitialize with default settings
            if "chat_initialized" in st.session_state:
                del st.session_state.chat_initialized
            if "chat_manager" in st.session_state:
                del st.session_state.chat_manager
            
            st.success("✅ 設定をデフォルトに戻しました")
            st.rerun()
        else:
            st.error("❌ 設定のリセットに失敗しました")


if __name__ == "__main__":
    main()
