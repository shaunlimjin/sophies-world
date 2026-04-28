"""Stage runner: bridges sync stage functions to async SSE streams."""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from datetime import date
from pathlib import Path
from typing import AsyncGenerator, Callable

REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _artifact_path(stage: str, artifacts_root: Path, today: date) -> Path | None:
    d = today.isoformat()
    mapping = {
        "research": artifacts_root / "research" / f"sophie-{d}-raw.json",
        "ranking":  artifacts_root / "research" / f"sophie-{d}.json",
        "synthesis": artifacts_root / "issues" / f"sophie-{d}.json",
        "render":   artifacts_root / "newsletters" / f"sophies-world-{d}.html",
    }
    return mapping.get(stage)


class StageRunner:
    def __init__(self, repo_root: Path, stage_queues: dict):
        self.repo_root = repo_root
        self._queues = stage_queues  # shared with app.state.stage_queues

    def _ar(self, name: str) -> Path:
        return self.repo_root / "artifacts" / "approaches" / name

    def _sentinel(self, name: str, stage: str, kind: str) -> Path:
        return self._ar(name) / f".stage-{stage}.{kind}"

    def is_running(self, name: str, stage: str) -> bool:
        return (name, stage) in self._queues or self._sentinel(name, stage, "running").exists()

    def _set_running(self, name: str, stage: str) -> None:
        s = self._sentinel(name, stage, "running")
        s.parent.mkdir(parents=True, exist_ok=True)
        s.touch()
        f = self._sentinel(name, stage, "failed")
        if f.exists():
            f.unlink()

    def _clear_running(self, name: str, stage: str) -> None:
        s = self._sentinel(name, stage, "running")
        if s.exists():
            s.unlink()
        self._queues.pop((name, stage), None)

    def _set_failed(self, name: str, stage: str) -> None:
        self._clear_running(name, stage)
        self._sentinel(name, stage, "failed").touch()

    def trigger(self, name: str, stage: str, provider_overrides: dict) -> None:
        """Start stage in a background thread. Raises RuntimeError if already running."""
        if self.is_running(name, stage):
            raise RuntimeError(f"Stage {stage} of run {name} is already running")
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[(name, stage)] = queue
        self._set_running(name, stage)

        ar = self._ar(name)
        today = date.today()

        def log(text: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "line", "text": text})

        def run_in_thread() -> None:
            try:
                _dispatch_stage(stage, self.repo_root, ar, provider_overrides, log)
                ap = _artifact_path(stage, ar, today)
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "type": "artifact",
                    "path": str(ap) if ap else None,
                })
                self._clear_running(name, stage)
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "type": "done", "stage": stage, "success": True,
                })
            except Exception as exc:
                self._set_failed(name, stage)
                loop.call_soon_threadsafe(queue.put_nowait, {
                    "type": "error", "message": str(exc), "stage": stage,
                })
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=run_in_thread, daemon=True).start()

    async def stream(self, name: str, stage: str) -> AsyncGenerator[str, None]:
        """Yield SSE events for a stage. If not running, returns status immediately."""
        queue = self._queues.get((name, stage))
        if queue is None:
            ar = self._ar(name)
            ap = _artifact_path(stage, ar, date.today())
            if ap and ap.exists():
                yield _sse("done", {"type": "done", "stage": stage, "success": True})
            elif self._sentinel(name, stage, "failed").exists():
                yield _sse("error", {"type": "error", "message": "Stage failed", "stage": stage})
            else:
                yield _sse("error", {"type": "error", "message": "Stage not started", "stage": stage})
            return

        yield _sse("stage", {"type": "stage", "stage": stage, "status": "running"})
        while True:
            item = await queue.get()
            if item is None:
                break
            yield _sse(item["type"], item)


def _load_config(repo_root: Path) -> dict:
    import yaml
    child_path = repo_root / "config" / "children" / "sophie.yaml"
    pipeline_path = repo_root / "config" / "pipelines" / "default.yaml"
    profile = yaml.safe_load(child_path.read_text(encoding="utf-8"))
    pipeline = yaml.safe_load(pipeline_path.read_text(encoding="utf-8"))
    active = profile.get("newsletter", {}).get("active_sections", [])
    sections = {}
    for sid in active:
        sp = repo_root / "config" / "sections" / f"{sid}.yaml"
        if sp.exists():
            sections[sid] = yaml.safe_load(sp.read_text(encoding="utf-8"))
    theme_path = repo_root / "config" / "themes" / "default.yaml"
    theme = yaml.safe_load(theme_path.read_text(encoding="utf-8"))
    return {"profile": profile, "pipeline": pipeline, "sections": sections, "theme": theme}


def _dispatch_stage(
    stage: str,
    repo_root: Path,
    artifacts_root: Path,
    provider_overrides: dict,
    log: Callable[[str], None],
) -> None:
    config = _load_config(repo_root)
    today = date.today()

    if stage == "research":
        from research_stage import run_research_stage
        run_research_stage(
            config=config, today=today, repo_root=repo_root,
            artifacts_root=artifacts_root, log=log,
            refresh=provider_overrides.get("refresh", False),
        )

    elif stage == "ranking":
        from ranking_stage import run_ranking_stage
        ranker = provider_overrides.get("ranker_provider", "heuristic_ranker")
        model_override = provider_overrides.get("ranking_model")
        run_ranking_stage(
            config=config, today=today, repo_root=repo_root,
            artifacts_root=artifacts_root, ranker_provider=ranker,
            model_override=model_override, log=log,
        )

    elif stage == "synthesis":
        from content_stage import run_synthesis_stage
        from generate import get_recent_headlines, get_next_issue_number, NEWSLETTERS_DIR
        synthesis_provider = provider_overrides.get("synthesis_provider", "hosted_packet_synthesis")
        model_override = provider_overrides.get("synthesis_model")
        recent = get_recent_headlines(NEWSLETTERS_DIR, today)
        issue_num = get_next_issue_number(NEWSLETTERS_DIR)
        run_synthesis_stage(
            config=config, today=today, issue_num=issue_num,
            recent_headlines=recent, repo_root=repo_root,
            artifacts_root=artifacts_root,
            synthesis_provider_name=synthesis_provider,
            model_override=model_override, log=log,
        )

    elif stage == "render":
        from render_stage import run_render_stage
        run_render_stage(config=config, today=today, repo_root=repo_root,
                         artifacts_root=artifacts_root, log=log)

    else:
        raise ValueError(f"Unknown stage: {stage}")