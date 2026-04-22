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
                "highlight": "optional — for money_moves sections: a concise tip or rule in a .money-highlight box",
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
                "return 1-2 spotlight items; prefer 2 when you have two distinct strong ideas",
                "if the second item would feel weak or repetitive, return 1 strong item instead",
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
- For `spotlight`, usually return 2 items when there are two clearly distinct good ideas; fall back to 1 only when the second would be weak or repetitive.
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


def run_content_provider(prompt: str, repo_root: Path, timeout_seconds: int = 300, provider=None, **kwargs) -> str:
    debug_dir = get_debug_dir(repo_root)
    (debug_dir / "last-content-prompt.txt").write_text(prompt, encoding="utf-8")

    if provider is not None:
        result = provider.generate(
            prompt,
            timeout=timeout_seconds,
            max_retries=2,
            debug_dir=debug_dir,
            **kwargs,
        )
        raw_output = result.get("result", "")
        (debug_dir / "last-content-stdout.txt").write_text(raw_output, encoding="utf-8")
        (debug_dir / "last-content-stderr.txt").write_text(result.get("error", "") or "", encoding="utf-8")
        if "error" in result and not raw_output:
            print(result["error"], file=sys.stderr)
            sys.exit(1)
        return raw_output

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


def extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise ValueError("content provider result did not contain JSON object")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]

    raise ValueError("content provider result did not contain a complete JSON object")


def build_packet_synthesis_prompt(
    issue_date: date,
    issue_num: int,
    config: Dict[str, Any],
    research_packet: Dict[str, Any],
) -> str:
    """Build the prompt for packet-driven synthesis (Mode B1/B2).

    The model receives pre-ranked candidates per section and must synthesize
    newsletter content from them without performing any web search.
    """
    profile = config["profile"]
    sections = config["sections"]
    formatted_date = f"{issue_date.strftime('%B')} {issue_date.day}, {issue_date.strftime('%Y')}"
    child_id = profile.get("id", "sophie")
    editorial = profile.get("newsletter", {}).get("editorial", {})
    profile_summary = build_profile_summary(profile)
    section_summaries = build_section_summaries(profile, sections)
    section_item_contracts = build_section_item_contracts()

    # Build a compact per-section candidate summary for the prompt.
    # For derived sections (sophies_challenge), include the source section's ranked
    # candidates directly so synthesis has explicit material to derive from.
    sections_by_id = {s["section_id"]: s for s in research_packet.get("sections", [])}

    section_packets = []
    for section in research_packet.get("sections", []):
        section_id = section["section_id"]
        derived_from = section.get("derived_from")

        if derived_from:
            # Use the source section's ranked candidates as the challenge's material
            source_section = sections_by_id.get(derived_from, {})
            source_candidates = source_section.get("ranked_candidates") or source_section.get("filtered_candidates") or []
            compact_candidates = [
                {
                    "title": c.get("title", ""),
                    "url": c.get("url", ""),
                    "source": c.get("source", ""),
                    "snippet": c.get("snippet", ""),
                }
                for c in source_candidates[:4]
            ]
            section_packets.append({
                "section_id": section_id,
                "derived_from": derived_from,
                "note": f"Create this section from the {derived_from} stories above — do not add unrelated material",
                "source_candidates": compact_candidates,
            })
            continue

        candidates = section.get("ranked_candidates") or section.get("filtered_candidates") or []
        compact_candidates = [
            {
                "title": c.get("title", ""),
                "url": c.get("url", ""),
                "source": c.get("source", ""),
                "snippet": c.get("snippet", ""),
                "published_at": c.get("published_at"),
            }
            for c in candidates[:6]  # cap per section to keep prompt bounded
        ]
        if compact_candidates:
            section_packets.append({
                "section_id": section_id,
                "candidates": compact_candidates,
            })

    return f"""You are generating structured newsletter content for Sophie's World.

You have been given pre-researched, ranked candidate articles for each section.
Use these candidates as your primary source material. Do NOT search the web.
Select from the candidates, synthesize their content into engaging newsletter sections,
and produce valid JSON only. Do not return HTML. Do not use markdown fences. Do not include commentary.

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

Pre-researched candidates per section (select and synthesize from these):
{json.dumps(section_packets, ensure_ascii=False, indent=2)}

For sections marked "derived_from", the source_candidates field contains the stories
to derive from. Do not invent other material for those sections.

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
- Every active section must appear exactly once and in the same order as section summaries.
- Keep `title` aligned to config, but make `render_title` richer and more editorial.
- Use block-type-appropriate item shapes from the contracts above.
- Links must be structured objects with label and url — use URLs from the provided candidates.
- Prefer 1-2 strong items over many weak ones.
- For `spotlight`, usually return 2 items when there are two clearly distinct good ideas; fall back to 1 only when the second would be weak or repetitive.
- Write for a smart 4th grader: warm, energetic, easy to follow, but not babyish.
- For `challenge`, split the content cleanly across `prompt_intro`, `prompt`, optional `bonus`, and `hint`.
- `greeting_text` must NOT start with another greeting like "Hi Sophie" or include day-of-week phrasing like "Happy Saturday".
- `bonus` must contain only the bonus question text, with no "Bonus" or emoji prefix.
- Do not use markdown emphasis markers like `*word*` or `**word**` anywhere in output text.
"""


def run_packet_synthesis_provider(prompt: str, repo_root: Path, timeout_seconds: int = 300, max_retries: int = 2, provider=None, **kwargs) -> str:
    """Call Claude without web tools (packet-driven synthesis mode)."""
    debug_dir = get_debug_dir(repo_root)
    (debug_dir / "last-packet-prompt.txt").write_text(prompt, encoding="utf-8")

    if provider is not None:
        result = provider.generate(
            prompt,
            timeout=timeout_seconds,
            max_retries=max_retries,
            debug_dir=debug_dir,
            **kwargs,
        )
        raw_output = result.get("result", "")
        parse_content_output(raw_output, repo_root)
        return raw_output

    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                [
                    "claude", "-p", prompt,
                    "--output-format", "json",
                    "--max-turns", "3",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"packet synthesis provider timed out after {timeout_seconds}s") from exc

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        (debug_dir / f"last-packet-stdout-attempt{attempt}.txt").write_text(stdout, encoding="utf-8")
        (debug_dir / f"last-packet-stderr-attempt{attempt}.txt").write_text(stderr, encoding="utf-8")

        if result.returncode != 0:
            if attempt < max_retries:
                print(f"packet synthesis attempt {attempt + 1} failed (exit {result.returncode}), retrying...", file=sys.stderr)
                continue
            print(f"claude exited with code {result.returncode}", file=sys.stderr)
            print(stderr, file=sys.stderr)
            sys.exit(1)

        # Validate JSON parse before returning — retry on invalid output
        try:
            parse_content_output(stdout)
            return stdout
        except ValueError as exc:
            if attempt < max_retries:
                print(f"packet synthesis attempt {attempt + 1} returned invalid JSON ({exc}), retrying...", file=sys.stderr)
                continue
            raise

    raise RuntimeError("packet synthesis provider failed all attempts")  # unreachable


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
    result = result.removeprefix("```json").removeprefix("```").strip()
    result = result.removesuffix("```").strip()
    try:
        return json.loads(extract_first_json_object(result))
    except json.JSONDecodeError as exc:
        raise ValueError(f"content provider returned invalid content JSON: {exc}") from exc
