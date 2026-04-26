"""Config CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from pydantic import BaseModel
import yaml

from web.api.deps import get_repo_root

router = APIRouter(prefix="/api/configs", tags=["configs"])


class ConfigWriteBody(BaseModel):
    content: str


@router.get("")
def list_configs(repo_root: Path = Depends(get_repo_root)) -> list[str]:
    from web.api.services.config_service import list_config_keys

    return list_config_keys(repo_root)


@router.get("/{file_key:path}")
def get_config(file_key: str, repo_root: Path = Depends(get_repo_root)) -> dict:
    from web.api.services.config_service import read_config

    try:
        return {"content": read_config(repo_root, file_key)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Config not found: {file_key}")


@router.put("/{file_key:path}")
def put_config(
    file_key: str,
    body: ConfigWriteBody,
    repo_root: Path = Depends(get_repo_root),
) -> dict:
    from web.api.services.config_service import write_config

    try:
        write_config(repo_root, file_key, body.content)
        return {"ok": True}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}")
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
