"""Run list + create + state endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from pydantic import BaseModel

from web.api.deps import get_repo_root

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunBody(BaseModel):
    name: str
    provider_overrides: dict = {}


@router.get("")
def list_runs(repo_root: Path = Depends(get_repo_root)):
    from web.api.services.run_service import list_runs as _list
    return _list(repo_root)


@router.post("")
def create_run(body: CreateRunBody, repo_root: Path = Depends(get_repo_root)):
    from web.api.services.run_service import create_run as _create
    try:
        return _create(repo_root, body.name, body.provider_overrides)
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Run already exists: {body.name}")


@router.get("/{name}")
def get_run(name: str, repo_root: Path = Depends(get_repo_root)):
    from web.api.services.run_service import get_run_state
    try:
        return get_run_state(repo_root, name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run not found: {name}")