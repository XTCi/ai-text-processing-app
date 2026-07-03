import importlib
import os

def test_settings_default_urls(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from core import config
    importlib.reload(config)
    assert config.settings.llm_base_url == "https://api.deepseek.com"
    assert config.settings.llm_model_fast == "deepseek-chat"
    assert config.settings.llm_model_think == "deepseek-reasoner"
    assert config.settings.llm_api_key == ""

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-123")
    from core import config
    importlib.reload(config)
    assert config.settings.llm_api_key == "sk-test-123"
