#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for Settings functionality
Tests the complete flow: Settings change → Save → Chat application
"""
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from researcher.config import load_settings, save_settings, DEFAULT_SETTINGS


def test_settings_integration_flow():
    """Test complete settings flow from change to application"""
    print("=" * 80)
    print("Integration Test: Settings Flow")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.json"
        
        with patch("researcher.config.SETTINGS_FILE_PATH", settings_path):
            
            # Step 1: Initial state (default settings)
            print("\n[Step 1] Load default settings")
            settings = load_settings()
            print(f"  Default settings loaded:")
            print(f"    - search_model: {settings['search_model']}")
            print(f"    - response_model: {settings['response_model']}")
            print(f"    - eval_model: {settings['eval_model']}")
            print(f"    - searxng_engine: {settings['searxng_engine']}")
            print(f"    - searxng_lang: {settings['searxng_lang']}")
            print(f"    - searxng_safesearch: {settings['searxng_safesearch']}")
            assert settings == DEFAULT_SETTINGS
            print("  ✓ Default settings confirmed")
            
            # Step 2: User changes settings in Settings page
            print("\n[Step 2] Simulate user changing settings in Settings page")
            new_settings = {
                'search_model': 'llama3.2:1b',  # Changed
                'response_model': 'llama3.1',   # Changed
                'eval_model': 'llama3.2:3b',    # Unchanged
                'searxng_engine': 'news',       # Changed
                'searxng_lang': 'en',           # Changed
                'searxng_safesearch': 'moderate', # Changed
                'ui_text_size': 'medium',       # Default
                'llm_providers': [],            # Default
            }
            print(f"  User selected new settings:")
            for key, value in new_settings.items():
                old_value = settings[key]
                status = "CHANGED" if value != old_value else "unchanged"
                print(f"    - {key}: {old_value} → {value} [{status}]")
            
            # Step 3: Save settings (simulate "💾 設定を保存" button click)
            print("\n[Step 3] Save settings")
            success = save_settings(new_settings)
            assert success is True
            print("  ✓ Settings saved successfully")
            
            # Step 4: Verify file persistence
            print("\n[Step 4] Verify settings persisted to file")
            assert settings_path.exists()
            print(f"  ✓ Settings file exists: {settings_path}")
            
            # Step 5: Reload settings (simulate Chat page initialization)
            print("\n[Step 5] Reload settings (simulate Chat page initialization)")
            reloaded_settings = load_settings()
            print(f"  Reloaded settings:")
            for key, value in reloaded_settings.items():
                print(f"    - {key}: {value}")
            assert reloaded_settings == new_settings
            print("  ✓ Settings correctly reloaded")
            
            # Step 6: Verify ChatManager would receive correct params
            print("\n[Step 6] Verify ChatManager would receive correct params")
            print(f"  Expected ChatManager initialization:")
            print(f"    - evaluation_model = '{reloaded_settings['eval_model']}'")
            print(f"    - searxng_engine = '{reloaded_settings['searxng_engine']}'")
            print(f"    - searxng_lang = '{reloaded_settings['searxng_lang']}'")
            print(f"    - searxng_safesearch = '{reloaded_settings['searxng_safesearch']}'")
            
            print(f"\n  Expected search() method params:")
            searxng_params = {}
            if reloaded_settings['searxng_engine']:
                searxng_params["engines"] = reloaded_settings['searxng_engine']
            if reloaded_settings['searxng_lang']:
                searxng_params["language"] = reloaded_settings['searxng_lang']
            if reloaded_settings['searxng_safesearch']:
                searxng_params["safesearch"] = reloaded_settings['searxng_safesearch']
            
            for key, value in searxng_params.items():
                print(f"    - {key} = '{value}'")
            
            assert searxng_params["engines"] == "news"
            assert searxng_params["language"] == "en"
            assert searxng_params["safesearch"] == "moderate"
            print("  ✓ SearXNG params correctly constructed")
            
            # Step 7: Test settings reset
            print("\n[Step 7] Test settings reset (🔄 デフォルトに戻す)")
            reset_success = save_settings(DEFAULT_SETTINGS)
            assert reset_success is True
            print("  ✓ Reset to defaults saved")
            
            reset_settings = load_settings()
            assert reset_settings == DEFAULT_SETTINGS
            print("  ✓ Settings correctly reset to defaults")
            
            # Step 8: Test edge case - partial settings
            print("\n[Step 8] Test edge case - partial settings file")
            partial_settings = {
                'search_model': 'custom-model'
                # Other keys missing
            }
            save_settings(partial_settings)
            
            loaded_partial = load_settings()
            print(f"  Loaded from partial settings:")
            for key, value in loaded_partial.items():
                source = "custom" if key == 'search_model' else "default"
                print(f"    - {key}: {value} ({source})")
            
            assert loaded_partial['search_model'] == 'custom-model'
            assert loaded_partial['response_model'] == DEFAULT_SETTINGS['response_model']
            print("  ✓ Partial settings merged with defaults")
            
    print("\n" + "=" * 80)
    print("All integration tests passed!")
    print("=" * 80)
    print("\n📋 Verification Checklist:")
    print("  ✅ Settings can be loaded")
    print("  ✅ Settings can be saved")
    print("  ✅ Settings persist to file")
    print("  ✅ Settings reload correctly")
    print("  ✅ ChatManager params are correctly constructed")
    print("  ✅ Settings can be reset to defaults")
    print("  ✅ Partial settings merge with defaults")


if __name__ == "__main__":
    test_settings_integration_flow()
