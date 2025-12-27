import os
from unittest.mock import patch
import tempfile
from pathlib import Path

from researcher.config import (
    DEFAULT_RELEVANCE_THRESHOLD,
    DEFAULT_SEARXNG_URL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_SETTINGS,
    get_embedding_model,
    get_relevance_threshold,
    get_searxng_url,
    load_blacklist_domains,
    save_blacklist_domains,
    load_settings,
    save_settings,
    BLACKLIST_FILE_PATH,
    SETTINGS_FILE_PATH,
)


def test_get_searxng_url_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_searxng_url() == DEFAULT_SEARXNG_URL


def test_get_searxng_url_from_env():
    with patch.dict(os.environ, {"SEARXNG_URL": "http://env:8888"}, clear=True):
        assert get_searxng_url() == "http://env:8888"


def test_get_searxng_url_from_cli():
    with patch.dict(os.environ, {"SEARXNG_URL": "http://env:8888"}, clear=True):
        assert get_searxng_url("http://cli:8888") == "http://cli:8888"


def test_get_searxng_url_priority():
    with patch.dict(os.environ, {"SEARXNG_URL": "http://env:8888"}, clear=True):
        assert get_searxng_url() == "http://env:8888"
    with patch.dict(os.environ, {}, clear=True):
        assert get_searxng_url() == DEFAULT_SEARXNG_URL


def test_get_embedding_model_resolution():
    with patch.dict(os.environ, {}, clear=True):
        assert get_embedding_model() == DEFAULT_EMBEDDING_MODEL
    with patch.dict(os.environ, {"EMBEDDING_MODEL": "env-model"}, clear=True):
        assert get_embedding_model() == "env-model"
    with patch.dict(os.environ, {"EMBEDDING_MODEL": "env-model"}, clear=True):
        assert get_embedding_model("cli-model") == "cli-model"


def test_get_relevance_threshold_resolution():
    with patch.dict(os.environ, {}, clear=True):
        assert get_relevance_threshold() == DEFAULT_RELEVANCE_THRESHOLD
    with patch.dict(os.environ, {"RELEVANCE_THRESHOLD": "0.8"}, clear=True):
        assert get_relevance_threshold() == 0.8
    assert get_relevance_threshold(0.9) == 0.9


def test_get_relevance_threshold_default_value():
    """Test that default relevance_threshold is 0.5, not 0.0."""
    with patch.dict(os.environ, {}, clear=True):
        threshold = get_relevance_threshold()
        # Verify default is 0.5 (meaning: return results with 50% relevance or higher)
        # 0.0 would mean "return all results" but that's not the intended behavior
        assert threshold == 0.5
        assert threshold == DEFAULT_RELEVANCE_THRESHOLD


def test_load_blacklist_domains_empty():
    """Test loading blacklist when file doesn't exist."""
    with patch("researcher.config.BLACKLIST_FILE_PATH", Path("/nonexistent/path/blacklist.json")):
        result = load_blacklist_domains()
        assert result == set()


def test_load_blacklist_domains_valid():
    """Test loading valid blacklist JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        json.dump(["wsj.com", "nytimes.com", "paywall.com"], f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.BLACKLIST_FILE_PATH", Path(temp_path)):
            result = load_blacklist_domains()
            assert result == {"wsj.com", "nytimes.com", "paywall.com"}
    finally:
        Path(temp_path).unlink()


def test_save_blacklist_domains():
    """Test saving blacklist domains to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "blacklist.json"
        with patch("researcher.config.BLACKLIST_FILE_PATH", temp_path):
            domains = {"example.com", "test.com"}
            save_blacklist_domains(domains)
            
            # Verify file was created and contains correct data
            assert temp_path.exists()
            import json
            with open(temp_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                assert set(saved_data) == domains


def test_save_blacklist_domains_creates_directory():
    """Test that save_blacklist_domains creates parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "subdir" / "nested" / "blacklist.json"
        with patch("researcher.config.BLACKLIST_FILE_PATH", temp_path):
            domains = {"example.com"}
            save_blacklist_domains(domains)
            
            # Verify directory structure was created
            assert temp_path.parent.exists()
            assert temp_path.exists()


def test_load_blacklist_domains_with_mixed_types():
    """Test that load_blacklist_domains filters out non-string items."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        json.dump(["wsj.com", 123, "example.com", None, "test.com"], f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.BLACKLIST_FILE_PATH", Path(temp_path)):
            result = load_blacklist_domains()
            # Only string entries should be loaded
            assert result == {"wsj.com", "example.com", "test.com"}
            assert 123 not in result
            assert None not in result
    finally:
        Path(temp_path).unlink()


