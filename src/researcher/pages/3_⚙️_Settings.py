# -*- coding: utf-8 -*-
"""
Settings Page - Configure LLM models, OpenAI-compatible providers and SearXNG.
"""

import streamlit as st
from researcher.config import (
    load_settings,
    save_settings,
    DEFAULT_SETTINGS,
    DEFAULT_OLLAMA_BASE_URL,
    MODEL_KEY_SEPARATOR,
    get_ollama_base_url,
)
from researcher.ollama_client import OllamaClient


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar():
    with st.sidebar:
        st.title("⚙️ 設定")
        st.divider()
        st.page_link("Home.py", label="🏠 ホーム")
        st.page_link("pages/1_💬_Chat.py", label="💬 Chat")
        st.page_link("pages/2_📚_History.py", label="📚 History")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_ollama_models(settings: dict | None = None):
    """Return list of model names from local Ollama, or [] on error."""
    try:
        base_url = get_ollama_base_url(settings)
        client = OllamaClient(base_url=base_url)
        models = client.list_models()
        return models if models else []
    except Exception as e:
        st.warning(f"⚠️ Ollamaサーバーに接続できません: {e}")
        return []


def _build_all_model_options(settings: dict, ollama_models: list) -> list:
    """Build the unified model option list.

    Ollama models are included as plain names.
    Each OpenAI-compatible provider's models are prefixed with
    ``<providerName>::``.
    """
    options = list(ollama_models)

    for provider in settings.get("llm_providers", []):
        name = provider.get("name", "").strip()
        for m in provider.get("models", []):
            m = m.strip()
            if m:
                key = f"{name}{MODEL_KEY_SEPARATOR}{m}"
                if key not in options:
                    options.append(key)

    return sorted(set(options))


# ---------------------------------------------------------------------------
# Render: Provider Management
# ---------------------------------------------------------------------------


def render_provider_settings(settings: dict) -> dict:
    """Render OpenAI-compatible provider management section."""
    st.subheader("🌐 OpenAI互換プロバイダ")
    st.caption(
        "VeniceAI・Azure OpenAI・OpenRouter など OpenAI 互換 API を持つプロバイダを追加できます。"
        "モデルの選択は「**🤖 LLMモデル設定**」セクションで行います。"
    )

    providers: list = [dict(p) for p in settings.get("llm_providers", [])]

    # ---- existing providers ----
    if providers:
        st.markdown("**登録済みプロバイダ**")
        to_delete = None

        for idx, provider in enumerate(providers):
            pname = provider.get("name", f"Provider {idx + 1}")
            with st.expander(f"✏️ {pname}", expanded=False):
                new_name = st.text_input(
                    "プロバイダ名",
                    value=provider.get("name", ""),
                    key=f"prov_name_{idx}",
                    help="モデルキーのプレフィックスになります（例: VeniceAI）",
                )
                new_base_url = st.text_input(
                    "ベースURL",
                    value=provider.get("base_url", ""),
                    key=f"prov_url_{idx}",
                    placeholder="https://api.venice.ai/api/v1",
                )
                new_api_key = st.text_input(
                    "APIキー",
                    value=provider.get("api_key", ""),
                    key=f"prov_key_{idx}",
                    type="password",
                    help="ベアラートークン。ローカルサーバーなど不要な場合は空欄。",
                )
                models_str = st.text_area(
                    "モデルID一覧（カンマ区切り）",
                    value=", ".join(provider.get("models", [])),
                    key=f"prov_models_{idx}",
                    placeholder="例: llama-3.3-70b, mistral-31-24b",
                    height=80,
                    help="このプロバイダで使用可能なモデルIDをカンマ区切りで入力します。",
                )

                col_upd, col_del = st.columns([3, 1])
                with col_upd:
                    if st.button(
                        "✅ 更新", key=f"prov_update_{idx}", use_container_width=True
                    ):
                        providers[idx] = {
                            "name": new_name.strip(),
                            "base_url": new_base_url.strip(),
                            "api_key": new_api_key,
                            "models": [
                                m.strip()
                                for m in models_str.replace("、", ",").split(",")
                                if m.strip()
                            ],
                        }
                        _save_providers_and_rerun(settings, providers)
                with col_del:
                    if st.button(
                        "🗑️ 削除", key=f"prov_delete_{idx}", use_container_width=True
                    ):
                        to_delete = idx

        if to_delete is not None:
            providers.pop(to_delete)
            _save_providers_and_rerun(settings, providers)
    else:
        st.info("プロバイダがまだ登録されていません。")

    # ---- add new provider ----
    with st.expander("➕ 新しいプロバイダを追加", expanded=False):
        new_name = st.text_input(
            "プロバイダ名 *",
            key="new_prov_name",
            placeholder="例: VeniceAI",
        )
        new_base_url = st.text_input(
            "ベースURL *",
            key="new_prov_url",
            placeholder="https://api.venice.ai/api/v1",
        )
        new_api_key = st.text_input(
            "APIキー",
            key="new_prov_key",
            type="password",
        )
        new_models_str = st.text_area(
            "モデルID一覧（カンマ区切り）",
            key="new_prov_models",
            placeholder="例: llama-3.3-70b, mistral-31-24b",
            height=80,
        )
        if st.button("➕ 追加", key="new_prov_add", use_container_width=True):
            if not new_name.strip():
                st.error("プロバイダ名は必須です。")
            elif not new_base_url.strip():
                st.error("ベースURLは必須です。")
            else:
                new_provider = {
                    "name": new_name.strip(),
                    "base_url": new_base_url.strip(),
                    "api_key": new_api_key,
                    "models": [
                        m.strip()
                        for m in new_models_str.replace("、", ",").split(",")
                        if m.strip()
                    ],
                }
                providers.append(new_provider)
                _save_providers_and_rerun(settings, providers)

    return {"llm_providers": providers}


