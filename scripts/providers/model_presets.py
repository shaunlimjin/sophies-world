"""Preset registry loader and resolver.

A preset is a named model configuration that maps to the {provider, model,
base_url?, api_key_env?} dict accepted by make_provider(). Presets live in
config/model_presets.yaml and are referenced by name from
config/pipelines/default.yaml and from per-run settings.json.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

# Internal-only fields that should not be passed to make_provider().
_INTERNAL_FIELDS = {"supports_tools", "label"}

# Strategy → does it need a tool-calling-capable model.
# Used by the API and UI to filter incompatible preset choices.
STRATEGY_REQUIRES_TOOLS: dict[str, bool] = {
    "hosted_integrated_search": True,
    "hosted_packet_synthesis": False,
    "hosted_model_ranker": False,
}


def load_presets(repo_root: Path) -> dict[str, dict]:
    """Read config/model_presets.yaml. Returns {name: preset_dict}.

    Raises:
        FileNotFoundError: if config/model_presets.yaml is missing.
    """
    path = Path(repo_root) / "config" / "model_presets.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Preset registry not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("presets", {}) or {}


def resolve_preset(name: str, presets: dict) -> dict:
    """Return {provider, model, base_url?, api_key_env?} for make_provider().

    Strips internal-only fields (supports_tools, label).

    Raises:
        ValueError: if preset name not found.
    """
    if name not in presets:
        raise ValueError(
            f"Unknown model preset: {name!r}. "
            f"Available: {sorted(presets.keys())}"
        )
    src = presets[name]
    return {k: v for k, v in src.items() if k not in _INTERNAL_FIELDS}


def resolve_model_config(value: Union[str, dict], presets: dict) -> dict:
    """Accept either a preset name (str) or an inline dict.

    String values are dereferenced via resolve_preset. Dict values are
    returned unchanged so existing inline-dict configs (e.g. in staging/
    overlays) keep working.
    """
    if isinstance(value, str):
        return resolve_preset(value, presets)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Expected preset name (str) or inline dict, got {type(value).__name__}")
