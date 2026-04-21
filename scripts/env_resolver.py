#!/usr/bin/env python3
"""Overlay resolution and output directory routing for prod/staging/approach environments."""

from pathlib import Path
from typing import Optional

ENV_PROD = "prod"
ENV_STAGING = "staging"


def get_artifacts_root(repo_root: Path, env: str, approach: Optional[str] = None) -> Path:
    if approach:
        return repo_root / "artifacts" / "approaches" / approach
    if env == ENV_STAGING:
        return repo_root / "artifacts" / "staging"
    return repo_root / "artifacts"


def get_newsletters_dir(repo_root: Path, env: str, approach: Optional[str] = None) -> Path:
    if approach:
        return repo_root / "artifacts" / "approaches" / approach / "newsletters"
    if env == ENV_STAGING:
        return repo_root / "newsletters" / "staging"
    return repo_root / "newsletters"


def resolve_config_file(
    repo_root: Path, env: str, approach: Optional[str], relative: str
) -> Path:
    """Return the config file path using overlay resolution: approach > staging > prod.

    For prod env, always returns the prod baseline. For staging/approach envs,
    checks each layer in order and returns the first existing file. Falls back
    to the prod baseline path (even if it doesn't exist — the caller handles missing files).
    """
    prod_path = repo_root / "config" / relative

    if env == ENV_PROD:
        print(f"  [config] {relative} → config/{relative}")
        return prod_path

    candidates: list = []
    if approach:
        candidates.append((
            f"staging/approaches/{approach}/config/{relative}",
            repo_root / "staging" / "approaches" / approach / "config" / relative,
        ))
    candidates.append((
        f"staging/config/{relative}",
        repo_root / "staging" / "config" / relative,
    ))

    for label, path in candidates:
        if path.exists():
            print(f"  [config] {relative} → {label}")
            return path

    print(f"  [config] {relative} → config/{relative} (prod baseline fallback)")
    return prod_path