def _save_providers_and_rerun(settings: dict, providers: list) -> None:
    """Persist updated providers list and force rerun."""
    updated = dict(settings)
    updated["llm_providers"] = providers
    if save_settings(updated):
        st.session_state.settings = updated
        for key in ("chat_initialized", "chat_manager", "chat_first_init"):
            st.session_state.pop(key, None)
        st.success("✅ プロバイダ設定を保存しました")
        st.rerun()
    else:
        st.error("❌ 保存に失敗しました")


# ---------------------------------------------------------------------------
# Original get_available_models kept as private alias for tests
# ---------------------------------------------------------------------------


def get_available_models():
    return _get_ollama_models()


# ---------------------------------------------------------------------------
# Render: LLM model selections
# ---------------------------------------------------------------------------


def render_llm_settings(
    settings: dict, all_model_options: list, ollama_models: list
) -> dict:
    st.subheader("🤖 LLMモデル設定")

    # --- Ollama base URL ---
    current_ollama_url = settings.get("ollama_base_url", "")
    resolved_ollama_url = get_ollama_base_url(settings)
    ollama_base_url = st.text_input(
        "Ollama ベースURL",
        value=current_ollama_url,
        placeholder=DEFAULT_OLLAMA_BASE_URL,
        help=(
            f"Ollama サーバーの接続先URL。空欄の場合はデフォルト "
            f"({DEFAULT_OLLAMA_BASE_URL}) を使用します。"
            f"環境変数 OLLAMA_URL でもオーバーライド可能です。"
        ),
        key="ollama_base_url_input",
    )
    st.caption(f"🔗 現在の接続先: `{resolved_ollama_url}`")

    st.markdown("---")

    if not all_model_options:
        st.warning(
            "利用可能なモデルが見つかりません。Ollamaサーバーへの接続またはプロバイダ設定を確認してください。"
        )

    st.info(
        f"**現在の設定**:\n"
        f"- Ollama接続先: {resolved_ollama_url}\n"
        f"- 検索語生成: {settings.get('search_model') or '(未設定)'}\n"
        f"- 回答生成: {settings.get('response_model') or '(未設定)'}\n"
        f"- 品質検証: {settings.get('eval_model') or '(未設定)'}\n"
        f"- 埋め込みモデル: {settings.get('embedding_model') or '(未設定)'}"
    )

    options = list(all_model_options)
    for key in ("search_model", "response_model", "eval_model"):
        val = settings.get(key, "")
        if val and val not in options:
            options.append(val)
    options = sorted(set(options))
    if not options:
        options = ["(モデルを入力)"]

    def _sel(label, setting_key, help_text, widget_key):
        default = settings.get(setting_key, "")
        idx = options.index(default) if default and default in options else 0
        return st.selectbox(
            label, options=options, index=idx, help=help_text, key=widget_key
        )

    search_model = _sel(
        "検索語生成モデル",
        "search_model",
        "Web検索のキーワード生成に使用するモデル",
        "search_model_select",
    )
    response_model = _sel(
        "回答生成モデル",
        "response_model",
        "ユーザーへの回答生成に使用するモデル",
        "response_model_select",
    )
    eval_model = _sel(
        "品質検証モデル",
        "eval_model",
        "回答の品質評価に使用するモデル（軽量モデル推奨）",
        "eval_model_select",
    )

    # Warn if an Ollama-style model name is not present in the actual Ollama list
    ollama_model_names = [m for m in all_model_options if MODEL_KEY_SEPARATOR not in m]
    for lbl, val in [
        ("検索語生成", search_model),
        ("回答生成", response_model),
        ("品質検証", eval_model),
    ]:
        if (
            val
            and MODEL_KEY_SEPARATOR not in val
            and ollama_model_names
            and val not in ollama_model_names
        ):
            st.warning(f"⚠️ {lbl}モデル '{val}' がOllamaに見つかりません。")

    st.markdown("---")
    st.markdown("**埋め込みモデル（リランカー用）**")
    st.caption(
        "検索結果の関連度スコアリングに使用します。Ollamaで利用可能な埋め込みモデルを指定してください。"
    )

    # Well-known embedding models to always show as options
    KNOWN_EMBED_MODELS = [
        "nomic-embed-text-v2-moe",
        "nomic-embed-text",
        "mxbai-embed-large",
        "all-minilm",
        "bge-m3",
        "snowflake-arctic-embed",
    ]
    embed_options = list(KNOWN_EMBED_MODELS)
    for m in ollama_models:
        if m not in embed_options:
            embed_options.append(m)
    current_embed = settings.get("embedding_model", "nomic-embed-text-v2-moe")
    if current_embed and current_embed not in embed_options:
        embed_options.insert(0, current_embed)

    embed_idx = (
        embed_options.index(current_embed) if current_embed in embed_options else 0
    )
    embedding_model = st.selectbox(
        "埋め込みモデル",
        options=embed_options,
        index=embed_idx,
        help="OllamaClient で使用する埋め込みモデル。`ollama pull <model>` で事前に取得してください。",
        key="embedding_model_select",
    )

    if embedding_model and ollama_models and embedding_model not in ollama_models:
        st.warning(
            f"⚠️ 埋め込みモデル '{embedding_model}' がOllamaに見つかりません。`ollama pull {embedding_model}` を実行してください。"
        )

    return {
        "search_model": search_model,
        "response_model": response_model,
        "eval_model": eval_model,
        "embedding_model": embedding_model,
        "ollama_base_url": ollama_base_url.strip(),
    }


