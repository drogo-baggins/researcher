#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for settings functionality
"""
import tempfile
from pathlib import Path
from unittest.mock import patch
import json

# Test load and save settings
def test_settings_integration():
    """Test that settings can be loaded and saved correctly"""
    from researcher.config import load_settings, save_settings, DEFAULT_SETTINGS
    
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.json"
        
        with patch("researcher.config.SETTINGS_FILE_PATH", settings_path):
            # Test 1: Load default settings when file doesn't exist
            print("[Test 1] Load default settings")
            settings = load_settings()
            print(f"  Loaded settings: {settings}")
            assert settings == DEFAULT_SETTINGS
            print("  ✓ Default settings loaded correctly")
            
            # Test 2: Save custom settings
            print("\n[Test 2] Save custom settings")
            custom_settings = {
                "search_model": "llama3.3",
                "response_model": "llama3.1",
                "eval_model": "llama3.2:1b",
                "searxng_engine": "news",
                "searxng_lang": "en",
                "searxng_safesearch": "strict",
                "ui_text_size": "medium",
                "llm_providers": [],
            }
            success = save_settings(custom_settings)
            assert success is True
            print("  ✓ Custom settings saved successfully")
            
            # Test 3: Load custom settings
            print("\n[Test 3] Load custom settings")
            loaded = load_settings()
            print(f"  Loaded settings: {loaded}")
            assert loaded == custom_settings
            print("  ✓ Custom settings loaded correctly")
            
            # Test 4: Partial update (only change one field)
            print("\n[Test 4] Partial update")
            partial_settings = {
                "search_model": "custom-model",
                "response_model": "llama3.1",
                "eval_model": "llama3.2:1b",
                "searxng_engine": "news",
                "searxng_lang": "en",
                "searxng_safesearch": "strict",
                "ui_text_size": "medium",
                "llm_providers": [],
            }
            save_settings(partial_settings)
            loaded = load_settings()
            assert loaded["search_model"] == "custom-model"
            assert loaded["response_model"] == "llama3.1"
            print("  ✓ Partial update works correctly")
            
            # Test 5: Verify file structure
            print("\n[Test 5] Verify file structure")
            with open(settings_path, "r", encoding="utf-8") as f:
                file_content = json.load(f)
            print(f"  File content: {json.dumps(file_content, indent=2)}")
            assert "search_model" in file_content
            assert "response_model" in file_content
            assert "eval_model" in file_content
            print("  ✓ File structure is correct")
            
    print("\n" + "=" * 80)
    print("All integration tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    test_settings_integration()
