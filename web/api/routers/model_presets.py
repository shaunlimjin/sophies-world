"""Model preset catalog endpoint."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends

from web.api.deps import get_repo_root

router = APIRouter(prefix="/api/model-presets", tags=["model-presets"])


@router.get("")
def get_model_presets(repo_root: Path = Depends(get_repo_root)):
    sys.path.insert(0, str(repo_root / "scripts"))
    from providers.model_presets import load_presets, STRATEGY_REQUIRES_TOOLS

    presets_raw = load_presets(repo_root)
    presets_out = [
        {
            "name": name,
            "label": p.get("label", name),
            "provider": p.get("provider"),
            "supports_tools": bool(p.get("supports_tools", False)),
        }
        for name, p in presets_raw.items()
    ]

    # Pipeline defaults (synthesis/ranking model names) for UI pre-selection.
    defaults: dict = {}
    pipeline_path = repo_root / "config" / "pipelines" / "default.yaml"
    if pipeline_path.exists():
        data = yaml.safe_load(pipeline_path.read_text(encoding="utf-8")) or {}
        models = data.get("models", {}) or {}
        for stage in ("synthesis", "ranking"):
            value = models.get(stage)
            # Only include if it's already a preset name (string). Inline dicts
            # are legacy and not surfaced as defaults to the UI.
            if isinstance(value, str):
                defaults[stage] = value

    return {
        "presets": presets_out,
        "strategy_requirements": {
            strategy: {"requires_tools": requires}
            for strategy, requires in STRATEGY_REQUIRES_TOOLS.items()
        },
        "defaults": defaults,
    }
