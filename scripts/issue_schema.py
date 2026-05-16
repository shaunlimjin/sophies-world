#!/usr/bin/env python3
"""Structured issue schema helpers and config-tree validation for Sophie's World."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ARTIFACTS_DIRNAME = "artifacts"
ISSUES_DIRNAME = "issues"

CONFIG_DIRNAME = "config"
SCHEMAS_DIRNAME = "schemas"

SCHEMA_FILENAMES = {
    "child": "child.schema.json",
    "section": "section.schema.json",
    "sections_catalog": "sections_catalog.schema.json",
    "theme": "theme.schema.json",
    "pipeline": "pipeline.schema.json",
    "research": "research.schema.json",
}


def get_issue_artifacts_dir(repo_root: Path, artifacts_root: Optional[Path] = None) -> Path:
    root = artifacts_root if artifacts_root is not None else repo_root / ARTIFACTS_DIRNAME
    return root / ISSUES_DIRNAME


def get_issue_artifact_path(
    repo_root: Path,
    child_id: str,
    issue_date: str,
    run_tag: Optional[str] = None,
    artifacts_root: Optional[Path] = None,
) -> Path:
    filename = f"{child_id}-{issue_date}"
    if run_tag:
        filename += f"-{run_tag}"
    filename += ".json"
    return get_issue_artifacts_dir(repo_root, artifacts_root) / filename


def write_issue_artifact(
    repo_root: Path,
    issue: Dict[str, Any],
    run_tag: Optional[str] = None,
    artifacts_root: Optional[Path] = None,
) -> Path:
    child_id = issue.get("child_id")
    issue_date = issue.get("issue_date")
    if not child_id or not issue_date:
        raise ValueError("issue artifact requires child_id and issue_date")
    out_dir = get_issue_artifacts_dir(repo_root, artifacts_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = get_issue_artifact_path(repo_root, child_id, issue_date, run_tag, artifacts_root)
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


# ---------------------------------------------------------------------------
# Config tree validation
# ---------------------------------------------------------------------------


class ConfigValidationError(Exception):
    """Raised when one or more configuration files fail schema validation."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(self._format_errors(errors))

    @staticmethod
    def _format_errors(errors: List[str]) -> str:
        header = f"Configuration validation failed ({len(errors)} error(s)):"
        return "\n".join([header, *[f"  - {e}" for e in errors]])


def _require_yaml():
    try:
        import yaml  # noqa: WPS433
    except ImportError as exc:
        raise ConfigValidationError([
            "PyYAML is required for config validation. Install with: pip3 install -r requirements.txt"
        ]) from exc
    return yaml


def _require_jsonschema():
    try:
        import jsonschema  # noqa: WPS433
    except ImportError as exc:
        raise ConfigValidationError([
            "jsonschema is required for config validation. Install with: pip3 install -r requirements.txt"
        ]) from exc
    return jsonschema


def load_schemas(repo_root: Path) -> Dict[str, Dict[str, Any]]:
    schemas_dir = repo_root / CONFIG_DIRNAME / SCHEMAS_DIRNAME
    schemas: Dict[str, Dict[str, Any]] = {}
    for key, filename in SCHEMA_FILENAMES.items():
        path = schemas_dir / filename
        if not path.exists():
            raise ConfigValidationError([f"schema file missing: {path}"])
        try:
            schemas[key] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigValidationError([f"schema file is not valid JSON: {path} ({exc})"]) from exc
    return schemas


def _iter_config_yaml_files(config_dir: Path) -> Iterable[Path]:
    for path in sorted(config_dir.rglob("*.yaml")):
        # Skip the schemas directory itself (these are JSON, but be defensive)
        if SCHEMAS_DIRNAME in path.relative_to(config_dir).parts:
            continue
        yield path
    for path in sorted(config_dir.rglob("*.yml")):
        if SCHEMAS_DIRNAME in path.relative_to(config_dir).parts:
            continue
        yield path


def classify_config_file(config_dir: Path, yaml_path: Path) -> Optional[str]:
    """Return the schema key to validate this file against, or None to skip."""
    try:
        rel_parts = yaml_path.relative_to(config_dir).parts
    except ValueError:
        return None

    if len(rel_parts) == 1:
        name = rel_parts[0]
        if name == "sections.yaml":
            return "sections_catalog"
        if name == "research.yaml":
            return "research"
        return None

    if len(rel_parts) >= 2:
        subdir = rel_parts[0]
        if subdir == "children":
            return "child"
        if subdir == "sections":
            return "section"
        if subdir == "themes":
            return "theme"
        if subdir == "pipelines":
            return "pipeline"
    return None


