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


def test_run_synthesis_stage_raises_if_missing_ranked_packet(tmp_path, monkeypatch):
    """run_synthesis_stage raises FileNotFoundError if ranked packet is missing."""
    import pytest
    from datetime import date
    from scripts import content_stage

    config = {
        "profile": {"newsletter": {"active_sections": []}},
        "sections": {},
        "pipeline": {"models": {}},
    }
    artifacts_root = tmp_path / "artifacts" / "approaches" / "test-run"
    artifacts_root.mkdir(parents=True)

    monkeypatch.setattr("providers.model_providers.make_provider", lambda cfg, repo_root=None: None)

    with pytest.raises(FileNotFoundError, match="Ranked research packet not found"):
        content_stage.run_synthesis_stage(
            config=config, today=date(2026, 4, 26), issue_num=1,
            recent_headlines=[], repo_root=tmp_path,
            artifacts_root=artifacts_root,
            synthesis_provider_name="hosted_packet_synthesis",
        )


def test_run_render_stage_raises_if_missing_issue_artifact(tmp_path, monkeypatch):
    """run_render_stage raises FileNotFoundError if issue artifact is missing."""
    import pytest
    from datetime import date
    from scripts.render_stage import run_render_stage

    config = {"theme": {}}
    artifacts_root = tmp_path / "artifacts" / "approaches" / "test-run"
    artifacts_root.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Issue artifact not found"):
        run_render_stage(
            config=config, today=date(2026, 4, 26),
            repo_root=tmp_path, artifacts_root=artifacts_root,
        )