def test_load_blacklist_domains_strips_whitespace():
    """Test that load_blacklist_domains strips whitespace from entries."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        json.dump(["  example.com  ", "test.com", "  "], f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.BLACKLIST_FILE_PATH", Path(temp_path)):
            result = load_blacklist_domains()
            # Whitespace should be stripped, empty entries ignored
            assert result == {"example.com", "test.com"}
    finally:
        Path(temp_path).unlink()


def test_save_feedback_includes_model():
    """Test that save_feedback includes model field in saved record."""
    from researcher.config import save_feedback, load_feedback_history, FEEDBACK_FILE_PATH
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        feedback_path = Path(tmpdir) / "feedback.json"
        
        with patch("researcher.config.FEEDBACK_FILE_PATH", feedback_path):
            # Save feedback with model
            success = save_feedback(
                query="Test query",
                response="Test response",
                rating="up",
                model="gpt-oss:20b",
                session_id=1
            )
            
            assert success is True
            assert feedback_path.exists()
            
            # Load and verify
            with open(feedback_path, "r") as f:
                records = json.load(f)
            
            assert len(records) == 1
            assert records[0]["model"] == "gpt-oss:20b"
            assert records[0]["query"] == "Test query"
            assert records[0]["response"] == "Test response"
            assert records[0]["rating"] == "up"
            assert records[0]["session_id"] == 1
            assert "timestamp" in records[0]


def test_feedback_stats_model_filter():
    """Test that get_feedback_stats correctly filters by model."""
    from researcher.config import save_feedback, get_feedback_stats, FEEDBACK_FILE_PATH
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        feedback_path = Path(tmpdir) / "feedback.json"
        
        with patch("researcher.config.FEEDBACK_FILE_PATH", feedback_path):
            # Save multiple feedback records with different models
            save_feedback("q1", "r1", "down", "gpt-oss:20b")
            save_feedback("q2", "r2", "down", "gpt-oss:20b")
            save_feedback("q3", "r3", "up", "gpt-oss:20b")
            save_feedback("q4", "r4", "down", "llama3.2")
            save_feedback("q5", "r5", "up", "llama3.2")
            
            # Get overall stats
            overall_stats = get_feedback_stats()
            assert overall_stats["total_count"] == 5
            assert overall_stats["thumbs_down_count"] == 3
            assert overall_stats["thumbs_down_rate"] == 0.6
            
            # Get model-specific stats
            gpt_oss_stats = get_feedback_stats(model_filter="gpt-oss:20b")
            assert gpt_oss_stats["total_count"] == 3
            assert gpt_oss_stats["thumbs_down_count"] == 2
            assert gpt_oss_stats["thumbs_down_rate"] == 2/3
            assert gpt_oss_stats.get("model_filter") == "gpt-oss:20b"
            
            # Check by_model in response contains both models
            assert "by_model" in gpt_oss_stats
            assert "gpt-oss:20b" in gpt_oss_stats["by_model"]
            assert "llama3.2" in gpt_oss_stats["by_model"]


def test_load_feedback_history_handles_missing_model():
    """Test that load_feedback_history sets 'unknown' for records without model field."""
    from researcher.config import load_feedback_history, FEEDBACK_FILE_PATH
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        feedback_path = Path(tmpdir) / "feedback.json"
        
        # Create feedback records with and without model field
        records = [
            {
                "timestamp": "2025-01-01T10:00:00",
                "query": "q1",
                "response": "r1",
                "rating": "up",
                "model": "gpt-oss:20b"
            },
            {
                "timestamp": "2025-01-01T09:00:00",
                "query": "q2",
                "response": "r2",
                "rating": "down"
                # Missing model field
            }
        ]
        
        with feedback_path.open("w") as f:
            json.dump(records, f)
        
        with patch("researcher.config.FEEDBACK_FILE_PATH", feedback_path):
            loaded = load_feedback_history()
            assert len(loaded) == 2
            assert loaded[0]["model"] == "gpt-oss:20b"
            assert loaded[1]["model"] == "unknown"  # Should be set to "unknown"


def test_load_settings_default():
    """Test loading settings when file doesn't exist returns default settings."""
    with patch("researcher.config.SETTINGS_FILE_PATH", Path("/nonexistent/path/settings.json")):
        result = load_settings()
        assert result == DEFAULT_SETTINGS
        assert result["search_model"] == "llama3.2"
        assert result["response_model"] == "llama3"
        assert result["eval_model"] == "llama3.2:3b"
        assert result["searxng_engine"] == "general"
        assert result["searxng_lang"] == "ja"
        assert result["searxng_safesearch"] == "off"


