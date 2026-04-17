import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import send


def test_load_config_success(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "GMAIL_USER=sender@gmail.com\n"
        "GMAIL_APP_PASSWORD=abcd efgh ijkl mnop\n"
        "RECIPIENT_EMAIL=sophie@gmail.com\n"
    )
    config = send.load_config(env)
    assert config["GMAIL_USER"] == "sender@gmail.com"
    assert config["GMAIL_APP_PASSWORD"] == "abcd efgh ijkl mnop"
    assert config["RECIPIENT_EMAIL"] == "sophie@gmail.com"


def test_load_config_missing_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GMAIL_USER=sender@gmail.com\n")
    try:
        send.load_config(env)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "GMAIL_APP_PASSWORD" in str(e)
        assert "RECIPIENT_EMAIL" in str(e)


def test_load_config_missing_file(tmp_path):
    env = tmp_path / ".env"
    try:
        send.load_config(env)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "GMAIL_USER" in str(e)


def test_find_newsletter_found(tmp_path):
    (tmp_path / "sophies-world-2026-04-17.html").write_text("<html/>")
    result = send.find_newsletter(tmp_path, date(2026, 4, 17))
    assert result == tmp_path / "sophies-world-2026-04-17.html"


def test_find_newsletter_not_found(tmp_path):
    result = send.find_newsletter(tmp_path, date(2026, 4, 17))
    assert result is None


def test_build_subject():
    result = send.build_subject(date(2026, 4, 17), 2)
    assert result == "Sophie's World · April 17, 2026 · Issue #2"


def test_build_message():
    msg = send.build_message(
        from_addr="sender@gmail.com",
        to_addr="sophie@gmail.com",
        subject="Sophie's World · April 17, 2026 · Issue #2",
        html_body="<html><body>Hello</body></html>",
    )
    assert msg["From"] == "sender@gmail.com"
    assert msg["To"] == "sophie@gmail.com"
    assert msg["Subject"] == "Sophie's World · April 17, 2026 · Issue #2"
    payload = msg.get_payload()
    assert any("<html>" in part.get_payload(decode=True).decode("utf-8") for part in payload)
