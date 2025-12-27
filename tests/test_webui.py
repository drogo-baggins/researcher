"""
Unit tests for Chat Page (pages/1_💬_Chat.py).

Tests verify Chat-specific functionality:
- render_chat() with evaluation metrics
- render_minimal_sidebar() settings
- render_feedback_buttons() interactions
- auto_save_session() logic
- load_session_helper() from shared_utils

Group/session management tests are in tests/e2e/test_webui_groups.py.
"""

import pytest
import sys
import importlib
from pathlib import Path
from unittest.mock import Mock, MagicMock
from types import ModuleType

# Setup import paths
pages_dir = Path(__file__).parent.parent / "src" / "researcher" / "pages"
researcher_dir = Path(__file__).parent.parent / "src" / "researcher"
src_dir = Path(__file__).parent.parent / "src"

for dir_path in [str(pages_dir), str(researcher_dir), str(src_dir)]:
    if dir_path not in sys.path:
        sys.path.insert(0, dir_path)

# Create mock pages module for imports
pages_module = ModuleType('pages')
shared_utils_module = importlib.import_module("shared_utils")
pages_module.shared_utils = shared_utils_module
sys.modules['pages'] = pages_module
sys.modules['pages.shared_utils'] = shared_utils_module

# Import Chat module
chat_module = importlib.import_module("1_💬_Chat")


def create_mock_columns(n):
    """Create mock columns that work with 'with' statement."""
    cols = []
    for _ in range(n):
        col = MagicMock()
        col.__enter__ = Mock(return_value=col)
        col.__exit__ = Mock(return_value=None)
        cols.append(col)
    return cols


# ============================================================
# Chat Rendering Tests
# ============================================================


def test_render_chat_displays_embedded_evaluation(monkeypatch):
    """Verify render_chat shows evaluation metrics from message.evaluation."""
    mock_st = Mock()
    monkeypatch.setattr(chat_module, 'st', mock_st)
    
    messages = [
        {"role": "user", "content": "What is AI?"},
        {
            "role": "assistant",
            "content": "AI is...",
            "evaluation": {
                "accuracy_score": 0.88,
                "freshness_score": 0.85,
                "overall_score": 0.87,
                "reasoning": "Good answer"
            }
        }
    ]
    
    mock_session_state = Mock()
    mock_session_state.messages = messages
    mock_session_state.chat_manager = Mock()
    mock_session_state.session_manager = Mock()
    mock_session_state.current_session_id = 1
    mock_session_state.model = "gpt-oss:20b"
    mock_session_state.language = "ja"
    mock_session_state.get = Mock(return_value=None)
    mock_session_state.__setitem__ = Mock()
    
    mock_st.session_state = mock_session_state
    mock_st.chat_message = MagicMock()
    mock_st.markdown = Mock()
    mock_st.columns = Mock(return_value=create_mock_columns(3))
    mock_st.metric = Mock()
    mock_st.expander = MagicMock()
    mock_st.button = Mock(return_value=False)
    
    chat_module.render_chat()
    
    # Verify metric was called for scores
    assert mock_st.metric.call_count >= 3, "Should display 3+ evaluation metrics"


def test_render_chat_uses_fallback_evaluation(monkeypatch):
    """Verify render_chat falls back to chat_manager.get_last_evaluation_score()."""
    mock_st = Mock()
    monkeypatch.setattr(chat_module, 'st', mock_st)
    
    messages = [
        {"role": "user", "content": "Test"},
        {"role": "assistant", "content": "Answer"}  # No evaluation field
    ]
    
    mock_cm = Mock()
    mock_cm.get_last_evaluation_score.return_value = {
        "accuracy_score": 0.90,
        "freshness_score": 0.85,
        "overall_score": 0.88
    }
    
    mock_session_state = Mock()
    mock_session_state.messages = messages
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = Mock()
    mock_session_state.current_session_id = 1
    mock_session_state.model = "gpt-oss:20b"
    mock_session_state.language = "ja"
    mock_session_state.get = Mock(return_value=None)
    mock_session_state.__setitem__ = Mock()
    
    mock_st.session_state = mock_session_state
    mock_st.chat_message = MagicMock()
    mock_st.markdown = Mock()
    mock_st.columns = Mock(return_value=create_mock_columns(3))
    mock_st.metric = Mock()
    mock_st.expander = MagicMock()
    mock_st.button = Mock(return_value=False)
    
    chat_module.render_chat()
    
    # Verify fallback was called
    mock_cm.get_last_evaluation_score.assert_called()
    assert mock_st.metric.call_count >= 3


