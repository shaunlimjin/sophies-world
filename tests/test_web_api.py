"""API unit tests using FastAPI TestClient."""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fastapi.testclient import TestClient


@pytest.fixture
def repo_root(tmp_path):
    """Minimal repo_root with config files."""
    (tmp_path / "config" / "children").mkdir(parents=True)
    (tmp_path / "config" / "pipelines").mkdir(parents=True)
    (tmp_path / "config" / "sections").mkdir(parents=True)
    (tmp_path / "config" / "children" / "sophie.yaml").write_text("id: sophie\n")
    (tmp_path / "config" / "pipelines" / "default.yaml").write_text("pipeline:\n  content_provider: hosted_packet_synthesis\n")
    (tmp_path / "config" / "research.yaml").write_text("queries: []\n")
    (tmp_path / "config" / "sections" / "world_watch.yaml").write_text("title: World Watch\n")
    return tmp_path


@pytest.fixture
def client(repo_root):
    from web.api.main import create_app
    app = create_app(repo_root=repo_root)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Configs endpoints
# ---------------------------------------------------------------------------

def test_list_configs_returns_expected_keys(client):
    resp = client.get("/api/configs")
    assert resp.status_code == 200
    keys = resp.json()
    assert "child" in keys
    assert "pipeline" in keys
    assert "research" in keys
    assert "section/world_watch" in keys


def test_get_config_returns_yaml_string(client):
    resp = client.get("/api/configs/child")
    assert resp.status_code == 200
    assert "sophie" in resp.json()["content"]


def test_get_config_404_for_unknown_key(client):
    resp = client.get("/api/configs/doesnotexist")
    assert resp.status_code == 404


def test_put_config_writes_valid_yaml(client, repo_root):
    resp = client.put("/api/configs/child", json={"content": "id: test\n"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "test" in (repo_root / "config" / "children" / "sophie.yaml").read_text()


def test_put_config_rejects_invalid_yaml(client):
    resp = client.put("/api/configs/child", json={"content": "key: [unclosed"})
    assert resp.status_code == 400
    assert "YAML" in resp.json()["detail"]