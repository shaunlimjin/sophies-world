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


def test_run_synthesis_stage_uses_model_override(tmp_path, monkeypatch):
    """When model_override is set, that preset is resolved and used regardless of pipeline default."""
    import sys
    from datetime import date
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

    captured = {}

    def fake_make_provider(cfg, repo_root=None):
        captured["cfg"] = cfg
        class _P:
            name = cfg["provider"]
            def generate(self, prompt, **kw):
                return {"result": '{"date":"2026-04-28","sections":[]}'}
        return _P()

    def fake_run_packet(prompt, repo_root, provider=None):
        captured["called_with_provider"] = provider.name if provider else None
        return '{"date":"2026-04-28","sections":[]}'

    def fake_validate(issue): pass
    def fake_write(repo_root, issue, artifacts_root=None): return None
    def fake_parse(text, repo_root=None): return {"date": "2026-04-28", "sections": []}

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "model_presets.yaml").write_text(
        "presets:\n"
        "  claude-opus:\n"
        "    provider: claude\n"
        "    model: opus\n"
        "    supports_tools: true\n"
        "  minimax-m2:\n"
        "    provider: openai_compatible\n"
        "    model: MiniMax-M2\n"
        "    supports_tools: false\n"
    )
    today = date.today()
    ar = tmp_path / "artifacts"
    (ar / "research").mkdir(parents=True)
    (ar / "research" / f"sophie-{today.isoformat()}.json").write_text('{"sections":[]}')

    monkeypatch.setattr("providers.model_providers.make_provider", fake_make_provider)
    import content_stage
    monkeypatch.setattr(content_stage, "run_packet_synthesis_provider", fake_run_packet)
    monkeypatch.setattr(content_stage, "parse_content_output", fake_parse)
    monkeypatch.setattr("issue_schema.validate_issue_artifact", fake_validate)
    monkeypatch.setattr("issue_schema.write_issue_artifact", fake_write)

    config = {
        "profile": {"newsletter": {"active_sections": []}},
        "sections": {},
        "pipeline": {"models": {"synthesis": "claude-opus"}},
    }
    content_stage.run_synthesis_stage(
        config=config, today=today, issue_num=1, recent_headlines=[],
        repo_root=tmp_path, artifacts_root=ar,
        synthesis_provider_name="hosted_packet_synthesis",
        model_override="minimax-m2",
        log=lambda _: None,
    )
    assert captured["cfg"]["provider"] == "openai_compatible"
    assert captured["called_with_provider"] == "openai_compatible"
