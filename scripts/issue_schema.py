#!/usr/bin/env python3
"""Structured issue schema helpers for Sophie's World."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


ARTIFACTS_DIRNAME = "artifacts"
ISSUES_DIRNAME = "issues"


def get_issue_artifacts_dir(repo_root: Path) -> Path:
    return repo_root / ARTIFACTS_DIRNAME / ISSUES_DIRNAME


def get_issue_artifact_path(repo_root: Path, child_id: str, issue_date: str) -> Path:
    return get_issue_artifacts_dir(repo_root) / f"{child_id}-{issue_date}.json"


def write_issue_artifact(repo_root: Path, issue: Dict[str, Any]) -> Path:
    child_id = issue.get("child_id")
    issue_date = issue.get("issue_date")
    if not child_id or not issue_date:
        raise ValueError("issue artifact requires child_id and issue_date")
    out_dir = get_issue_artifacts_dir(repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = get_issue_artifact_path(repo_root, child_id, issue_date)
    out_path.write_text(json.dumps(issue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def load_issue_artifact(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_issue_artifact(issue: Dict[str, Any]) -> None:
    required_top = ["issue_date", "issue_number", "child_id", "theme_id", "editorial", "sections", "footer"]
    missing_top = [key for key in required_top if key not in issue]
    if missing_top:
        raise ValueError(f"issue artifact missing required top-level fields: {missing_top}")

    sections = issue.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("issue artifact requires a non-empty sections list")

    for idx, section in enumerate(sections):
        missing = [key for key in ["id", "title", "block_type", "items"] if key not in section]
        if missing:
            raise ValueError(f"section {idx} missing required fields: {missing}")
        if not isinstance(section["items"], list) or not section["items"]:
            raise ValueError(f"section {section.get('id', idx)} requires a non-empty items list")