def _format_instance_path(abs_path: Iterable[Any]) -> str:
    parts = [str(p) for p in abs_path]
    return "/".join(parts) if parts else "<root>"


def _validate_file(
    yaml_path: Path,
    schema_key: str,
    schemas: Dict[str, Dict[str, Any]],
    repo_root: Path,
    yaml_module,
    jsonschema_module,
) -> List[str]:
    display_path = str(yaml_path.relative_to(repo_root))
    try:
        raw = yaml_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{display_path}: could not read file ({exc})"]

    try:
        data = yaml_module.safe_load(raw)
    except yaml_module.YAMLError as exc:
        return [f"{display_path}: YAML parse error ({exc})"]

    if data is None:
        return [f"{display_path}: file is empty or contains only null"]

    schema = schemas[schema_key]
    validator_cls = jsonschema_module.validators.validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except jsonschema_module.SchemaError as exc:
        return [f"{display_path}: internal schema error ({exc.message})"]

    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not errors:
        return []

    formatted: List[str] = []
    for err in errors:
        location = _format_instance_path(err.absolute_path)
        formatted.append(f"{display_path}: [{location}] {err.message}")
    return formatted


def _cross_check_active_sections(config_dir: Path, yaml_module) -> List[str]:
    """Ensure every child's active_sections reference a real section file."""
    errors: List[str] = []
    children_dir = config_dir / "children"
    sections_dir = config_dir / "sections"
    if not children_dir.exists() or not sections_dir.exists():
        return errors

    available = {p.stem for p in sections_dir.glob("*.yaml")}

    for child_path in sorted(children_dir.glob("*.yaml")):
        try:
            data = yaml_module.safe_load(child_path.read_text(encoding="utf-8"))
        except yaml_module.YAMLError:
            # parse errors are already reported by the main pass
            continue
        if not isinstance(data, dict):
            continue
        active = (data.get("newsletter") or {}).get("active_sections") or []
        display = str(child_path.relative_to(config_dir.parent))
        for section_id in active:
            if section_id not in available:
                errors.append(
                    f"{display}: newsletter.active_sections references unknown section '{section_id}' "
                    f"(expected config/sections/{section_id}.yaml)"
                )
    return errors


def validate_config_tree(repo_root: Path) -> List[str]:
    """Validate every YAML file under config/ against its schema.

    Returns a list of error messages; empty list means success. Does not raise.
    """
    yaml_module = _require_yaml()
    jsonschema_module = _require_jsonschema()

    config_dir = repo_root / CONFIG_DIRNAME
    if not config_dir.exists():
        return [f"config directory not found: {config_dir}"]

    schemas = load_schemas(repo_root)

    errors: List[str] = []
    validated = 0
    skipped: List[str] = []

    for yaml_path in _iter_config_yaml_files(config_dir):
        schema_key = classify_config_file(config_dir, yaml_path)
        if schema_key is None:
            skipped.append(str(yaml_path.relative_to(repo_root)))
            continue
        file_errors = _validate_file(
            yaml_path, schema_key, schemas, repo_root, yaml_module, jsonschema_module
        )
        errors.extend(file_errors)
        validated += 1

    errors.extend(_cross_check_active_sections(config_dir, yaml_module))

    print(f"[validate-config] checked {validated} YAML file(s) under config/")
    if skipped:
        print(f"[validate-config] skipped (no matching schema): {len(skipped)}")
    return errors


def validate_config_tree_or_raise(repo_root: Path) -> None:
    errors = validate_config_tree(repo_root)
    if errors:
        raise ConfigValidationError(errors)


def _cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate YAML config files under config/ against their JSON schemas."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root (defaults to the parent of scripts/).",
    )
    args = parser.parse_args(argv)

    try:
        errors = validate_config_tree(args.repo_root)
    except ConfigValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if errors:
        print(ConfigValidationError._format_errors(errors), file=sys.stderr)
        return 1

    print("[validate-config] OK — all configuration files passed schema validation.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
