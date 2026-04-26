"""FastAPI dependency: inject repo_root from app state."""
from fastapi import Request
from pathlib import Path


def get_repo_root(request: Request) -> Path:
    return request.app.state.repo_root