# ---------------------------------------------------------------------------
# Render: UI settings
# ---------------------------------------------------------------------------


def render_ui_settings(settings: dict) -> dict:
    st.subheader("🎨 UI設定")
    size_options = ["small", "medium", "large"]
    size_labels = {"small": "小 (0.9倍)", "medium": "中 (標準)", "large": "大 (1.1倍)"}
    current = settings.get("ui_text_size", "medium")
    idx = size_options.index(current) if current in size_options else 1
    selected = st.selectbox(
        "文字サイズ",
        options=size_options,
        index=idx,
        format_func=lambda x: size_labels[x],
        help="全ページの文字サイズを変更します",
        key="ui_text_size_select",
    )
    return {"ui_text_size": selected}


# ---------------------------------------------------------------------------
# Render: SearXNG
# ---------------------------------------------------------------------------


def render_searxng_settings(settings: dict) -> dict:
    st.subheader("🔍 SearXNG検索設定")
    st.info(
        f"**現在の設定**:\n"
        f"- 検索エンジン: {settings.get('searxng_engine', 'general')}\n"
        f"- 言語: {settings.get('searxng_lang', 'ja')}\n"
        f"- セーフサーチ: {settings.get('searxng_safesearch', 'off')}"
    )

    engine_options = ["general", "news", "science", "images", "カスタム"]
    current_engine = settings.get("searxng_engine", "general")
    is_custom = current_engine not in ["general", "news", "science", "images"]
    engine_idx = (
        engine_options.index("カスタム")
        if is_custom
        else engine_options.index(current_engine)
    )
    sel_engine_opt = st.selectbox(
        "検索エンジン",
        options=engine_options,
        index=engine_idx,
        help="SearXNGで使用する検索エンジンカテゴリ",
        key="searxng_engine_select",
    )
    sel_engine = sel_engine_opt
    if sel_engine_opt == "カスタム":
        sel_engine = st.text_input(
            "カスタムエンジン名",
            value=current_engine if is_custom else "",
            placeholder="例: duckduckgo, google, bing",
            help="SearXNGでサポートされているエンジン名を入力",
            key="custom_engine_input",
        )

    lang_options = ["ja", "en"]
    cur_lang = settings.get("searxng_lang", "ja")
    lang_idx = lang_options.index(cur_lang) if cur_lang in lang_options else 0
    sel_lang = st.selectbox(
        "検索言語", options=lang_options, index=lang_idx, key="searxng_lang_select"
    )

    safe_options = ["off", "moderate", "on"]
    cur_safe = settings.get("searxng_safesearch", "off")
    safe_idx = safe_options.index(cur_safe) if cur_safe in safe_options else 0
    sel_safe = st.selectbox(
        "セーフサーチ",
        options=safe_options,
        index=safe_idx,
        key="searxng_safesearch_select",
    )

    return {
        "searxng_engine": sel_engine,
        "searxng_lang": sel_lang,
        "searxng_safesearch": sel_safe,
        "is_custom_engine": sel_engine_opt == "カスタム",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Settings - Researcher", page_icon="⚙️", layout="wide")

    from researcher.utils.page_utils import apply_text_size_css

    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()

    apply_text_size_css(st.session_state.settings.get("ui_text_size", "medium"))
    render_sidebar()

    st.title("⚙️ 設定")
    st.markdown(
        "このページでは Researcher の設定を管理できます。"
        "設定は `~/.researcher/settings.json` に保存され、"
        "次回の Chat 初期化時に反映されます。"
    )
    st.divider()

    settings = st.session_state.settings

    # --- Provider management (saved immediately on add/update/delete) ---
    provider_result = render_provider_settings(settings)
    settings = {**settings, **provider_result}

    st.divider()

    # --- LLM model selectors ---
    ollama_models = _get_ollama_models(settings)
    all_model_options = _build_all_model_options(settings, ollama_models)
    llm_selections = render_llm_settings(settings, all_model_options, ollama_models)

    st.divider()

    # --- SearXNG ---
    searxng_selections = render_searxng_settings(settings)

    st.divider()

    # --- UI appearance ---
    ui_selections = render_ui_settings(settings)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        save_button = st.button(
            "💾 設定を保存",
            type="primary",
            use_container_width=True,
            key="save_settings_button",
        )
    with col2:
        reset_button = st.button(
            "🔄 デフォルトに戻す", use_container_width=True, key="reset_settings_button"
        )

    if save_button:
        if (
            searxng_selections["is_custom_engine"]
            and not searxng_selections["searxng_engine"].strip()
        ):
            st.warning("カスタムエンジン名を入力してください")
        else:
            new_settings = {
                **llm_selections,
                "searxng_engine": searxng_selections["searxng_engine"],
                "searxng_lang": searxng_selections["searxng_lang"],
                "searxng_safesearch": searxng_selections["searxng_safesearch"],
                "ui_text_size": ui_selections["ui_text_size"],
                "llm_providers": settings.get("llm_providers", []),
            }
            if save_settings(new_settings):
                st.session_state.settings = new_settings
                for key in ("chat_initialized", "chat_manager", "chat_first_init"):
                    st.session_state.pop(key, None)
                st.success("✅ 設定を保存しました")
                st.rerun()
            else:
                st.error("❌ 設定の保存に失敗しました")

    if reset_button:
        if save_settings(DEFAULT_SETTINGS):
            st.session_state.settings = dict(DEFAULT_SETTINGS)
            for key in ("chat_initialized", "chat_manager", "chat_first_init"):
                st.session_state.pop(key, None)
            st.success("✅ 設定をデフォルトに戻しました")
            st.rerun()
        else:
            st.error("❌ 設定のリセットに失敗しました")


if __name__ == "__main__":
    main()
