"""Tests for the config-tree schema validator in issue_schema."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import issue_schema


REPO_ROOT = Path(__file__).parent.parent


def _make_repo(tmp_path: Path) -> Path:
    """Copy schemas into a fresh tmp_path repo and return the repo root."""
    (tmp_path / "config").mkdir()
    shutil.copytree(
        REPO_ROOT / "config" / "schemas",
        tmp_path / "config" / "schemas",
    )
    return tmp_path


def test_live_config_validates_cleanly():
    """The checked-in config/ tree must pass validation."""
    errors = issue_schema.validate_config_tree(REPO_ROOT)
    assert errors == [], "live config/ failed validation:\n" + "\n".join(errors)


def test_missing_required_field_in_section(tmp_path):
    repo = _make_repo(tmp_path)
    sections = repo / "config" / "sections"
    sections.mkdir()
    (sections / "bad.yaml").write_text(
        "id: bad\n"
        "display:\n"
        "  title: Hi\n"
        "  block_type: fact_list\n"
        "editorial:\n"
        "  goal: hello\n",
        encoding="utf-8",
    )
    errors = issue_schema.validate_config_tree(repo)
    assert any("link_style" in e for e in errors), errors


def test_invalid_enum_value_in_section(tmp_path):
    repo = _make_repo(tmp_path)
    sections = repo / "config" / "sections"
    sections.mkdir()
    (sections / "weird.yaml").write_text(
        "id: weird\n"
        "display:\n"
        "  title: Hi\n"
        "  block_type: not_a_real_type\n"
        "  link_style: link-blue\n"
        "editorial:\n"
        "  goal: hello\n",
        encoding="utf-8",
    )
    errors = issue_schema.validate_config_tree(repo)
    assert any("block_type" in e or "not_a_real_type" in e for e in errors), errors


def test_malformed_yaml_reports_parse_error(tmp_path):
    repo = _make_repo(tmp_path)
    themes = repo / "config" / "themes"
    themes.mkdir()
    (themes / "default.yaml").write_text(
        "theme_id: default\n  bad-indent-here:\n",
        encoding="utf-8",
    )
    errors = issue_schema.validate_config_tree(repo)
    assert any("YAML parse error" in e for e in errors), errors


def test_active_section_without_section_file(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "config" / "children").mkdir()
    (repo / "config" / "sections").mkdir()
    (repo / "config" / "children" / "alex.yaml").write_text(
        "id: alex\n"
        "name: Alex\n"
        "newsletter:\n"
        "  active_sections:\n"
        "    - does_not_exist\n"
        "  theme: default\n",
        encoding="utf-8",
    )
    errors = issue_schema.validate_config_tree(repo)
    assert any("does_not_exist" in e for e in errors), errors


def test_classify_config_file_routes_correctly():
    config_dir = REPO_ROOT / "config"
    assert issue_schema.classify_config_file(config_dir, config_dir / "sections.yaml") == "sections_catalog"
    assert issue_schema.classify_config_file(config_dir, config_dir / "research.yaml") == "research"
    assert issue_schema.classify_config_file(config_dir, config_dir / "children" / "sophie.yaml") == "child"
    assert issue_schema.classify_config_file(config_dir, config_dir / "sections" / "weird_but_true.yaml") == "section"
    assert issue_schema.classify_config_file(config_dir, config_dir / "themes" / "default.yaml") == "theme"
    assert issue_schema.classify_config_file(config_dir, config_dir / "pipelines" / "default.yaml") == "pipeline"


def test_validate_or_raise_raises_on_error(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "config" / "themes").mkdir()
    (repo / "config" / "themes" / "default.yaml").write_text(
        "theme_id: default\n",  # missing required template_path
        encoding="utf-8",
    )
    with pytest.raises(issue_schema.ConfigValidationError) as excinfo:
        issue_schema.validate_config_tree_or_raise(repo)
    assert "template_path" in str(excinfo.value)


def test_cli_returns_zero_on_clean_config(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    (repo / "config" / "themes").mkdir()
    (repo / "config" / "themes" / "default.yaml").write_text(
        "theme_id: default\ntemplate_path: scripts/template.html\n",
        encoding="utf-8",
    )
    rc = issue_schema._cli(["--repo-root", str(repo)])
    assert rc == 0


def test_cli_returns_nonzero_on_invalid_config(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    (repo / "config" / "themes").mkdir()
    (repo / "config" / "themes" / "default.yaml").write_text(
        "template_path: scripts/template.html\n",  # missing theme_id
        encoding="utf-8",
    )
    rc = issue_schema._cli(["--repo-root", str(repo)])
    assert rc == 1
