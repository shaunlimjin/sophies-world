"""FastAPI app factory for Sophie's World admin API."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def create_app(repo_root: Path = REPO_ROOT) -> FastAPI:
    app = FastAPI(title="Sophie's World Admin API")
    app.state.repo_root = repo_root
    app.state.stage_queues: dict = {}  # key: (run_name, stage) → asyncio.Queue

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from web.api.routers import configs, runs, stages, compare, promote
    app.include_router(configs.router)
    app.include_router(runs.router)
    app.include_router(stages.router)
    app.include_router(compare.router)
    app.include_router(promote.router)

    ui_dist = repo_root / "web" / "ui" / "dist"
    if ui_dist.exists():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


app = create_app()