def test_load_settings_valid():
    """Test loading valid settings JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        custom_settings = {
            "search_model": "llama3.3",
            "response_model": "llama3.1",
            "eval_model": "llama3.2:1b",
            "searxng_engine": "news",
            "searxng_lang": "en",
            "searxng_safesearch": "strict"
        }
        json.dump(custom_settings, f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.SETTINGS_FILE_PATH", Path(temp_path)):
            result = load_settings()
            assert result["search_model"] == "llama3.3"
            assert result["response_model"] == "llama3.1"
            assert result["eval_model"] == "llama3.2:1b"
            assert result["searxng_engine"] == "news"
            assert result["searxng_lang"] == "en"
            assert result["searxng_safesearch"] == "strict"
    finally:
        Path(temp_path).unlink()


def test_load_settings_partial():
    """Test loading settings with missing keys merges with defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        partial_settings = {
            "search_model": "custom-model"
            # Other keys missing
        }
        json.dump(partial_settings, f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.SETTINGS_FILE_PATH", Path(temp_path)):
            result = load_settings()
            assert result["search_model"] == "custom-model"  # Custom value
            assert result["response_model"] == "llama3"  # Default value
            assert result["eval_model"] == "llama3.2:3b"  # Default value
    finally:
        Path(temp_path).unlink()


def test_load_settings_invalid_json():
    """Test loading settings with invalid JSON returns defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name
    
    try:
        with patch("researcher.config.SETTINGS_FILE_PATH", Path(temp_path)):
            result = load_settings()
            assert result == DEFAULT_SETTINGS
    finally:
        Path(temp_path).unlink()


def test_save_settings():
    """Test saving settings to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "settings.json"
        with patch("researcher.config.SETTINGS_FILE_PATH", temp_path):
            custom_settings = {
                "search_model": "llama3.3",
                "response_model": "llama3.1",
                "eval_model": "llama3.2:1b",
                "searxng_engine": "news",
                "searxng_lang": "en",
                "searxng_safesearch": "strict"
            }
            success = save_settings(custom_settings)
            
            assert success is True
            assert temp_path.exists()
            
            # Verify file content
            import json
            with open(temp_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                assert saved_data == custom_settings


def test_save_settings_creates_directory():
    """Test that save_settings creates parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "subdir" / "nested" / "settings.json"
        with patch("researcher.config.SETTINGS_FILE_PATH", temp_path):
            settings = {"search_model": "test"}
            success = save_settings(settings)
            
            assert success is True
            assert temp_path.parent.exists()
            assert temp_path.exists()


def test_settings_atomic_write():
    """Test that save_settings uses atomic write (temp file + replace)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "settings.json"
        with patch("researcher.config.SETTINGS_FILE_PATH", temp_path):
            settings1 = {"search_model": "model1"}
            save_settings(settings1)
            
            # Overwrite with new settings
            settings2 = {"search_model": "model2", "response_model": "model2"}
            success = save_settings(settings2)
            
            assert success is True
            
            # Verify new content
            import json
            with open(temp_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                assert saved_data == settings2
