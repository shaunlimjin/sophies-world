import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import env_resolver


def test_get_artifacts_root_prod(tmp_path):
    result = env_resolver.get_artifacts_root(tmp_path, "prod")
    assert result == tmp_path / "artifacts"


def test_get_artifacts_root_staging(tmp_path):
    result = env_resolver.get_artifacts_root(tmp_path, "staging")
    assert result == tmp_path / "artifacts" / "staging"


def test_get_artifacts_root_approach(tmp_path):
    result = env_resolver.get_artifacts_root(tmp_path, "staging", "approach-b2-v2")
    assert result == tmp_path / "artifacts" / "approaches" / "approach-b2-v2"


def test_get_newsletters_dir_prod(tmp_path):
    result = env_resolver.get_newsletters_dir(tmp_path, "prod")
    assert result == tmp_path / "newsletters"


def test_get_newsletters_dir_staging(tmp_path):
    result = env_resolver.get_newsletters_dir(tmp_path, "staging")
    assert result == tmp_path / "newsletters" / "staging"


def test_get_newsletters_dir_approach(tmp_path):
    result = env_resolver.get_newsletters_dir(tmp_path, "staging", "approach-b2-v2")
    assert result == tmp_path / "artifacts" / "approaches" / "approach-b2-v2" / "newsletters"


def test_resolve_config_file_prod_returns_prod_path(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("x: 1")

    result = env_resolver.resolve_config_file(tmp_path, "prod", None, "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"


def test_resolve_config_file_staging_no_override_falls_back_to_prod(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("x: 1")

    result = env_resolver.resolve_config_file(tmp_path, "staging", None, "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"


def test_resolve_config_file_staging_uses_staging_override(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")

    result = env_resolver.resolve_config_file(tmp_path, "staging", None, "research.yaml")
    assert result == tmp_path / "staging" / "config" / "research.yaml"


def test_resolve_config_file_approach_prefers_approach_override(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")
    approach_dir = tmp_path / "staging" / "approaches" / "approach-b2-v2" / "config"
    approach_dir.mkdir(parents=True)
    (approach_dir / "research.yaml").write_text("approach: true")

    result = env_resolver.resolve_config_file(tmp_path, "staging", "approach-b2-v2", "research.yaml")
    assert result == approach_dir / "research.yaml"


def test_resolve_config_file_approach_falls_back_to_staging(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")
    approach_dir = tmp_path / "staging" / "approaches" / "approach-b2-v2" / "config"
    approach_dir.mkdir(parents=True)

    result = env_resolver.resolve_config_file(tmp_path, "staging", "approach-b2-v2", "research.yaml")
    assert result == tmp_path / "staging" / "config" / "research.yaml"


def test_resolve_config_file_approach_falls_back_to_prod(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")

    result = env_resolver.resolve_config_file(tmp_path, "staging", "approach-b2-v2", "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"


def test_resolve_config_file_prod_ignores_staging_overrides(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")

    result = env_resolver.resolve_config_file(tmp_path, "prod", None, "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"
