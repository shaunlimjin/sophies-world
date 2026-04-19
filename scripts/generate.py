#!/usr/bin/env python3
"""Generate a Sophie's World newsletter issue."""

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import List

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install it with: pip3 install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

from content_stage import build_content_prompt, parse_content_output, run_content_provider
from issue_schema import validate_issue_artifact, write_issue_artifact
from render_stage import load_template, render_issue_html

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
NEWSLETTERS_DIR = REPO_ROOT / "newsletters"


def load_config(repo_root: Path) -> dict:
    config_dir = repo_root / "config"

    child_path = config_dir / "children" / "sophie.yaml"
    if not child_path.exists():
        print(f"Error: child config not found: {child_path}", file=sys.stderr)
        sys.exit(1)
    profile = yaml.safe_load(child_path.read_text(encoding="utf-8"))

    sections_path = config_dir / "sections.yaml"
    if not sections_path.exists():
        print(f"Error: sections config not found: {sections_path}", file=sys.stderr)
        sys.exit(1)
    sections_data = yaml.safe_load(sections_path.read_text(encoding="utf-8"))
    sections = sections_data.get("sections", {})

    theme_name = profile.get("newsletter", {}).get("theme", "default")
    theme_path = config_dir / "themes" / f"{theme_name}.yaml"
    if not theme_path.exists():
        print(f"Error: theme config not found: {theme_path}", file=sys.stderr)
        sys.exit(1)
    theme = yaml.safe_load(theme_path.read_text(encoding="utf-8"))

    active_sections = profile.get("newsletter", {}).get("active_sections", [])
    missing = [s for s in active_sections if s not in sections]
    if missing:
        print(f"Error: active_sections reference unknown section IDs: {missing}", file=sys.stderr)
        sys.exit(1)

    return {"profile": profile, "sections": sections, "theme": theme}


def get_template_path(repo_root: Path, theme: dict) -> Path:
    template_rel = theme.get("template_path")
    if not template_rel:
        print("Error: theme config missing required field: template_path", file=sys.stderr)
        sys.exit(1)
    template_path = repo_root / template_rel
    if not template_path.exists():
        print(f"Error: template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)
    return template_path


def get_next_issue_number(newsletters_dir: Path) -> int:
    existing = list(newsletters_dir.glob("sophies-world-*.html"))
    return len(existing) + 1


def get_recent_headlines(newsletters_dir: Path, today: date) -> List[str]:
    today_name = f"sophies-world-{today.strftime('%Y-%m-%d')}.html"
    files = sorted(newsletters_dir.glob("sophies-world-*.html"))
    previous = [f for f in files if f.name != today_name]
    if not previous:
        return []
    content = previous[-1].read_text(encoding="utf-8")
    raw = re.findall(r"<h3[^>]*>(.*?)</h3>", content, re.DOTALL)
    return [re.sub(r"<[^>]+>", "", h).strip() for h in raw if h.strip()]


def get_output_path(newsletters_dir: Path, issue_date: date) -> Path:
    filename = f"sophies-world-{issue_date.strftime('%Y-%m-%d')}.html"
    return newsletters_dir / filename


def check_output_exists(output_path: Path) -> bool:
    if output_path.exists():
        print(f"Output already exists, skipping: {output_path}")
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Write to newsletters/test/ and always regenerate")
    args = parser.parse_args()

    today = date.today()
    issue_num = get_next_issue_number(NEWSLETTERS_DIR)
    recent_headlines = get_recent_headlines(NEWSLETTERS_DIR, today)

    if args.test:
        output_dir = NEWSLETTERS_DIR / "test"
        output_dir.mkdir(exist_ok=True)
    else:
        output_dir = NEWSLETTERS_DIR

    output_path = get_output_path(output_dir, today)

    if not args.test and check_output_exists(output_path):
        return

    config = load_config(REPO_ROOT)
    template_path = get_template_path(REPO_ROOT, config["theme"])
    template_html = load_template(template_path)

    print(f"Generating structured content for Issue #{issue_num}...")
    prompt = build_content_prompt(today, issue_num, config, recent_headlines)
    raw_output = run_content_provider(prompt, REPO_ROOT)
    issue = parse_content_output(raw_output, REPO_ROOT)
    validate_issue_artifact(issue)
    artifact_path = write_issue_artifact(REPO_ROOT, issue)

    print(f"Rendering HTML from artifact: {artifact_path}")
    html = render_issue_html(template_html, issue)
    output_path.write_text(html, encoding="utf-8")
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
