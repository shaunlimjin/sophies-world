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

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
NEWSLETTERS_DIR = REPO_ROOT / "newsletters"
TEMPLATE_PATH = SCRIPTS_DIR / "template.html"

SOPHIE_PROFILE = """
Sophie is a 4th-grader (age ~9-10) living in Fremont, California. Her family is Singaporean.
She loves: gymnastics (active participant), skiing, K-pop (especially Katseye and BLACKPINK),
non-fiction fun facts ("Weird But True" style), business fairs, and learning about saving money.
"""

SECTION_RULES = """
Newsletter sections to fill in (replace each <!-- PLACEHOLDER --> comment with real HTML content):

1. DATE_BADGE — Format: <div class="date-badge">📅 {month} {day}, {year} · Issue #{n}</div>

2. GREETING — Warm personalised opening. Reference Sophie's name and something from this week.
   Use <span>Sophie's World</span> for the newsletter name.

3. WEIRD_BUT_TRUE — 2-3 wild fun facts (animals, science, nature). Search for recent or
   timeless fascinating facts. Use .fact-list > .fact-item structure. Link to Nat Geo Kids,
   Britannica, or NewsForKids.net using .link-purple class.

4. WORLD_WATCH — 2 real, current events happening THIS WEEK. Search the web for what's in
   the news right now. Explain each for a 4th grader with an analogy (.analogy div).
   MUST include serious topics if relevant (conflicts, economy, tariffs). Use .link-green links
   to Time for Kids, NewsForKids.net, Britannica, or BBC Newsround.

5. SINGAPORE_SPOTLIGHT — A fun fact about Singapore (cultural, historical, economic, nature,
   food, or quirky). Does not need to be current news — timeless or surprising facts are great.
   Use .sg-spot items and .link-pink links.

6. USA_CORNER — California/Fremont angle, or US sports/science/culture. Current this week.
   Use .link-blue links.

7. KPOP_CORNER — Current Katseye and BLACKPINK news. Search for their latest releases,
   performances, or announcements. Use .kpop-item structure and .link-rose links to YouTube.

8. MONEY_MOVES — One saving/entrepreneurship concept + a real kid entrepreneur story.
   Include a .money-highlight tip box. Use .link-amber links.

9. SOPHIES_CHALLENGE — A maths or reasoning puzzle TIED TO a World Watch story this week.
   Include percentages, fractions, or basic reasoning. Reference the World Watch story by name.
   Add a .challenge-hint. Use .link-orange links.

10. FOOTER — Standard footer with issue number and date.
    Format: <div class="footer" style="background:#fff;border-radius:0 0 24px 24px;margin-top:3px;">
    <span class="hearts">💖 🌏 💖</span>
    <strong>Sophie's World</strong> · Issue #{n} · {Month} {DD}, {YYYY}<br>
    Made with love by Dad &amp; Claude 🤖❤️<br>
    <span style="font-size:12px;color:#bbb;">Fremont, California ↔ Singapore</span></div>

Reading level: 4th grade. Tone: warm, fun, curious. Use emojis naturally.
Links: prefer Time for Kids, NewsForKids.net, Britannica, BBC Newsround, Nat Geo Kids.
"""


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


def build_prompt(template_html: str, issue_date: date, issue_num: int, recent_headlines: List[str] = []) -> str:
    formatted_date = f"{issue_date.strftime('%B')} {issue_date.day}, {issue_date.strftime('%Y')}"
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
{SOPHIE_PROFILE}

## Your Task
Fill in the HTML template below. Replace every <!-- PLACEHOLDER --> comment with the correct HTML content.
Search the web for current events and news happening THIS WEEK ({formatted_date}).
Return ONLY the completed HTML — no explanation, no markdown fences, no commentary. Just the raw HTML.
{avoid_section}
## Section Rules
{SECTION_RULES}

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

    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt = build_prompt(template_html, today, issue_num, recent_headlines)

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
