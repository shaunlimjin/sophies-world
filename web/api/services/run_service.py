"""Run state management — filesystem as source of truth."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

STAGES = ["research", "ranking", "synthesis", "render"]


class StageState(BaseModel):
    name: str
    status: str  # pending | running | done | failed
    artifact_path: Optional[str] = None


class RunState(BaseModel):
    name: str
    created_at: str
    stages: list[StageState]
    settings: dict[str, str] = {}


class RunSummary(BaseModel):
    name: str
    created_at: str
    stage_statuses: dict[str, str]
    settings: dict[str, str] = {}


def _read_settings(ar: Path) -> dict[str, str]:
    sf = ar / "settings.json"
    if sf.exists():
        try:
            return json.loads(sf.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _approaches_dir(repo_root: Path) -> Path:
    return repo_root / "artifacts" / "approaches"


def _artifacts_root(repo_root: Path, name: str) -> Path:
    return _approaches_dir(repo_root) / name


def _stage_artifact_path(artifacts_root: Path, stage: str, today: date) -> Optional[Path]:
    d = today.isoformat()
    mapping = {
        "research": artifacts_root / "research" / f"sophie-{d}-raw.json",
        "ranking":  artifacts_root / "research" / f"sophie-{d}.json",
        "synthesis": artifacts_root / "issues" / f"sophie-{d}.json",
        "render":   artifacts_root / "newsletters" / f"sophies-world-{d}.html",
    }
    return mapping.get(stage)


def _stage_status(
    artifacts_root: Path, stage: str, today: date
) -> tuple[str, Optional[str]]:
    running = artifacts_root / f".stage-{stage}.running"
    failed = artifacts_root / f".stage-{stage}.failed"
    artifact = _stage_artifact_path(artifacts_root, stage, today)
    if running.exists():
        return "running", None
    if failed.exists():
        return "failed", None
    if artifact and artifact.exists():
        return "done", str(artifact)
    return "pending", None


def list_runs(repo_root: Path) -> list[RunSummary]:
    d = _approaches_dir(repo_root)
    if not d.exists():
        return []
    today = date.today()
    result = []
    for run_dir in sorted(d.iterdir(), key=lambda p: -p.stat().st_mtime):
        if not run_dir.is_dir():
            continue
        ar = run_dir
        result.append(RunSummary(
            name=run_dir.name,
            created_at=str(int(run_dir.stat().st_mtime)),
            stage_statuses={s: _stage_status(ar, s, today)[0] for s in STAGES},
            settings=_read_settings(ar),
        ))
    return result


def get_run_state(repo_root: Path, name: str) -> RunState:
    ar = _artifacts_root(repo_root, name)
    if not ar.exists():
        raise FileNotFoundError(f"Run not found: {name}")
    today = date.today()
    stages = []
    for s in STAGES:
        status, artifact_path = _stage_status(ar, s, today)
        stages.append(StageState(name=s, status=status, artifact_path=artifact_path))
    return RunState(name=name, created_at=str(int(ar.stat().st_mtime)), stages=stages, settings=_read_settings(ar))


def create_run(repo_root: Path, name: str, overrides: dict[str, str] = None) -> RunSummary:
    ar = _artifacts_root(repo_root, name)
    if ar.exists():
        raise FileExistsError(f"Run already exists: {name}")
    if overrides:
        _validate_model_overrides(repo_root, overrides)
    ar.mkdir(parents=True)
    if overrides:
        (ar / "settings.json").write_text(json.dumps(overrides), encoding="utf-8")
    return RunSummary(
        name=name,
        created_at=str(int(ar.stat().st_mtime)),
        stage_statuses={s: "pending" for s in STAGES},
        settings=overrides or {},
    )


def _validate_model_overrides(repo_root: Path, overrides: dict) -> None:
    """Raise ValueError if any model preset name is unknown or strategy-incompatible."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
    from providers.model_presets import load_presets, STRATEGY_REQUIRES_TOOLS

    pairs = [
        ("synthesis_model", "synthesis_provider"),
        ("ranking_model", "ranker_provider"),
    ]
    relevant = [(m, s) for m, s in pairs if m in overrides]
    if not relevant:
        return

    presets = load_presets(repo_root)
    for model_key, strategy_key in relevant:
        name = overrides[model_key]
        if name not in presets:
            raise ValueError(
                f"Unknown model preset: {name!r}. "
                f"Available: {sorted(presets.keys())}"
            )
        strategy = overrides.get(strategy_key)
        if strategy and STRATEGY_REQUIRES_TOOLS.get(strategy):
            if not presets[name].get("supports_tools"):
                raise ValueError(
                    f"Preset {name!r} is incompatible with strategy {strategy!r} "
                    f"(tool-calling required)."
                )