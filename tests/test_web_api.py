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


# ---------------------------------------------------------------------------
# Runs endpoints
# ---------------------------------------------------------------------------

def test_list_runs_empty_when_no_approaches(client):
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_run_and_list(client):
    resp = client.post("/api/runs", json={"name": "approach-a"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "approach-a"
    assert body["stage_statuses"]["research"] == "pending"

    resp2 = client.get("/api/runs")
    assert any(r["name"] == "approach-a" for r in resp2.json())


def test_create_run_409_on_collision(client):
    client.post("/api/runs", json={"name": "dup-run"})
    resp = client.post("/api/runs", json={"name": "dup-run"})
    assert resp.status_code == 409


def test_get_run_state_404_for_missing_run(client):
    resp = client.get("/api/runs/nonexistent")
    assert resp.status_code == 404


def test_get_run_state_returns_all_stages_pending(client):
    client.post("/api/runs", json={"name": "fresh-run"})
    resp = client.get("/api/runs/fresh-run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "fresh-run"
    assert len(body["stages"]) == 4
    assert all(s["status"] == "pending" for s in body["stages"])


# ---------------------------------------------------------------------------
# Stage endpoints
# ---------------------------------------------------------------------------

def test_trigger_stage_409_if_already_running(client, repo_root):
    client.post("/api/runs", json={"name": "run-a"})
    # Create a running sentinel manually
    sentinel = repo_root / "artifacts" / "approaches" / "run-a" / ".stage-research.running"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.touch()
    resp = client.post("/api/runs/run-a/stages/research", json={})
    assert resp.status_code == 409


def test_trigger_stage_404_if_run_missing(client):
    resp = client.post("/api/runs/nope/stages/research", json={})
    assert resp.status_code == 404


def test_artifact_endpoint_404_if_missing(client):
    client.post("/api/runs", json={"name": "run-b"})
    resp = client.get("/api/runs/run-b/stages/research/artifact")
    assert resp.status_code == 404


def test_artifact_endpoint_returns_json(client, repo_root):
    from datetime import date
    today = date.today()
    client.post("/api/runs", json={"name": "run-c"})
    ar = repo_root / "artifacts" / "approaches" / "run-c" / "research"
    ar.mkdir(parents=True)
    (ar / f"sophie-{today.isoformat()}-raw.json").write_text('{"issue_date": "test"}')
    resp = client.get("/api/runs/run-c/stages/research/artifact")
    assert resp.status_code == 200
    assert "issue_date" in resp.text


# ---------------------------------------------------------------------------
# Compare endpoint
# ---------------------------------------------------------------------------

def test_compare_returns_null_for_missing_artifact(client, repo_root):
    from datetime import date
    today = date.today()
    client.post("/api/runs", json={"name": "left-run"})
    client.post("/api/runs", json={"name": "right-run"})
    # Only create right artifact
    ar = repo_root / "artifacts" / "approaches" / "right-run" / "research"
    ar.mkdir(parents=True)
    (ar / f"sophie-{today.isoformat()}-raw.json").write_text('{"issue_date": "test"}')

    resp = client.get("/compare?a=left-run&b=right-run&stage=research")
    assert resp.status_code == 200
    body = resp.json()
    assert body["left"] is None
    assert body["right"] is not None


def test_compare_returns_both_artifacts(client, repo_root):
    from datetime import date
    today = date.today()
    for name in ("run-x", "run-y"):
        client.post("/api/runs", json={"name": name})
        ar = repo_root / "artifacts" / "approaches" / name / "research"
        ar.mkdir(parents=True)
        (ar / f"sophie-{today.isoformat()}-raw.json").write_text(f'{{"run": "{name}"}}')
    resp = client.get("/compare?a=run-x&b=run-y&stage=research")
    assert resp.status_code == 200
    assert "run-x" in resp.json()["left"]
    assert "run-y" in resp.json()["right"]


# ---------------------------------------------------------------------------
# Promote endpoint
# ---------------------------------------------------------------------------

def test_promote_preview_shows_add_action(client, repo_root):
    from datetime import date
    today = date.today()
    client.post("/api/runs", json={"name": "winner"})
    ar = repo_root / "artifacts" / "approaches" / "winner" / "newsletters"
    ar.mkdir(parents=True)
    (ar / f"sophies-world-{today.isoformat()}.html").write_text("<html>winner</html>")

    resp = client.post("/api/runs/winner/promote/preview", json={"to": "staging"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["to"] == "staging"
    assert len(body["changes"]) == 1
    assert body["changes"][0]["action"] in ("add", "replace")


def test_promote_apply_copies_newsletter(client, repo_root):
    from datetime import date
    today = date.today()
    client.post("/api/runs", json={"name": "winner2"})
    ar = repo_root / "artifacts" / "approaches" / "winner2" / "newsletters"
    ar.mkdir(parents=True)
    html_content = "<html>winner newsletter</html>"
    (ar / f"sophies-world-{today.isoformat()}.html").write_text(html_content)

    resp = client.post(
        "/api/runs/winner2/promote/apply",
        json={"to": "staging", "confirmed": True}
    )
    assert resp.status_code == 200
    dest = repo_root / "newsletters" / "staging" / f"sophies-world-{today.isoformat()}.html"
    assert dest.exists()
    assert dest.read_text() == html_content


def test_trigger_stage_merges_settings_json_into_overrides(client, repo_root):
    """The trigger endpoint should pass settings.json values to the runner."""
    import json
    captured = {}

    class FakeRunner:
        def __init__(self, *a, **kw): pass
        def trigger(self, name, stage, overrides):
            captured["overrides"] = overrides
        def is_running(self, name, stage): return False

    from web.api.services import stage_runner as sr_module
    original = sr_module.StageRunner
    sr_module.StageRunner = FakeRunner

    try:
        ar = repo_root / "artifacts" / "approaches" / "test-run"
        ar.mkdir(parents=True)
        (ar / "settings.json").write_text(json.dumps({
            "synthesis_provider": "hosted_packet_synthesis",
            "synthesis_model": "minimax-m2",
        }))

        resp = client.post("/api/runs/test-run/stages/synthesis", json={"provider_overrides": {}})
        assert resp.status_code == 200
        assert captured["overrides"]["synthesis_model"] == "minimax-m2"
        assert captured["overrides"]["synthesis_provider"] == "hosted_packet_synthesis"
    finally:
        sr_module.StageRunner = original


def test_trigger_stage_request_overrides_win_over_settings(client, repo_root):
    """When the trigger body sets a key, it overrides settings.json."""
    import json
    captured = {}

    class FakeRunner:
        def __init__(self, *a, **kw): pass
        def trigger(self, name, stage, overrides):
            captured["overrides"] = overrides
        def is_running(self, name, stage): return False

    from web.api.services import stage_runner as sr_module
    original = sr_module.StageRunner
    sr_module.StageRunner = FakeRunner

    try:
        ar = repo_root / "artifacts" / "approaches" / "test-run"
        ar.mkdir(parents=True)
        (ar / "settings.json").write_text(json.dumps({"synthesis_model": "claude-opus"}))

        resp = client.post(
            "/api/runs/test-run/stages/synthesis",
            json={"provider_overrides": {"synthesis_model": "minimax-m2"}},
        )
        assert resp.status_code == 200
        assert captured["overrides"]["synthesis_model"] == "minimax-m2"
    finally:
        sr_module.StageRunner = original