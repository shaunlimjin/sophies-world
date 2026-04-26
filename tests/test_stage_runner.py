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