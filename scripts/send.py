#!/usr/bin/env python3
"""Send today's Sophie's World newsletter via Gmail SMTP."""

import argparse
import smtplib
import sys
from datetime import date
from email.headerregistry import Address
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from novelty_gate import assert_issue_novelty

REPO_ROOT = Path(__file__).parent.parent
NEWSLETTERS_DIR = REPO_ROOT / "newsletters"
ENV_PATH = REPO_ROOT / ".env"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def load_config(env_path: Path) -> dict:
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    required = ["GMAIL_USER", "GMAIL_APP_PASSWORD", "RECIPIENT_EMAIL"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise ValueError(f"Missing required .env variables: {', '.join(missing)}")
    return config


def find_newsletter(newsletters_dir: Path, today: date) -> Optional[Path]:
    filename = f"sophies-world-{today.strftime('%Y-%m-%d')}.html"
    path = newsletters_dir / filename
    return path if path.exists() else None


def get_issue_number(newsletters_dir: Path) -> int:
    existing = list(newsletters_dir.glob("sophies-world-*.html"))
    return len(existing)


def build_subject(issue_date: date, issue_num: int) -> str:
    formatted = f"{issue_date.strftime('%B')} {issue_date.day}, {issue_date.strftime('%Y')}"
    return f"Sophie's World · {formatted} · Issue #{issue_num}"


def build_message(from_addr: str, to_addr: str, subject: str, html_body: str, display_name: str = "Daddy") -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    local_part, domain = from_addr.split("@", 1)
    msg["From"] = str(Address(display_name, local_part, domain))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_email(config: dict, msg: MIMEMultipart) -> None:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(config["GMAIL_USER"], config["GMAIL_APP_PASSWORD"])
        server.sendmail(config["GMAIL_USER"], config["RECIPIENT_EMAIL"], msg.as_string())


def parse_issue_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--date must be YYYY-MM-DD") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=parse_issue_date, default=None, help="Issue date to send (YYYY-MM-DD; default: today)")
    args = parser.parse_args()

    try:
        config = load_config(ENV_PATH)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    today = args.date or date.today()
    newsletter = find_newsletter(NEWSLETTERS_DIR, today)
    if newsletter is None:
        print(f"No newsletter found for {today}. Run generate.py first.", file=sys.stderr)
        sys.exit(1)

    issue_num = get_issue_number(NEWSLETTERS_DIR)
    subject = build_subject(today, issue_num)
    issue_artifact = REPO_ROOT / "artifacts" / "issues" / f"sophie-{today.strftime('%Y-%m-%d')}.json"
    if issue_artifact.exists():
        import json
        try:
            issue = json.loads(issue_artifact.read_text(encoding="utf-8"))
            assert_issue_novelty(issue, REPO_ROOT)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            print("Send blocked. Regenerate the issue with fresh stories/facts before sending.", file=sys.stderr)
            sys.exit(1)

    html_body = newsletter.read_text(encoding="utf-8")
    msg = build_message(config["GMAIL_USER"], config["RECIPIENT_EMAIL"], subject, html_body)

    print(f"Sending Issue #{issue_num} to {config['RECIPIENT_EMAIL']}...")
    try:
        send_email(config, msg)
    except smtplib.SMTPException as e:
        print(f"SMTP error: {e}", file=sys.stderr)
        sys.exit(1)
    print("Sent!")


if __name__ == "__main__":
    main()
