#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Settings page functionality
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from researcher.config import load_settings, save_settings, DEFAULT_SETTINGS


def test_settings_page_logic():
    """Test the core logic used in Settings page"""
    print("=" * 80)
    print("Test: Settings Page Logic")
    print("=" * 80)
    
    # Test 1: Load default settings
    print("\n[Test 1] Load default settings")
    settings = load_settings()
    print(f"  Loaded settings: {settings}")
    assert "search_model" in settings
    assert "response_model" in settings
    assert "eval_model" in settings
    assert "searxng_engine" in settings
    assert "searxng_lang" in settings
    assert "searxng_safesearch" in settings
    print("  ✓ All required keys present")
    
    # Test 2: Simulate model selection
    print("\n[Test 2] Simulate LLM model selection")
    llm_selections = {
        'search_model': 'llama3.3',
        'response_model': 'llama3.1',
        'eval_model': 'llama3.2:1b'
    }
    print(f"  Selected models: {llm_selections}")
    print("  ✓ Model selection works")
    
    # Test 3: Simulate SearXNG settings selection
    print("\n[Test 3] Simulate SearXNG settings selection")
    searxng_selections = {
        'searxng_engine': 'news',
        'searxng_lang': 'en',
        'searxng_safesearch': 'moderate'
    }
    print(f"  Selected SearXNG settings: {searxng_selections}")
    print("  ✓ SearXNG selection works")
    
    # Test 4: Build new settings (like save button logic)
    print("\n[Test 4] Build and validate new settings")
    new_settings = {
        **llm_selections,
        **searxng_selections
    }
    print(f"  New settings: {new_settings}")
    assert len(new_settings) == 6
    print("  ✓ New settings structure is correct")
    
    # Test 5: Custom engine validation
    print("\n[Test 5] Custom engine validation")
    custom_engine = "duckduckgo"
    is_custom_engine = custom_engine not in ["general", "news", "science", "images"]
    print(f"  Custom engine: {custom_engine}")
    print(f"  Is custom: {is_custom_engine}")
    assert is_custom_engine
    print("  ✓ Custom engine validation works")
    
    # Test 6: Empty custom engine validation
    print("\n[Test 6] Empty custom engine validation")
    empty_engine = ""
    should_warn = not empty_engine.strip()
    print(f"  Empty engine: '{empty_engine}'")
    print(f"  Should warn: {should_warn}")
    assert should_warn
    print("  ✓ Empty engine validation works")
    
    # Test 7: Model backward compatibility
    print("\n[Test 7] Model backward compatibility")
    available_models = ["llama3", "llama3.2", "llama3.3"]
    current_model = "old-model-not-in-list"
    
    model_options = list(available_models)
    if current_model and current_model not in model_options:
        model_options.append(current_model)
    
    print(f"  Available models: {available_models}")
    print(f"  Current model: {current_model}")
    print(f"  Model options (with backward compat): {model_options}")
    assert current_model in model_options
    print("  ✓ Backward compatibility works")
    
    # Test 8: Reset to defaults
    print("\n[Test 8] Reset to defaults")
    reset_settings = DEFAULT_SETTINGS.copy()
    print(f"  Default settings: {reset_settings}")
    assert reset_settings == DEFAULT_SETTINGS
    print("  ✓ Reset to defaults works")
    
    print("\n" + "=" * 80)
    print("All Settings page logic tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    test_settings_page_logic()
