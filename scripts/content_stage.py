#!/usr/bin/env python3
"""Content stage orchestration for Sophie's World."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from typing import Any, Dict, List


def build_content_prompt(issue_date: date, issue_num: int, config: Dict[str, Any], recent_headlines: List[str]) -> str:
    profile = config["profile"]
    sections = config["sections"]
    formatted_date = f"{issue_date.strftime('%B')} {issue_date.day}, {issue_date.strftime('%Y')}"
    child_id = profile.get("id", "sophie")
    editorial = profile.get("newsletter", {}).get("editorial", {})
    active_sections = profile.get("newsletter", {}).get("active_sections", [])
    section_summaries = []
    for section_id in active_sections:
        section = sections[section_id]
        section_summaries.append({
            "id": section_id,
            "title": section.get("title"),
            "goal": section.get("goal"),
            "block_type": section.get("block_type"),
            "content_rules": section.get("content_rules", []),
            "source_preferences": section.get("source_preferences", []),
            "link_style": section.get("link_style"),
        })

    avoid_text = ""
    if recent_headlines:
        avoid_text = "\nPreviously covered headlines to avoid repeating:\n" + "\n".join(f"- {h}" for h in recent_headlines)

    return f"""You are generating structured newsletter content for Sophie's World.

Return valid JSON only. Do not return HTML. Do not use markdown fences. Do not include commentary.

Issue metadata:
- issue_date: {issue_date.isoformat()}
- issue_number: {issue_num}
- child_id: {child_id}
- formatted_date: {formatted_date}

Child profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Editorial defaults:
{json.dumps(editorial, ensure_ascii=False, indent=2)}

Active section definitions:
{json.dumps(section_summaries, ensure_ascii=False, indent=2)}
{avoid_text}

Return JSON with this top-level structure:
{{
  "issue_date": "YYYY-MM-DD",
  "issue_number": number,
  "child_id": "...",
  "theme_id": "...",
  "editorial": {{ ... }},
  "page_title": "...",
  "date_badge_html": "...",
  "greeting_html": "...",
  "sections": [
    {{
      "id": "...",
      "title": "...",
      "render_title": "...",
      "block_type": "...",
      "link_style": "...",
      "items": [...],
      "links": [...]
    }}
  ],
  "footer": {{
    "issue_number": number,
    "issue_date_display": "Month DD, YYYY",
    "tagline": "...",
    "location_line": "..."
  }}
}}

Rules:
- Every active section must appear exactly once and in the same order.
- Use block-type-appropriate item shapes.
- Links must be structured objects with label and url.
- For `story_list`, each item should include `headline`, `body` (array of paragraphs), optional `analogy`, and `links`.
- For `fact_list`, each item should include `title` and `body`.
- For `spotlight` and `interest_feature`, each item should include `headline`, `body` (array), and optional `links`.
- For `challenge`, use one item with `prompt`, `hint`, and optional `links`.
- `greeting_html` should be complete HTML for the greeting div.
- `date_badge_html` should be complete HTML for the date badge div.
"""


def run_content_provider(prompt: str) -> str:
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


def parse_content_output(json_str: str) -> Dict[str, Any]:
    try:
        outer = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"content provider returned invalid envelope JSON: {exc}") from exc
    if outer.get("is_error") or not outer.get("result"):
        raise ValueError("content provider returned empty or error result")
    result = outer["result"].strip()
    start = result.find("{")
    if start == -1:
        raise ValueError("content provider result did not contain JSON object")
    try:
        return json.loads(result[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"content provider returned invalid content JSON: {exc}") from exc
