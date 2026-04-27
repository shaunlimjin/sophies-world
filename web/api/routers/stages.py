"""Stage trigger, SSE stream, and artifact fetch endpoints."""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from pathlib import Path
from pydantic import BaseModel

from web.api.deps import get_repo_root

router = APIRouter(prefix="/api/runs", tags=["stages"])

VALID_STAGES = {"research", "ranking", "synthesis", "render"}


class TriggerBody(BaseModel):
    provider_overrides: dict = {}


def _get_runner(request: Request, repo_root: Path):
    from web.api.services.stage_runner import StageRunner
    return StageRunner(repo_root=repo_root, stage_queues=request.app.state.stage_queues)


@router.post("/{name}/stages/{stage}")
async def trigger_stage(
    name: str,
    stage: str,
    body: TriggerBody,
    request: Request,
    repo_root: Path = Depends(get_repo_root),
):
    if stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")
    ar = repo_root / "artifacts" / "approaches" / name
    if not ar.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {name}")
    overrides = body.provider_overrides
    if not overrides:
        from web.api.services.run_service import _read_settings
        overrides = _read_settings(ar)

    runner = _get_runner(request, repo_root)
    try:
        runner.trigger(name, stage, overrides)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"accepted": True, "run": name, "stage": stage}


@router.get("/{name}/stages/{stage}/stream")
async def stream_stage(
    name: str,
    stage: str,
    request: Request,
    repo_root: Path = Depends(get_repo_root),
):
    if stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")
    runner = _get_runner(request, repo_root)

    async def event_generator():
        async for chunk in runner.stream(name, stage):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{name}/stages/{stage}/artifact")
def get_artifact(
    name: str,
    stage: str,
    repo_root: Path = Depends(get_repo_root),
):
    if stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")
    ar = repo_root / "artifacts" / "approaches" / name
    today = date.today()
    d = today.isoformat()
    paths = {
        "research": ar / "research" / f"sophie-{d}-raw.json",
        "ranking":  ar / "research" / f"sophie-{d}.json",
        "synthesis": ar / "issues" / f"sophie-{d}.json",
        "render":   ar / "newsletters" / f"sophies-world-{d}.html",
    }
    path = paths.get(stage)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact not found for stage: {stage}")
    content_type = "text/html" if stage == "render" else "application/json"
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type=content_type)
