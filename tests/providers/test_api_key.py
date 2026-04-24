import os
import pytest
from scripts.providers.model_providers._api_key import load_api_key


def test_load_from_env(monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "from-env")
    assert load_api_key("MY_TEST_KEY") == "from-env"


def test_load_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text('MY_TEST_KEY=from-dotenv\n', encoding="utf-8")
    assert load_api_key("MY_TEST_KEY", repo_root=tmp_path) == "from-dotenv"


def test_dotenv_strips_quotes(tmp_path):
    (tmp_path / ".env").write_text('MY_TEST_KEY="quoted-value"\n', encoding="utf-8")
    assert load_api_key("MY_TEST_KEY", repo_root=tmp_path) == "quoted-value"


def test_dotenv_takes_priority_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "from-env")
    (tmp_path / ".env").write_text('MY_TEST_KEY=from-dotenv\n', encoding="utf-8")
    assert load_api_key("MY_TEST_KEY", repo_root=tmp_path) == "from-dotenv"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_KEY_XYZ", raising=False)
    with pytest.raises(RuntimeError, match="NONEXISTENT_KEY_XYZ"):
        load_api_key("NONEXISTENT_KEY_XYZ")
