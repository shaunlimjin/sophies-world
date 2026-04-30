"""Compare endpoint: fetch artifacts for two runs at the same stage."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pathlib import Path
from typing import Optional

from web.api.deps import get_repo_root

router = APIRouter(prefix="/compare", tags=["compare"])


def _read_artifact(repo_root: Path, run_name: str, stage: str) -> Optional[str]:
    ar = repo_root / "artifacts" / "approaches" / run_name
    if not ar.exists():
        return None
    from web.api.services.run_service import _read_run_date, _stage_artifact_path
    run_date = _read_run_date(ar)
    if not run_date:
        return None
    path = _stage_artifact_path(ar, stage, run_date)
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return None


@router.get("")
def compare(
    a: str,
    b: str,
    stage: str,
    repo_root: Path = Depends(get_repo_root),
) -> dict:
    return {
        "left": _read_artifact(repo_root, a, stage),
        "right": _read_artifact(repo_root, b, stage),
        "stage": stage,
        "runs": {"a": a, "b": b},
    }