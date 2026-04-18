import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import generate


def test_get_next_issue_number_no_files(tmp_path):
    assert generate.get_next_issue_number(tmp_path) == 1


def test_get_next_issue_number_with_existing(tmp_path):
    (tmp_path / "sophies-world-2026-04-09.html").touch()
    (tmp_path / "sophies-world-2026-04-16.html").touch()
    assert generate.get_next_issue_number(tmp_path) == 3


def test_get_output_path(tmp_path):
    result = generate.get_output_path(tmp_path, date(2026, 4, 23))
    assert result == tmp_path / "sophies-world-2026-04-23.html"


def test_parse_claude_output_success():
    payload = json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "<html><body>Hello</body></html>",
    })
    assert generate.parse_claude_output(payload) == "<html><body>Hello</body></html>"


def test_parse_claude_output_error():
    payload = json.dumps({
        "type": "result",
        "subtype": "error",
        "is_error": True,
        "result": "",
    })
    assert generate.parse_claude_output(payload) is None


def test_parse_claude_output_non_html():
    payload = json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "Here is your newsletter:",
    })
    assert generate.parse_claude_output(payload) is None


def test_get_recent_headlines_no_previous(tmp_path):
    assert generate.get_recent_headlines(tmp_path, date(2026, 4, 18)) == []


def test_get_recent_headlines_excludes_today(tmp_path):
    (tmp_path / "sophies-world-2026-04-18.html").write_text(
        "<h3>Today's Story</h3>"
    )
    assert generate.get_recent_headlines(tmp_path, date(2026, 4, 18)) == []


def test_get_recent_headlines_returns_previous_h3s(tmp_path):
    (tmp_path / "sophies-world-2026-04-11.html").write_text(
        "<h3>🌍 Big Story One</h3><h3>🎤 K-pop News</h3>"
    )
    result = generate.get_recent_headlines(tmp_path, date(2026, 4, 18))
    assert result == ["🌍 Big Story One", "🎤 K-pop News"]


def test_get_recent_headlines_uses_most_recent(tmp_path):
    (tmp_path / "sophies-world-2026-04-04.html").write_text("<h3>Old Story</h3>")
    (tmp_path / "sophies-world-2026-04-11.html").write_text("<h3>Recent Story</h3>")
    result = generate.get_recent_headlines(tmp_path, date(2026, 4, 18))
    assert result == ["Recent Story"]


def test_idempotent_skips_existing(tmp_path, capsys):
    existing = tmp_path / "sophies-world-2026-04-23.html"
    existing.write_text("<html/>")
    result = generate.check_output_exists(existing)
    assert result is True
    captured = capsys.readouterr()
    assert "already exists" in captured.out


def test_idempotent_proceeds_when_missing(tmp_path):
    path = tmp_path / "sophies-world-2026-04-23.html"
    assert generate.check_output_exists(path) is False