# ============================================================
# Minimal Sidebar Tests
# ============================================================


def test_render_minimal_sidebar_shows_model_selector(monkeypatch):
    """Verify minimal sidebar displays model dropdown."""
    mock_st = Mock()
    monkeypatch.setattr(chat_module, 'st', mock_st)
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(side_effect=lambda key, default=None: {
        "available_models": ["gpt-oss:20b", "llama2:7b"],
        "model": "gpt-oss:20b",
        "language": "ja",
        "auto_search_enabled": False
    }.get(key, default))
    mock_session_state.__setitem__ = Mock()
    
    mock_cm = Mock()
    mock_cm.ollama_client.test_connection.return_value = True
    mock_cm.searxng_client.test_connection.return_value = True
    mock_session_state.chat_manager = mock_cm
    
    mock_st.session_state = mock_session_state
    mock_st.sidebar = MagicMock()
    mock_st.title = Mock()
    mock_st.subheader = Mock()
    mock_st.selectbox = Mock(return_value="gpt-oss:20b")
    mock_st.checkbox = Mock(return_value=False)
    mock_st.divider = Mock()
    mock_st.metric = Mock()
    mock_st.page_link = Mock()
    
    chat_module.render_minimal_sidebar()
    
    # Verify selectbox was called
    assert mock_st.selectbox.called, "Should display model selector"


def test_render_minimal_sidebar_shows_connection_status(monkeypatch):
    """Verify minimal sidebar displays Ollama/SearxNG connection status."""
    mock_st = Mock()
    monkeypatch.setattr(chat_module, 'st', mock_st)
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(side_effect=lambda key, default=None: {
        "available_models": ["gpt-oss:20b"],
        "model": "gpt-oss:20b",
        "language": "ja"
    }.get(key, default))
    mock_session_state.__setitem__ = Mock()
    
    mock_cm = Mock()
    mock_cm.ollama_client.test_connection.return_value = True
    mock_cm.searxng_client.test_connection.return_value = False
    mock_session_state.chat_manager = mock_cm
    
    mock_st.session_state = mock_session_state
    mock_st.sidebar = MagicMock()
    mock_st.title = Mock()
    mock_st.subheader = Mock()
    mock_st.selectbox = Mock(return_value="gpt-oss:20b")
    mock_st.checkbox = Mock(return_value=False)
    mock_st.divider = Mock()
    mock_st.metric = Mock()
    mock_st.page_link = Mock()
    
    chat_module.render_minimal_sidebar()
    
    # Verify connection checks
    mock_cm.ollama_client.test_connection.assert_called()
    mock_cm.searxng_client.test_connection.assert_called()
    assert mock_st.metric.call_count >= 2, "Should show 2+ connection metrics"


# ============================================================
# Feedback Buttons Tests
# ============================================================


def test_render_feedback_buttons_saves_upvote(monkeypatch):
    """Verify 👍 button saves positive feedback."""
    mock_st = Mock()
    mock_save_feedback = Mock(return_value=True)
    
    monkeypatch.setattr(chat_module, 'st', mock_st)
    monkeypatch.setattr(chat_module, 'save_feedback', mock_save_feedback)
    
    mock_session_state = Mock()
    mock_cm = Mock()
    mock_cm.get_current_model.return_value = "gpt-oss:20b"
    mock_session_state.chat_manager = mock_cm
    mock_session_state.current_session_id = 1
    
    mock_st.session_state = mock_session_state
    mock_st.columns = Mock(return_value=create_mock_columns(3))
    mock_st.button = Mock(side_effect=[True, False])  # First button clicked
    mock_st.success = Mock()
    
    chat_module.render_feedback_buttons(0, "Question", "Answer")
    
    # Verify save was called with "up"
    mock_save_feedback.assert_called_once_with("Question", "Answer", "up", "gpt-oss:20b", 1)
    mock_st.success.assert_called_once()


