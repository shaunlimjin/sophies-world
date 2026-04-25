"""Tests for content_stage provider injection."""
from unittest.mock import MagicMock
from pathlib import Path

from scripts.content_stage import run_content_provider, run_packet_synthesis_provider


def test_run_content_provider_uses_provider(monkeypatch):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"result": '{"test": true}'}

    monkeypatch.setattr("scripts.content_stage.parse_content_output", lambda raw, repo=None: {"test": True})

    result = run_content_provider("prompt", Path("/tmp"), provider=mock_provider)
    assert result == '{"test": true}'
    mock_provider.generate.assert_called_once()


def test_run_packet_synthesis_provider_uses_provider(monkeypatch):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"result": '{"test": true}'}

    monkeypatch.setattr("scripts.content_stage.parse_content_output", lambda raw, repo=None: {"test": True})

    result = run_packet_synthesis_provider("prompt", Path("/tmp"), provider=mock_provider)
    assert result == '{"test": true}'
    mock_provider.generate.assert_called_once_with(
        "prompt",
        timeout=300,
        max_retries=0,
        max_turns=3,
    )


def test_run_packet_synthesis_provider_uses_raw_stdout_when_provider_parse_fails(monkeypatch, tmp_path):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {
        "result": "",
        "stdout": '{"test": true}',
        "stderr": "provider parse failed",
        "error": "parse_error: envelope parse failed",
    }

    monkeypatch.setattr("scripts.content_stage.parse_content_output", lambda raw, repo=None: {"test": True})

    result = run_packet_synthesis_provider("prompt", tmp_path, provider=mock_provider)
    assert result == '{"test": true}'
    assert (tmp_path / "artifacts" / "debug" / "last-packet-stderr-attempt0.txt").read_text() == "provider parse failed"
