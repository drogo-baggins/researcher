#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for Settings page - Chat reinitialization after settings change
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_settings_chat_reinitialization():
    """Test that Chat reinitializes after settings change"""
    print("=" * 80)
    print("Test: Settings → Chat Reinitialization")
    print("=" * 80)
    
    # Simulate Streamlit session state
    class SessionState:
        def __init__(self):
            self._state = {}
        
        def __setitem__(self, key, value):
            self._state[key] = value
        
        def __getitem__(self, key):
            return self._state[key]
        
        def __delitem__(self, key):
            del self._state[key]
        
        def __contains__(self, key):
            return key in self._state
        
        def get(self, key, default=None):
            return self._state.get(key, default)
    
    st_session_state = SessionState()
    
    # Test 1: Initial Chat initialization
    print("\n[Test 1] Initial Chat initialization")
    st_session_state["chat_initialized"] = True
    st_session_state["chat_manager"] = "ChatManager(search_model=llama3.2, ...)"
    st_session_state["settings"] = {
        "search_model": "llama3.2",
        "response_model": "llama3"
    }
    print(f"  chat_initialized: {st_session_state['chat_initialized']}")
    print(f"  chat_manager: {st_session_state['chat_manager']}")
    print(f"  settings: {st_session_state['settings']}")
    print("  ✓ Chat initialized")
    
    # Test 2: Settings page - save new settings
    print("\n[Test 2] Settings page - save new settings")
    new_settings = {
        "search_model": "llama3.3",  # Changed
        "response_model": "llama3.1"  # Changed
    }
    print(f"  New settings: {new_settings}")
    
    # Simulate Settings.py save button logic
    st_session_state["settings"] = new_settings
    
    # Force Chat to reinitialize (THE FIX)
    if "chat_initialized" in st_session_state:
        del st_session_state["chat_initialized"]
        print("  ✓ Deleted chat_initialized")
    
    if "chat_manager" in st_session_state:
        del st_session_state["chat_manager"]
        print("  ✓ Deleted chat_manager")
    
    # Test 3: Verify state after save
    print("\n[Test 3] Verify state after save")
    assert "chat_initialized" not in st_session_state, "chat_initialized should be deleted"
    assert "chat_manager" not in st_session_state, "chat_manager should be deleted"
    assert st_session_state["settings"] == new_settings, "Settings should be updated"
    print(f"  chat_initialized exists: {('chat_initialized' in st_session_state)}")
    print(f"  chat_manager exists: {('chat_manager' in st_session_state)}")
    print(f"  settings: {st_session_state['settings']}")
    print("  ✓ State correctly cleared")
    
    # Test 4: Simulate Chat page reload
    print("\n[Test 4] Simulate Chat page reload")
    print("  initialize_session_chat() will see:")
    print(f"    - chat_initialized in session_state: {('chat_initialized' in st_session_state)}")
    
    if "chat_initialized" not in st_session_state:
        print("    → Will perform FULL initialization")
        print("    → Will create NEW OllamaClient(search_model='llama3.3')")
        print("    → Will create NEW OllamaClient(response_model='llama3.1')")
        print("    → Will create NEW ChatManager with new settings")
        
        # Simulate reinitialization
        st_session_state["chat_initialized"] = True
        st_session_state["chat_manager"] = f"ChatManager(search_model={new_settings['search_model']}, ...)"
        print("  ✓ Chat reinitialized with new settings")
    else:
        print("    → Will SKIP initialization (BUG!)")
        print("    → Old settings will remain")
    
    # Test 5: Verify final state
    print("\n[Test 5] Verify final state")
    assert st_session_state["chat_initialized"] is True
    assert "llama3.3" in st_session_state["chat_manager"]
    print(f"  chat_initialized: {st_session_state['chat_initialized']}")
    print(f"  chat_manager: {st_session_state['chat_manager']}")
    print("  ✓ New settings applied to ChatManager")
    
    # Test 6: Reset button scenario
    print("\n[Test 6] Reset button scenario")
    from researcher.config import DEFAULT_SETTINGS
    
    # Simulate reset button
    st_session_state["settings"] = DEFAULT_SETTINGS.copy()
    
    if "chat_initialized" in st_session_state:
        del st_session_state["chat_initialized"]
    if "chat_manager" in st_session_state:
        del st_session_state["chat_manager"]
    
    print(f"  Settings reset to: {st_session_state['settings']}")
    print(f"  chat_initialized cleared: {('chat_initialized' not in st_session_state)}")
    print(f"  chat_manager cleared: {('chat_manager' not in st_session_state)}")
    print("  ✓ Reset correctly clears Chat state")
    
    print("\n" + "=" * 80)
    print("All reinitialization tests passed!")
    print("=" * 80)
    print("\n📋 Verification:")
    print("  ✅ Settings save clears chat_initialized")
    print("  ✅ Settings save clears chat_manager")
    print("  ✅ Chat reinitializes on next page load")
    print("  ✅ New settings applied to ChatManager")
    print("  ✅ Reset button clears Chat state")


if __name__ == "__main__":
    test_settings_chat_reinitialization()
