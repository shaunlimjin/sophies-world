"""Tests for stage runner SSE lifecycle and sentinel management."""
import asyncio
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def runner(tmp_path):
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from web.api.services.stage_runner import StageRunner
    queues = {}
    return StageRunner(repo_root=tmp_path, stage_queues=queues)


def test_is_running_false_initially(runner, tmp_path):
    assert not runner.is_running("my-run", "research")


def test_set_running_creates_sentinel(runner, tmp_path):
    (tmp_path / "artifacts" / "approaches" / "my-run").mkdir(parents=True)
    runner._set_running("my-run", "research")
    assert (tmp_path / "artifacts" / "approaches" / "my-run" / ".stage-research.running").exists()
    assert runner.is_running("my-run", "research")


def test_set_failed_removes_running_sentinel(runner, tmp_path):
    (tmp_path / "artifacts" / "approaches" / "my-run").mkdir(parents=True)
    runner._set_running("my-run", "research")
    runner._set_failed("my-run", "research")
    running = tmp_path / "artifacts" / "approaches" / "my-run" / ".stage-research.running"
    failed = tmp_path / "artifacts" / "approaches" / "my-run" / ".stage-research.failed"
    assert not running.exists()
    assert failed.exists()


def test_clear_running_removes_sentinel(runner, tmp_path):
    (tmp_path / "artifacts" / "approaches" / "my-run").mkdir(parents=True)
    runner._set_running("my-run", "research")
    runner._clear_running("my-run", "research")
    assert not runner.is_running("my-run", "research")


def test_trigger_raises_if_already_running(runner, tmp_path):
    (tmp_path / "artifacts" / "approaches" / "my-run").mkdir(parents=True)
    runner._set_running("my-run", "research")
    with pytest.raises(RuntimeError, match="already running"):
        runner.trigger("my-run", "research", {})


async def collect_stream(runner, name, stage):
    events = []
    async for chunk in runner.stream(name, stage):
        events.append(chunk)
    return events


def test_stream_done_stage_emits_done_event(runner, tmp_path):
    """stream() on a completed stage emits a single done event."""
    today = date.today()
    ar = tmp_path / "artifacts" / "approaches" / "my-run"
    research_dir = ar / "research"
    research_dir.mkdir(parents=True)
    raw_path = research_dir / f"sophie-{today.isoformat()}-raw.json"
    raw_path.write_text("{}")

    events = asyncio.run(collect_stream(runner, "my-run", "research"))
    assert any('"type": "done"' in e for e in events)


def test_stream_failed_stage_emits_error_event(runner, tmp_path):
    """stream() on a failed stage emits a single error event."""
    ar = tmp_path / "artifacts" / "approaches" / "my-run"
    ar.mkdir(parents=True)
    (ar / ".stage-research.failed").touch()

    events = asyncio.run(collect_stream(runner, "my-run", "research"))
    assert any('"type": "error"' in e for e in events)


def test_dispatch_stage_passes_model_override_to_synthesis(tmp_path, monkeypatch):
    """When provider_overrides has synthesis_model, it is forwarded to run_synthesis_stage."""
    captured = {}
    def fake_run_synthesis(**kwargs):
        captured.update(kwargs)
    def fake_recent(*a, **kw): return []
    def fake_issue_num(*a, **kw): return 1

    monkeypatch.setattr("content_stage.run_synthesis_stage", fake_run_synthesis)
    monkeypatch.setattr("generate.get_recent_headlines", fake_recent)
    monkeypatch.setattr("generate.get_next_issue_number", fake_issue_num)

    (tmp_path / "config" / "children").mkdir(parents=True)
    (tmp_path / "config" / "pipelines").mkdir(parents=True)
    (tmp_path / "config" / "themes").mkdir(parents=True)
    (tmp_path / "config" / "children" / "sophie.yaml").write_text("newsletter:\n  active_sections: []\n")
    (tmp_path / "config" / "pipelines" / "default.yaml").write_text("pipeline: {}\n")
    (tmp_path / "config" / "themes" / "default.yaml").write_text("template_path: x\n")

    from web.api.services.stage_runner import _dispatch_stage
    ar = tmp_path / "artifacts" / "approaches" / "my-run"
    ar.mkdir(parents=True)
    overrides = {"synthesis_provider": "hosted_packet_synthesis", "synthesis_model": "minimax-m2"}
    _dispatch_stage("synthesis", tmp_path, ar, overrides, log=lambda _: None)
    assert captured["model_override"] == "minimax-m2"
    assert captured["synthesis_provider_name"] == "hosted_packet_synthesis"


def test_dispatch_stage_passes_model_override_to_ranking(tmp_path, monkeypatch):
    """When provider_overrides has ranking_model, it is forwarded to run_ranking_stage."""
    captured = {}
    def fake_run_ranking(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("ranking_stage.run_ranking_stage", fake_run_ranking)

    (tmp_path / "config" / "children").mkdir(parents=True)
    (tmp_path / "config" / "pipelines").mkdir(parents=True)
    (tmp_path / "config" / "themes").mkdir(parents=True)
    (tmp_path / "config" / "children" / "sophie.yaml").write_text("newsletter:\n  active_sections: []\n")
    (tmp_path / "config" / "pipelines" / "default.yaml").write_text("pipeline: {}\n")
    (tmp_path / "config" / "themes" / "default.yaml").write_text("template_path: x\n")

    from web.api.services.stage_runner import _dispatch_stage
    ar = tmp_path / "artifacts" / "approaches" / "my-run"
    ar.mkdir(parents=True)
    overrides = {"ranker_provider": "hosted_model_ranker", "ranking_model": "claude-sonnet"}
    _dispatch_stage("ranking", tmp_path, ar, overrides, log=lambda _: None)
    assert captured["model_override"] == "claude-sonnet"
    assert captured["ranker_provider"] == "hosted_model_ranker"