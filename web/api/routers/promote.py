"""Promote endpoints: preview diff and apply promotion."""
from __future__ import annotations

import shutil
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from pydantic import BaseModel
from typing import Optional

from web.api.deps import get_repo_root

router = APIRouter(prefix="/api/runs", tags=["promote"])


class PromoteBody(BaseModel):
    to: str  # "staging" or "prod"
    confirmed: bool = False


def _newsletter_dest(repo_root: Path, to: str, today: date) -> Path:
    filename = f"sophies-world-{today.isoformat()}.html"
    if to == "staging":
        return repo_root / "newsletters" / "staging" / filename
    return repo_root / "newsletters" / filename


def _newsletter_source(repo_root: Path, name: str, today: date) -> Optional[Path]:
    p = (repo_root / "artifacts" / "approaches" / name / "newsletters"
         / f"sophies-world-{today.isoformat()}.html")
    return p if p.exists() else None


def _build_diff(source: Path, dest: Path, repo_root: Path) -> dict:
    action = "replace" if dest.exists() else "add"
    entry = {
        "action": action,
        "source": str(source.relative_to(repo_root)),
        "path": str(dest.relative_to(repo_root)),
    }
    if action == "replace":
        old = dest.read_text(encoding="utf-8")
        new = source.read_text(encoding="utf-8")
        entry["chars_changed"] = abs(len(new) - len(old))
    return entry


@router.post("/{name}/promote/preview")
def promote_preview(
    name: str,
    body: PromoteBody,
    repo_root: Path = Depends(get_repo_root),
) -> dict:
    if body.to not in ("staging", "prod"):
        raise HTTPException(status_code=400, detail="to must be 'staging' or 'prod'")
    today = date.today()
    source = _newsletter_source(repo_root, name, today)
    if source is None:
        raise HTTPException(status_code=400, detail="Render stage not complete for this run")
    dest = _newsletter_dest(repo_root, body.to, today)
    return {
        "run": name,
        "to": body.to,
        "date": today.isoformat(),
        "changes": [_build_diff(source, dest, repo_root)],
    }


@router.post("/{name}/promote/apply")
def promote_apply(
    name: str,
    body: PromoteBody,
    repo_root: Path = Depends(get_repo_root),
) -> dict:
    if body.to not in ("staging", "prod"):
        raise HTTPException(status_code=400, detail="to must be 'staging' or 'prod'")
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmed must be true")
    today = date.today()
    source = _newsletter_source(repo_root, name, today)
    if source is None:
        raise HTTPException(status_code=400, detail="Render stage not complete for this run")
    dest = _newsletter_dest(repo_root, body.to, today)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return {"ok": True, "copied_to": str(dest.relative_to(repo_root))}