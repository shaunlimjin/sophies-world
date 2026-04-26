"""YAML config read/write for the admin API."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import yaml

_CONFIG_FILES = {
    "child": "config/children/sophie.yaml",
    "pipeline": "config/pipelines/default.yaml",
    "research": "config/research.yaml",
}


def _resolve_path(repo_root: Path, file_key: str) -> Optional[Path]:
    if file_key in _CONFIG_FILES:
        return repo_root / _CONFIG_FILES[file_key]
    if file_key.startswith("section/"):
        section_id = file_key[len("section/") :]
        if "/" not in section_id and section_id.replace("_", "").isalpha():
            return repo_root / "config" / "sections" / f"{section_id}.yaml"
    return None


def list_config_keys(repo_root: Path) -> list[str]:
    keys = list(_CONFIG_FILES.keys())
    sections_dir = repo_root / "config" / "sections"
    if sections_dir.exists():
        for f in sorted(sections_dir.glob("*.yaml")):
            keys.append(f"section/{f.stem}")
    return keys


def read_config(repo_root: Path, file_key: str) -> str:
    path = _resolve_path(repo_root, file_key)
    if path is None or not path.exists():
        raise FileNotFoundError(f"Config not found: {file_key}")
    return path.read_text(encoding="utf-8")


def write_config(repo_root: Path, file_key: str, content: str) -> None:
    path = _resolve_path(repo_root, file_key)
    if path is None:
        raise ValueError(f"Unknown config key: {file_key}")
    yaml.safe_load(content)  # raises yaml.YAMLError if invalid
    path.write_text(content, encoding="utf-8")