def test_render_feedback_buttons_saves_downvote(monkeypatch):
    """Verify 👎 button saves negative feedback."""
    mock_st = Mock()
    mock_save_feedback = Mock(return_value=True)
    
    monkeypatch.setattr(chat_module, 'st', mock_st)
    monkeypatch.setattr(chat_module, 'save_feedback', mock_save_feedback)
    
    mock_session_state = Mock()
    mock_cm = Mock()
    mock_cm.get_current_model.return_value = "llama2:7b"
    mock_session_state.chat_manager = mock_cm
    mock_session_state.current_session_id = 2
    
    mock_st.session_state = mock_session_state
    mock_st.columns = Mock(return_value=create_mock_columns(3))
    mock_st.button = Mock(side_effect=[False, True])  # Second button clicked
    mock_st.success = Mock()
    
    chat_module.render_feedback_buttons(1, "Q", "A")
    
    # Verify save was called with "down"
    mock_save_feedback.assert_called_once_with("Q", "A", "down", "llama2:7b", 2)
    mock_st.success.assert_called_once()


# ============================================================
# Auto Save Session Tests
# ============================================================


def test_auto_save_session_creates_new_session(monkeypatch):
    """Verify auto_save creates session when current_session_id is None."""
    mock_st = Mock()
    monkeypatch.setattr(chat_module, 'st', mock_st)
    
    mock_session_manager = Mock()
    mock_session_manager.create_session.return_value = 10
    
    mock_session_state = Mock()
    mock_session_state.current_session_id = None
    mock_session_state.session_manager = mock_session_manager
    mock_session_state.get = Mock(side_effect=lambda key, default=None: {
        "language": "ja"
    }.get(key, default))
    mock_session_state.__setitem__ = Mock()
    
    mock_st.session_state = mock_session_state
    
    messages = [{"role": "user", "content": "New"}]
    mock_cm = Mock()
    
    result = chat_module.auto_save_session("New", messages, mock_cm)
    
    # Verify create was called
    mock_session_manager.create_session.assert_called_once()
    assert result is True


def test_auto_save_session_updates_existing_session(monkeypatch):
    """Verify auto_save updates session when current_session_id exists."""
    mock_st = Mock()
    monkeypatch.setattr(chat_module, 'st', mock_st)
    
    mock_session_manager = Mock()
    mock_session_manager.save_session.return_value = True
    
    mock_session_state = Mock()
    mock_session_state.current_session_id = 5
    mock_session_state.session_manager = mock_session_manager
    mock_session_state.get = Mock(side_effect=lambda key, default=None: {
        "language": "ja"
    }.get(key, default))
    mock_session_state.__setitem__ = Mock()
    
    mock_st.session_state = mock_session_state
    
    messages = [{"role": "user", "content": "Update"}]
    mock_cm = Mock()
    
    result = chat_module.auto_save_session("Update", messages, mock_cm)
    
    # Verify save was called
    mock_session_manager.save_session.assert_called_once()
    assert result is True


# ============================================================
# Load Session Helper Tests (from shared_utils)
# ============================================================


def test_load_session_helper_triggers_rerun(monkeypatch):
    """Verify load_session_helper calls st.rerun() by default."""
    mock_st = Mock()
    monkeypatch.setattr(shared_utils_module, 'st', mock_st)
    
    mock_session_manager = Mock()
    mock_session_manager.load_session.return_value = {
        "messages": [{"role": "user", "content": "Loaded"}],
        "model": "gpt-oss:20b",
        "search_results": []
    }
    
    mock_cm = Mock()
    mock_cm.clear_history = Mock()
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(return_value=[])
    mock_session_state.__setitem__ = Mock()
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = mock_session_manager
    
    mock_st.session_state = mock_session_state
    mock_st.error = Mock()
    mock_st.rerun = Mock()
    
    shared_utils_module.load_session_helper(10, "Test", trigger_rerun=True)
    
    # Verify rerun was called
    mock_st.rerun.assert_called_once()


