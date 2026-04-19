#!/usr/bin/env python3
"""Content stage orchestration for Sophie's World."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List


def build_profile_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    newsletter = profile.get("newsletter", {})
    editorial = newsletter.get("editorial", {})
    return {
        "id": profile.get("id", "sophie"),
        "name": profile.get("name", "Sophie"),
        "age_band": profile.get("age_band"),
        "location": profile.get("location"),
        "cultural_context": profile.get("cultural_context", []),
        "active_interests": profile.get("interests", {}).get("active", []),
        "reading_level": editorial.get("reading_level"),
        "tone": editorial.get("tone", []),
        "use_emojis": editorial.get("use_emojis"),
    }


def build_section_summaries(profile: Dict[str, Any], sections: Dict[str, Any]) -> List[Dict[str, Any]]:
    active_section_ids = profile.get("newsletter", {}).get("active_sections", [])
    summaries = []
    for section_id in active_section_ids:
        section = sections[section_id]
        rules = section.get("content_rules", [])[:3]
        sources = section.get("source_preferences", [])[:3]
        summaries.append({
            "id": section_id,
            "title": section.get("title"),
            "goal": section.get("goal"),
            "block_type": section.get("block_type"),
            "rules": rules,
            "preferred_sources": sources,
            "link_style": section.get("link_style"),
        })
    return summaries


def build_section_item_contracts() -> Dict[str, Dict[str, Any]]:
    return {
        "fact_list": {
            "section_fields": ["title", "render_title", "section_intro(optional)"],
            "item_shape": {"title": "...", "body": "..."},
            "quality_notes": [
                "render_title should be more vivid than the section label, not a copy of it",
                "section_intro is optional and should only be used when it adds warmth or context",
            ],
        },
        "story_list": {
            "section_fields": ["title", "render_title", "section_intro(optional)"],
            "item_shape": {
                "headline": "...",
                "body": ["paragraph 1", "paragraph 2"],
                "analogy": "optional",
                "links": [{"label": "...", "url": "..."}],
            },
            "quality_notes": [
                "render_title should feel like a real magazine sub-head, not just the label repeated",
                "use section_intro sparingly to tee up the stories",
            ],
        },
        "spotlight": {
            "section_fields": ["title", "render_title", "section_intro(optional)"],
            "item_shape": {
                "headline": "...",
                "body": ["paragraph 1", "paragraph 2"],
                "links": [{"label": "...", "url": "..."}],
            },
            "quality_notes": [
                "one strong spotlight item is better than several thin ones",
                "headline should be specific and exciting",
            ],
        },
        "interest_feature": {
            "section_fields": ["title", "render_title", "section_intro(optional)"],
            "item_shape": {
                "headline": "...",
                "body": ["paragraph 1", "paragraph 2"],
                "links": [{"label": "...", "url": "..."}],
            },
            "quality_notes": [
                "lean into the child's active interest and make it feel personal",
                "avoid generic headlines",
            ],
        },
        "challenge": {
            "section_fields": ["title", "render_title", "section_intro(optional)"],
            "item_shape": {
                "prompt_intro": "short setup paragraph",
                "prompt": "main challenge question",
                "bonus": "optional bonus question or extension",
                "hint": "helpful hint",
                "links": [{"label": "...", "url": "..."}],
            },
            "quality_notes": [
                "format for readability in a card, not as one giant blob",
                "main prompt should be concise after the setup",
            ],
        },
    }


def build_content_prompt(issue_date: date, issue_num: int, config: Dict[str, Any], recent_headlines: List[str]) -> str:
    profile = config["profile"]
    sections = config["sections"]
    formatted_date = f"{issue_date.strftime('%B')} {issue_date.day}, {issue_date.strftime('%Y')}"
    child_id = profile.get("id", "sophie")
    editorial = profile.get("newsletter", {}).get("editorial", {})
    profile_summary = build_profile_summary(profile)
    section_summaries = build_section_summaries(profile, sections)
    section_item_contracts = build_section_item_contracts()

    avoid_text = ""
    if recent_headlines:
        avoid_text = "\nPreviously covered headlines to avoid repeating:\n" + "\n".join(f"- {h}" for h in recent_headlines[:6])

    return f"""You are generating structured newsletter content for Sophie's World.

Return valid JSON only. Do not return HTML. Do not use markdown fences. Do not include commentary.

Issue metadata:
- issue_date: {issue_date.isoformat()}
- issue_number: {issue_num}
- child_id: {child_id}
- formatted_date: {formatted_date}

Child summary:
{json.dumps(profile_summary, ensure_ascii=False, indent=2)}

Editorial defaults:
{json.dumps(editorial, ensure_ascii=False, indent=2)}

Active section summaries:
{json.dumps(section_summaries, ensure_ascii=False, indent=2)}

Block-type item contracts:
{json.dumps(section_item_contracts, ensure_ascii=False, indent=2)}
{avoid_text}

Return JSON with this top-level structure:
{{
  "issue_date": "YYYY-MM-DD",
  "issue_number": number,
  "child_id": "...",
  "child_name": "...",
  "theme_id": "...",
  "editorial": {{ ... }},
  "greeting_text": "one warm sentence fragment for after 'Hey Sophie! 👋', without repeating the child's name or adding weekday labels, and it may include <span>Sophie's World</span>",
  "sections": [
    {{
      "id": "...",
      "title": "canonical section label from config",
      "render_title": "more vivid magazine-style heading, not just the same label copied",
      "section_intro": "optional short intro line for the section",
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
- Keep `title` aligned to config, but make `render_title` richer and more editorial.
- Use block-type-appropriate item shapes from the contracts above.
- Links must be structured objects with label and url.
- Prefer 1-2 strong items over many weak ones.
- Write for a smart 4th grader: warm, energetic, easy to follow, but not babyish.
- For `challenge`, split the content cleanly across `prompt_intro`, `prompt`, optional `bonus`, and `hint` so the renderer can avoid one squished text blob.
- `greeting_text` must NOT start with another greeting like "Hi Sophie" or include day-of-week phrasing like "Happy Saturday".
- `bonus` must contain only the bonus question text, with no "Bonus" or emoji prefix.
- Do not use markdown emphasis markers like `*word*` or `**word**` anywhere in output text.
"""


def get_debug_dir(repo_root: Path) -> Path:
    path = repo_root / "artifacts" / "debug"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_content_provider(prompt: str, repo_root: Path, timeout_seconds: int = 300) -> str:
    debug_dir = get_debug_dir(repo_root)
    (debug_dir / "last-content-prompt.txt").write_text(prompt, encoding="utf-8")
    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--allowedTools", "WebSearch,WebFetch",
                "--output-format", "json",
                "--max-turns", "10",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"content provider timed out after {timeout_seconds}s") from exc
    (debug_dir / "last-content-stdout.txt").write_text(result.stdout or "", encoding="utf-8")
    (debug_dir / "last-content-stderr.txt").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode != 0:
        print(f"claude exited with code {result.returncode}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


def parse_content_output(json_str: str, repo_root: Path | None = None) -> Dict[str, Any]:
    if repo_root is not None:
        get_debug_dir(repo_root).joinpath("last-parse-input.txt").write_text(json_str or "", encoding="utf-8")
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
