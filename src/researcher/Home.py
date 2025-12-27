"""
Streamlit Home Page for Researcher - Entry point for multipage application.

This module provides the main entry point and session initialization for
the Researcher web application.
"""

import logging
import streamlit as st
from researcher.utils.page_utils import initialize_session

LOGGER = logging.getLogger(__name__)


def main():
    """Main entry point for the Streamlit application."""
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
    
    # Welcome UI
    st.title("🔍 Researcher")
    st.markdown("*ローカルAIリサーチャー - Ollama + SearXNG*")
    st.markdown("---")
    
    st.subheader("📖 使い方")
    st.markdown("""
    - **💬 Chat**: LLMとの会話応酬を行います
    - **📚 History**: 過去のセッション/グループを管理します
    - **⚙️ 設定**: LLMモデルとSearXNG検索パラメータを設定します
    """)
    
    # Navigation buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        st.page_link("pages/1_💬_Chat.py", label="💬 チャットを開始", use_container_width=True)
    with col2:
        st.page_link("pages/2_📚_History.py", label="📚 履歴を表示", use_container_width=True)
    with col3:
        st.page_link("pages/3_⚙️_Settings.py", label="⚙️ 設定", use_container_width=True)


if __name__ == "__main__":
    main()