def test_load_session_helper_no_rerun_when_disabled(monkeypatch):
    """Verify load_session_helper skips st.rerun() when trigger_rerun=False."""
    mock_st = Mock()
    monkeypatch.setattr(shared_utils_module, 'st', mock_st)
    
    mock_session_manager = Mock()
    mock_session_manager.load_session.return_value = {
        "messages": [],
        "model": "gpt-oss:20b",
        "search_results": []
    }
    
    mock_cm = Mock()
    mock_cm.clear_history = Mock()
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(return_value=[])
    mock_session_state.__setitem__ = Mock()
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = mock_session_manager
    
    mock_st.session_state = mock_session_state
    mock_st.error = Mock()
    mock_st.rerun = Mock()
    
    shared_utils_module.load_session_helper(20, "No Rerun", trigger_rerun=False)
    
    # Verify rerun was NOT called
    mock_st.rerun.assert_not_called()


def test_load_session_helper_handles_load_failure(monkeypatch):
    """Verify load_session_helper shows error on exception."""
    mock_st = Mock()
    monkeypatch.setattr(shared_utils_module, 'st', mock_st)
    
    mock_session_manager = Mock()
    mock_session_manager.load_session.side_effect = Exception("DB error")
    
    mock_cm = Mock()
    mock_cm.clear_history = Mock()
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(return_value=[])
    mock_session_state.__setitem__ = Mock()
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = mock_session_manager
    
    mock_cm.messages = []
    
    mock_st.session_state = mock_session_state
    mock_st.error = Mock()
    mock_st.rerun = Mock()
    
    shared_utils_module.load_session_helper(99, "Failed")
    
    # Verify error was shown
    mock_st.error.assert_called()
    # Verify rerun was NOT called
    mock_st.rerun.assert_not_called()

def test_load_session_helper_deepcopy_failure(monkeypatch):
    """Verify load_session_helper handles deepcopy failures gracefully."""
    mock_st = Mock()
    monkeypatch.setattr(shared_utils_module, 'st', mock_st)
    
    # Mock deepcopy to raise exception
    original_deepcopy = shared_utils_module.copy.deepcopy
    call_count = [0]
    
    def mock_deepcopy(obj):
        call_count[0] += 1
        # Fail on first few calls (backup), but allow later ones
        if call_count[0] <= 2:
            raise TypeError("Cannot deepcopy object")
        return original_deepcopy(obj)
    
    monkeypatch.setattr(shared_utils_module.copy, 'deepcopy', mock_deepcopy)
    
    mock_session_manager = Mock()
    mock_session_manager.load_session.return_value = {
        "exchanges": [
            {
                "user_message": "Test",
                "assistant_message": "Response",
                "model": "gpt-oss:20b",
                "language": "ja",
                "search_results": None,
                "evaluation_score": None
            }
        ],
        "tags": []
    }
    
    mock_cm = Mock()
    mock_cm.clear_history = Mock()
    mock_cm.messages = []
    mock_cm.language = "ja"
    mock_cm.ollama_client = Mock()
    mock_cm.ollama_client.model = "gpt-oss:20b"
    mock_cm.reranker = Mock()
    mock_cm.reranker.ollama_client = Mock()
    mock_cm.reranker.ollama_client.model = "gpt-oss:20b"
    mock_cm.agent = None
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(return_value=[])
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = mock_session_manager
    
    mock_st.session_state = mock_session_state
    mock_st.error = Mock()
    mock_st.rerun = Mock()
    
    # Should not raise exception, should use fallback
    shared_utils_module.load_session_helper(1, "Test", trigger_rerun=False)
    
    # Verify session was loaded despite deepcopy failure
    assert mock_st.error.call_count == 0
    # Verify state was updated (fallback worked)
    assert mock_session_state.current_session_id == 1


