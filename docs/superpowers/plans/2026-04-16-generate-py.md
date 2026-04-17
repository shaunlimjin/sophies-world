# generate.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/generate.py` — a CLI script that calls the `claude` subprocess with web search to generate a new Sophie's World HTML newsletter issue and writes it to `newsletters/`.

**Architecture:** The script reads a clean HTML skeleton (`scripts/template.html`), builds a detailed prompt with Sophie's profile + section rules + current date + template HTML, shells out to `claude -p ... --output-format json`, extracts the `result` field, and writes the completed HTML to `newsletters/sophies-world-YYYY-MM-DD.html`.

**Tech Stack:** Python 3, `subprocess`, `json`, `pathlib`, `datetime`; `claude` CLI (already installed and authenticated)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/template.html` | Create | HTML skeleton — full CSS from Issue #1, content replaced with section placeholders |
| `scripts/generate.py` | Create | Main generation script |
| `tests/test_generate.py` | Create | Unit tests for core logic (issue number, path, JSON parsing, idempotency) |

---

## Task 1: Create `scripts/template.html`

**Files:**
- Create: `scripts/template.html`

The template keeps the full CSS and structural HTML from Issue #1, but replaces each section's text content with a descriptive placeholder comment. Claude receives this template in the prompt and fills in the content between the outer structural divs.

- [ ] **Step 1: Create `scripts/template.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title><!-- PAGE_TITLE --></title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Nunito', Arial, sans-serif;
    background: #f0f4ff;
    color: #2d2d2d;
    padding: 20px;
  }

  .wrapper {
    max-width: 640px;
    margin: 0 auto;
  }

  /* ── HEADER ── */
  .header {
    background: linear-gradient(135deg, #ff6eb4 0%, #ff9a3c 50%, #ffda47 100%);
    border-radius: 24px 24px 0 0;
    padding: 36px 32px 28px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .header::before {
    content: "✨🌍✨";
    font-size: 28px;
    display: block;
    margin-bottom: 8px;
    letter-spacing: 6px;
  }
  .header h1 {
    font-size: 40px;
    font-weight: 900;
    color: #fff;
    text-shadow: 2px 3px 0 rgba(0,0,0,0.15);
    letter-spacing: -1px;
    line-height: 1.1;
  }
  .header .subtitle {
    font-size: 15px;
    color: rgba(255,255,255,0.92);
    margin-top: 8px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }
  .header .date-badge {
    display: inline-block;
    background: rgba(255,255,255,0.3);
    border: 2px solid rgba(255,255,255,0.6);
    border-radius: 50px;
    padding: 5px 18px;
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    margin-top: 12px;
    letter-spacing: 0.5px;
  }

  /* ── GREETING BAND ── */
  .greeting {
    background: #fff;
    border-left: 5px solid #ff6eb4;
    padding: 16px 24px;
    font-size: 16px;
    font-weight: 600;
    color: #444;
    line-height: 1.6;
  }
  .greeting span { color: #ff6eb4; }

  /* ── SECTION CARDS ── */
  .card {
    background: #fff;
    padding: 24px 28px;
    margin-top: 3px;
  }

  .section-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    border-radius: 50px;
    padding: 4px 14px;
    margin-bottom: 12px;
  }

  .card-wbt   { border-top: 4px solid #a78bfa; }
  .label-wbt  { background: #ede9fe; color: #6d28d9; }

  .card-world { border-top: 4px solid #34d399; }
  .label-world{ background: #d1fae5; color: #065f46; }

  .card-sg    { border-top: 4px solid #f472b6; }
  .label-sg   { background: #fce7f3; color: #9d174d; }

  .card-usa   { border-top: 4px solid #60a5fa; }
  .label-usa  { background: #dbeafe; color: #1e40af; }

  .card-kpop  { border-top: 4px solid #f9a8d4; }
  .label-kpop { background: #fdf2f8; color: #be185d; }

  .card-money { border-top: 4px solid #fbbf24; }
  .label-money{ background: #fef3c7; color: #92400e; }

  .card-challenge { border-top: 4px solid #fb923c; background: #fff7ed; }
  .label-challenge{ background: #ffedd5; color: #9a3412; }

  .card h2 {
    font-size: 20px;
    font-weight: 800;
    margin-bottom: 10px;
    line-height: 1.2;
    color: #1a1a2e;
  }
  .card p {
    font-size: 15px;
    line-height: 1.75;
    color: #3d3d3d;
    margin-bottom: 10px;
  }
  .card p:last-child { margin-bottom: 0; }

  /* ── LEARN MORE LINKS ── */
  .learn-more {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 14px;
  }
  .learn-more a {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    font-weight: 700;
    text-decoration: none;
    padding: 5px 13px;
    border-radius: 50px;
    border: 2px solid;
    transition: opacity 0.15s;
    letter-spacing: 0.3px;
  }
  .learn-more a:hover { opacity: 0.8; }
  .link-green  { color: #065f46; border-color: #34d399; background: #d1fae5; }
  .link-purple { color: #5b21b6; border-color: #a78bfa; background: #ede9fe; }
  .link-pink   { color: #9d174d; border-color: #f472b6; background: #fce7f3; }
  .link-blue   { color: #1e40af; border-color: #60a5fa; background: #dbeafe; }
  .link-rose   { color: #be185d; border-color: #f9a8d4; background: #fdf2f8; }
  .link-amber  { color: #92400e; border-color: #fbbf24; background: #fef3c7; }
  .link-orange { color: #9a3412; border-color: #fb923c; background: #ffedd5; }

  /* ── FACT PILLS ── */
  .fact-list { display: flex; flex-direction: column; gap: 12px; margin-top: 4px; }
  .fact-item {
    background: #f5f3ff;
    border-left: 4px solid #a78bfa;
    border-radius: 0 12px 12px 0;
    padding: 12px 16px;
    font-size: 15px;
    line-height: 1.65;
    color: #3d3d3d;
  }
  .fact-item strong { color: #6d28d9; }

  /* ── WORLD WATCH STORIES ── */
  .world-stories { display: flex; flex-direction: column; gap: 16px; margin-top: 4px; }
  .world-story {
    background: #f0fdf4;
    border-left: 4px solid #34d399;
    border-radius: 0 12px 12px 0;
    padding: 14px 18px;
  }
  .world-story h3 {
    font-size: 15px;
    font-weight: 800;
    color: #065f46;
    margin-bottom: 6px;
  }
  .world-story p {
    font-size: 14px;
    line-height: 1.7;
    color: #3d3d3d;
    margin-bottom: 6px;
  }
  .world-story p:last-of-type { margin-bottom: 0; }
  .world-story .analogy {
    background: #dcfce7;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    font-style: italic;
    color: #166534;
    margin-top: 8px;
  }
  .world-story .story-links { margin-top: 10px; }

  /* ── SG SPOTS ── */
  .sg-spots { display: flex; flex-direction: column; gap: 12px; margin-top: 4px; }
  .sg-spot {
    background: #fdf2f8;
    border-left: 4px solid #f472b6;
    border-radius: 0 12px 12px 0;
    padding: 12px 16px;
  }
  .sg-spot h3 { font-size: 15px; font-weight: 800; color: #be185d; margin-bottom: 4px; }
  .sg-spot p  { font-size: 14px; line-height: 1.65; color: #4a4a4a; margin: 0; }

  /* ── KPOP BANDS ── */
  .kpop-grid { display: flex; flex-direction: column; gap: 12px; margin-top: 4px; }
  .kpop-item {
    background: #fdf2f8;
    border-left: 4px solid #f9a8d4;
    border-radius: 0 12px 12px 0;
    padding: 12px 16px;
  }
  .kpop-item h3 { font-size: 15px; font-weight: 800; color: #be185d; margin-bottom: 4px; }
  .kpop-item p  { font-size: 14px; line-height: 1.65; color: #4a4a4a; margin: 0; }

  /* ── MONEY HIGHLIGHT ── */
  .money-highlight {
    background: #fffbeb;
    border: 2px dashed #fbbf24;
    border-radius: 12px;
    padding: 14px 18px;
    margin-top: 12px;
    font-size: 14px;
    line-height: 1.65;
    color: #3d3d3d;
  }
  .money-highlight strong { color: #b45309; }

  /* ── CHALLENGE BOX ── */
  .challenge-q {
    background: #fff;
    border: 3px solid #fb923c;
    border-radius: 16px;
    padding: 18px 20px;
    margin-top: 10px;
    font-size: 16px;
    font-weight: 700;
    color: #1a1a2e;
    text-align: center;
    line-height: 1.6;
  }
  .challenge-hint {
    text-align: center;
    font-size: 13px;
    color: #9a6a3e;
    margin-top: 10px;
    font-style: italic;
  }

  /* ── FOOTER ── */
  .footer {
    text-align: center;
    padding: 28px 20px;
    font-size: 13px;
    color: #888;
    line-height: 1.8;
  }
  .footer .hearts {
    font-size: 22px;
    display: block;
    margin-bottom: 6px;
    letter-spacing: 4px;
  }
  .footer strong { color: #ff6eb4; }

  /* ── DIVIDER ── */
  .divider {
    height: 3px;
    background: linear-gradient(90deg, #ff6eb4, #ff9a3c, #ffda47, #34d399, #60a5fa, #a78bfa);
    border-radius: 3px;
    margin: 3px 0;
  }
</style>
</head>
<body>
<div class="wrapper">

  <!-- HEADER -->
  <div class="header">
    <h1>Sophie's World</h1>
    <div class="subtitle">Your weekly dose of wow, fun &amp; big ideas</div>
    <!-- DATE_BADGE: e.g. <div class="date-badge">📅 April 23, 2026 · Issue #2</div> -->
  </div>

  <!-- GREETING -->
  <!-- GREETING: <div class="greeting">Hey Sophie! 👋 ... <span>Sophie's World</span> ... </div> -->

  <div class="divider"></div>

  <!-- WEIRD BUT TRUE -->
  <div class="card card-wbt">
    <div class="section-label label-wbt">🤯 Weird But True</div>
    <!-- WEIRD_BUT_TRUE: h2 title, then .fact-list with 2-3 .fact-item divs (each with <strong>emoji Title</strong> body), then .learn-more links using .link-purple -->
  </div>

  <div class="divider"></div>

  <!-- WORLD WATCH -->
  <div class="card card-world">
    <div class="section-label label-world">🌍 World Watch</div>
    <!-- WORLD_WATCH: h2 title, then .world-stories with 2 .world-story divs. Each story: h3, p tags, .analogy div, .story-links.learn-more with .link-green links -->
  </div>

  <div class="divider"></div>

  <!-- SINGAPORE SPOTLIGHT -->
  <div class="card card-sg">
    <div class="section-label label-sg">🇸🇬 Singapore Spotlight</div>
    <!-- SINGAPORE_SPOTLIGHT: h2 title, .sg-spots with 1-2 .sg-spot divs (h3 + p), then .learn-more with .link-pink links -->
  </div>

  <div class="divider"></div>

  <!-- USA CORNER -->
  <div class="card card-usa">
    <div class="section-label label-usa">🇺🇸 USA Corner</div>
    <!-- USA_CORNER: h2 title, p tags for content, .learn-more with .link-blue links -->
  </div>

  <div class="divider"></div>

  <!-- K-POP CORNER -->
  <div class="card card-kpop">
    <div class="section-label label-kpop">🎤 K-pop Corner</div>
    <!-- KPOP_CORNER: h2 title, .kpop-grid with 2 .kpop-item divs (h3 + p), .learn-more with .link-rose links -->
  </div>

  <div class="divider"></div>

  <!-- MONEY MOVES -->
  <div class="card card-money">
    <div class="section-label label-money">💰 Money Moves</div>
    <!-- MONEY_MOVES: h2 title, p tags, .money-highlight div, p for kid entrepreneur story, .learn-more with .link-amber links -->
  </div>

  <div class="divider"></div>

  <!-- SOPHIE'S CHALLENGE -->
  <div class="card card-challenge">
    <div class="section-label label-challenge">🧠 Sophie's Challenge</div>
    <!-- SOPHIES_CHALLENGE: h2 "Can You Figure This Out?", .challenge-q div with the puzzle (tied to World Watch), .challenge-hint p, .learn-more with .link-orange links -->
  </div>

  <!-- FOOTER -->
  <!-- FOOTER: <div class="footer" style="background:#fff;border-radius:0 0 24px 24px;margin-top:3px;"><span class="hearts">💖 🌏 💖</span><strong>Sophie's World</strong> · Issue #N · Month DD, YYYY<br>Made with love by Dad &amp; Claude 🤖❤️<br><span style="font-size:12px;color:#bbb;">Fremont, California ↔ Singapore</span></div> -->

</div>
</body>
</html>
```

- [ ] **Step 2: Verify template renders in browser**

Open `scripts/template.html` in a browser. Should show the coloured header, empty card outlines with section labels, and no broken layout. The placeholder comments are invisible in the browser.

- [ ] **Step 3: Commit**

```bash
git add scripts/template.html
git commit -m "feat: add HTML template skeleton for newsletter generation"
```

---

## Task 2: Write failing tests for core logic

**Files:**
- Create: `tests/test_generate.py`

- [ ] **Step 1: Create `tests/test_generate.py` with failing tests**

```python
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

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
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
cd /Users/hobbes/dev/sophies-world
python -m pytest tests/test_generate.py -v 2>&1 | head -40
```

Expected: All 8 tests fail with `ModuleNotFoundError: No module named 'generate'`

---

## Task 3: Implement `scripts/generate.py`

**Files:**
- Create: `scripts/generate.py`

- [ ] **Step 1: Create `scripts/generate.py`**

```python
#!/usr/bin/env python3
"""Generate a Sophie's World newsletter issue using the claude CLI."""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

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

5. SINGAPORE_SPOTLIGHT — Something current happening in Singapore this week (culture, food,
   animals, tech, events). Search for it. Use .sg-spot items and .link-pink links.

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


def get_output_path(newsletters_dir: Path, issue_date: date) -> Path:
    filename = f"sophies-world-{issue_date.strftime('%Y-%m-%d')}.html"
    return newsletters_dir / filename


def check_output_exists(output_path: Path) -> bool:
    if output_path.exists():
        print(f"Output already exists, skipping: {output_path}")
        return True
    return False


def parse_claude_output(json_str: str) -> str | None:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None
    if data.get("is_error") or not data.get("result"):
        return None
    result = data["result"].strip()
    if not result.startswith("<"):
        return None
    return result


def build_prompt(template_html: str, issue_date: date, issue_num: int) -> str:
    formatted_date = issue_date.strftime("%B %-d, %Y")
    return f"""You are generating Issue #{issue_num} of Sophie's World newsletter, dated {formatted_date}.

## About Sophie
{SOPHIE_PROFILE}

## Your Task
Fill in the HTML template below. Replace every <!-- PLACEHOLDER --> comment with the correct HTML content.
Search the web for current events and news happening THIS WEEK ({formatted_date}).
Return ONLY the completed HTML — no explanation, no markdown fences, no commentary. Just the raw HTML.

## Section Rules
{SECTION_RULES}

## Template to Fill In
{template_html}
"""


def run_claude(prompt: str) -> str:
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--tools", "WebSearch,WebFetch",
            "--allowedTools", "WebSearch", "WebFetch",
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
    today = date.today()
    issue_num = get_next_issue_number(NEWSLETTERS_DIR)
    output_path = get_output_path(NEWSLETTERS_DIR, today)

    if check_output_exists(output_path):
        return

    template_html = TEMPLATE_PATH.read_text()
    prompt = build_prompt(template_html, today, issue_num)

    print(f"Generating Issue #{issue_num} for {today}...")
    raw_output = run_claude(prompt)

    html = parse_claude_output(raw_output)
    if html is None:
        print("Error: claude returned empty or non-HTML output.", file=sys.stderr)
        print("Raw output:", file=sys.stderr)
        print(raw_output[:500], file=sys.stderr)
        sys.exit(1)

    output_path.write_text(html)
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the tests**

```bash
cd /Users/hobbes/dev/sophies-world
python -m pytest tests/test_generate.py -v
```

Expected output:
```
tests/test_generate.py::test_get_next_issue_number_no_files PASSED
tests/test_generate.py::test_get_next_issue_number_with_existing PASSED
tests/test_generate.py::test_get_output_path PASSED
tests/test_generate.py::test_parse_claude_output_success PASSED
tests/test_generate.py::test_parse_claude_output_error PASSED
tests/test_generate.py::test_parse_claude_output_non_html PASSED
tests/test_generate.py::test_idempotent_skips_existing PASSED
tests/test_generate.py::test_idempotent_proceeds_when_missing PASSED

8 passed
```

If any test fails, fix `generate.py` until all 8 pass before continuing.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate.py tests/test_generate.py
git commit -m "feat: implement generate.py with tests"
```

---

## Task 4: Smoke test end-to-end

**Files:**
- Read: `newsletters/` (verify output file is created)

- [ ] **Step 1: Run a dry check — verify the script can be imported and prints help**

```bash
cd /Users/hobbes/dev/sophies-world
python scripts/generate.py --help 2>&1 || python scripts/generate.py 2>&1 | head -5
```

Expected: Either a help message or `Generating Issue #2 for 2026-...` (it will start calling claude).

- [ ] **Step 2: Run the full generation (takes ~1-2 minutes)**

```bash
cd /Users/hobbes/dev/sophies-world
python scripts/generate.py
```

Expected output:
```
Generating Issue #2 for 2026-04-16...
Written: newsletters/sophies-world-2026-04-16.html
```

If today is 2026-04-16 and Issue #1 already exists, the script will skip (idempotency). In that case, temporarily rename Issue #1, run the script, then rename it back.

- [ ] **Step 3: Verify output file**

```bash
ls -la newsletters/
wc -c newsletters/sophies-world-2026-04-16.html  # should be >10KB
```

Open the generated HTML file in a browser and check:
- All 7 sections are present and filled in
- No `<!-- PLACEHOLDER -->` comments remain visible in the source
- Links exist in each section
- Footer shows correct issue number and date

- [ ] **Step 4: Run idempotency check**

```bash
python scripts/generate.py
```

Expected: `Output already exists, skipping: newsletters/sophies-world-2026-04-16.html`

- [ ] **Step 5: Commit**

```bash
git add newsletters/
git commit -m "feat: add Issue #2 generated by generate.py"
```
