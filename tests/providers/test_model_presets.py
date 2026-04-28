"""Tests for the preset registry loader and resolver."""
import sys
from pathlib import Path
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from providers.model_presets import (
    load_presets,
    resolve_preset,
    resolve_model_config,
    STRATEGY_REQUIRES_TOOLS,
)


@pytest.fixture
def repo_with_presets(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "model_presets.yaml").write_text(yaml.safe_dump({
        "presets": {
            "claude-opus": {
                "label": "Claude Opus",
                "provider": "claude",
                "model": "opus",
                "supports_tools": True,
            },
            "minimax-m2": {
                "provider": "openai_compatible",
                "model": "MiniMax-M2",
                "base_url": "https://api.minimax.io/v1",
                "api_key_env": "MINIMAX_API_KEY",
                "supports_tools": False,
            },
        }
    }))
    return tmp_path


def test_load_presets_returns_dict(repo_with_presets):
    presets = load_presets(repo_with_presets)
    assert "claude-opus" in presets
    assert "minimax-m2" in presets


def test_load_presets_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_presets(tmp_path)


def test_resolve_preset_returns_provider_dict(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_preset("claude-opus", presets)
    assert resolved == {"provider": "claude", "model": "opus"}


def test_resolve_preset_includes_optional_fields(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_preset("minimax-m2", presets)
    assert resolved == {
        "provider": "openai_compatible",
        "model": "MiniMax-M2",
        "base_url": "https://api.minimax.io/v1",
        "api_key_env": "MINIMAX_API_KEY",
    }


def test_resolve_preset_strips_internal_fields(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_preset("claude-opus", presets)
    assert "supports_tools" not in resolved
    assert "label" not in resolved


def test_resolve_preset_unknown_name_raises(repo_with_presets):
    presets = load_presets(repo_with_presets)
    with pytest.raises(ValueError, match="not-a-preset"):
        resolve_preset("not-a-preset", presets)


def test_resolve_model_config_with_string_uses_preset(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_model_config("claude-opus", presets)
    assert resolved["provider"] == "claude"


def test_resolve_model_config_with_dict_passthrough(repo_with_presets):
    presets = load_presets(repo_with_presets)
    inline = {"provider": "claude", "model": "sonnet"}
    resolved = resolve_model_config(inline, presets)
    assert resolved == inline


def test_strategy_requires_tools_flags():
    assert STRATEGY_REQUIRES_TOOLS["hosted_integrated_search"] is True
    assert STRATEGY_REQUIRES_TOOLS["hosted_packet_synthesis"] is False
    assert STRATEGY_REQUIRES_TOOLS["hosted_model_ranker"] is False