def test_load_session_helper_old_session_format(monkeypatch):
    """Verify load_session_helper handles V2 schema (exchanges)."""
    mock_st = Mock()
    monkeypatch.setattr(shared_utils_module, 'st', mock_st)
    
    mock_session_manager = Mock()
    # V2 session format: exchanges instead of history
    mock_session_manager.load_session.return_value = {
        "exchanges": [
            {
                "user_message": "Old session",
                "assistant_message": "Response",
                "model": "gpt-oss:20b",
                "language": "ja",
                "search_results": None,
                "evaluation_score": None
            }
        ],
        "tags": []
    }
    
    mock_cm = Mock()
    mock_cm.clear_history = Mock()
    mock_cm.messages = []
    mock_cm.language = "ja"
    mock_cm.ollama_client = Mock()
    mock_cm.ollama_client.model = "gpt-oss:20b"
    mock_cm.reranker = Mock()
    mock_cm.reranker.ollama_client = Mock()
    mock_cm.reranker.ollama_client.model = "gpt-oss:20b"
    mock_cm.agent = None
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(return_value=[])
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = mock_session_manager
    
    mock_st.session_state = mock_session_state
    mock_st.error = Mock()
    mock_st.rerun = Mock()
    
    # Should load successfully
    shared_utils_module.load_session_helper(1, "Old Session", trigger_rerun=False)
    
    # Verify no errors
    mock_st.error.assert_not_called()
    # Verify state was updated
    assert mock_session_state.current_session_id == 1


def test_load_session_helper_trace_logging(monkeypatch, caplog):
    """Verify load_session_helper outputs trace logs at each step."""
    import logging
    caplog.set_level(logging.INFO)
    
    mock_st = Mock()
    monkeypatch.setattr(shared_utils_module, 'st', mock_st)
    
    mock_session_manager = Mock()
    mock_session_manager.load_session.return_value = {
        "exchanges": [
            {
                "user_message": "Test",
                "assistant_message": "Response",
                "model": "gpt-oss:20b",
                "language": "ja",
                "search_results": [{"title": "Test result"}],
                "evaluation_score": None
            }
        ],
        "tags": ["test"]
    }
    
    mock_cm = Mock()
    mock_cm.clear_history = Mock()
    mock_cm.messages = []
    mock_cm.language = "ja"
    mock_cm.ollama_client = Mock()
    mock_cm.ollama_client.model = "gpt-oss:20b"
    mock_cm.reranker = Mock()
    mock_cm.reranker.ollama_client = Mock()
    mock_cm.reranker.ollama_client.model = "gpt-oss:20b"
    mock_cm.agent = None
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(return_value=[])
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = mock_session_manager
    
    mock_st.session_state = mock_session_state
    mock_st.error = Mock()
    mock_st.rerun = Mock()
    
    # Execute load
    shared_utils_module.load_session_helper(1, "Test Session", trigger_rerun=False)
    
    # Verify trace logs were output
    log_text = caplog.text
    assert "[TRACE] load_session_helper started" in log_text
    assert "[TRACE] Clearing ChatManager state" in log_text
    assert "[TRACE] Loading session from database" in log_text
    assert "[TRACE] Session loaded successfully" in log_text
    assert "[TRACE] Extracting session data" in log_text
    assert "[TRACE] Updating session_state" in log_text
    assert "[TRACE] Syncing ChatManager" in log_text
    assert "[TRACE] load_session_helper completed successfully" in log_text


def test_load_session_helper_extract_failure_dumps_session_data(monkeypatch, caplog):
    """Verify session_data is dumped to logs on extract failure."""
    import logging
    caplog.set_level(logging.ERROR)
    
    mock_st = Mock()
    monkeypatch.setattr(shared_utils_module, 'st', mock_st)
    
    # Return session_data with malformed structure that will cause extraction to fail
    mock_session_manager = Mock()
    mock_session_manager.load_session.return_value = {
        "history": "invalid_not_a_list",  # This should cause an error
        "model": "gpt-oss:20b"
    }
    
    mock_cm = Mock()
    mock_cm.clear_history = Mock()
    mock_cm.messages = []
    
    mock_session_state = Mock()
    mock_session_state.get = Mock(return_value=[])
    mock_session_state.chat_manager = mock_cm
    mock_session_state.session_manager = mock_session_manager
    
    mock_st.session_state = mock_session_state
    mock_st.error = Mock()
    mock_st.rerun = Mock()
    
    # Execute load (should fail during extraction)
    shared_utils_module.load_session_helper(1, "Bad Session", trigger_rerun=False)
    
    # Verify error was shown
    mock_st.error.assert_called()
    
    # Verify session_data dump or keys were logged
    log_text = caplog.text
    assert ("[DEBUG] Session data dump" in log_text or 
            "[DEBUG] Session data keys" in log_text)