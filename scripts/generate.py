#!/usr/bin/env python3
"""Generate a Sophie's World newsletter issue using the claude CLI."""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install it with: pip3 install pyyaml", file=sys.stderr)
    sys.exit(1)

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
NEWSLETTERS_DIR = REPO_ROOT / "newsletters"
TEMPLATE_PATH = SCRIPTS_DIR / "template.html"


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


def parse_claude_output(json_str: str) -> Optional[str]:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None
    if data.get("is_error") or not data.get("result"):
        return None
    result = data["result"]
    html_start = result.find("<")
    if html_start == -1:
        return None
    return result[html_start:]


def build_profile_description(profile: dict) -> str:
    name = profile.get("name", "Sophie")
    age_band = profile.get("age_band", "4th-grade")
    location = profile.get("location", "Fremont, California")
    cultural_parts = profile.get("cultural_context", [])
    cultural_str = ". ".join(cultural_parts) + "." if cultural_parts else ""
    active_interests = profile.get("interests", {}).get("active", [])
    interests_str = ", ".join(active_interests) if active_interests else ""
    return (
        f"{name} is a {age_band} student living in {location}. {cultural_str}\n"
        f"Active interests: {interests_str}."
    )


def build_section_rules(profile: dict, sections: dict) -> str:
    active_section_ids = profile.get("newsletter", {}).get("active_sections", [])
    lines = [
        "Newsletter sections to fill in (replace each <!-- PLACEHOLDER --> comment with real HTML content):",
        "",
        "1. DATE_BADGE — Format: <div class=\"date-badge\">📅 {month} {day}, {year} · Issue #{n}</div>",
        "",
        "2. GREETING — Warm personalised opening. Reference Sophie's name and something from this week.",
        "   Use <span>Sophie's World</span> for the newsletter name.",
        "",
    ]
    for i, section_id in enumerate(active_section_ids, start=3):
        section = sections[section_id]
        goal = section.get("goal", "")
        content_rules = section.get("content_rules", [])
        link_style = section.get("link_style", "")
        source_prefs = section.get("source_preferences", [])
        rules_str = "; ".join(content_rules) if content_rules else ""
        sources_str = ", ".join(source_prefs) if source_prefs else ""
        lines.append(f"{i}. {section_id.upper()} — {goal}")
        if rules_str:
            lines.append(f"   Content rules: {rules_str}")
        if link_style:
            lines.append(f"   Link style: {link_style}")
        if sources_str:
            lines.append(f"   Preferred sources: {sources_str}")
        lines.append("")

    footer_num = len(active_section_ids) + 3
    lines += [
        f"{footer_num}. FOOTER — Standard footer with issue number and date.",
        '    Format: <div class="footer" style="background:#fff;border-radius:0 0 24px 24px;margin-top:3px;">',
        '    <span class="hearts">💖 🌏 💖</span>',
        "    <strong>Sophie's World</strong> · Issue #{n} · {Month} {DD}, {YYYY}<br>",
        "    Made with love by Dad &amp; Claude 🤖❤️<br>",
        '    <span style="font-size:12px;color:#bbb;">Fremont, California ↔ Singapore</span></div>',
        "",
        "Reading level: 4th grade. Tone: warm, fun, curious. Use emojis naturally.",
        "Links: prefer Time for Kids, NewsForKids.net, Britannica, BBC Newsround, Nat Geo Kids.",
    ]
    return "\n".join(lines)


def build_prompt(template_html: str, issue_date: date, issue_num: int, config: dict, recent_headlines: List[str] = []) -> str:
    formatted_date = f"{issue_date.strftime('%B')} {issue_date.day}, {issue_date.strftime('%Y')}"
    profile_description = build_profile_description(config["profile"])
    section_rules = build_section_rules(config["profile"], config["sections"])
    avoid_section = ""
    if recent_headlines:
        headlines_list = "\n".join(f"- {h}" for h in recent_headlines)
        avoid_section = f"""
## Topics already covered — do NOT repeat these
The previous issue covered the following stories and facts. Choose entirely different topics:
{headlines_list}

"""
    return f"""You are generating Issue #{issue_num} of Sophie's World newsletter, dated {formatted_date}.

## About Sophie
{profile_description}

## Your Task
Fill in the HTML template below. Replace every <!-- PLACEHOLDER --> comment with the correct HTML content.
Search the web for current events and news happening THIS WEEK ({formatted_date}).

When you are done researching, output the completed HTML directly as your final message.
CRITICAL RULES — if you break any of these the output is unusable:
- Your final message MUST start with <!DOCTYPE html> and contain nothing else
- Do NOT ask for permission, approval, or confirmation before outputting the HTML
- Do NOT describe what you are about to write
- Do NOT use markdown, code fences, or any wrapper — just the raw HTML
{avoid_section}
## Section Rules
{section_rules}

## Template to Fill In
{template_html}
"""


def run_claude(prompt: str) -> str:
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--allowedTools", "WebSearch,WebFetch",
            "--output-format", "json",
            "--max-turns", "10",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"claude exited with code {result.returncode}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


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
    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt = build_prompt(template_html, today, issue_num, config, recent_headlines)

    label = "TEST" if args.test else f"Issue #{issue_num}"
    print(f"Generating {label} for {today}...")
    raw_output = run_claude(prompt)

    html = parse_claude_output(raw_output)
    if html is None:
        print("Error: claude returned empty or non-HTML output.", file=sys.stderr)
        print("Raw output:", file=sys.stderr)
        print(raw_output[:500], file=sys.stderr)
        sys.exit(1)

    output_path.write_text(html, encoding="utf-8")
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
