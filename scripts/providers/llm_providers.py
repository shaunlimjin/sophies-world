"""Hosted LLM provider: model-based reranker using Claude (Mode B2)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def model_rank_candidates(
    filtered_pool: Dict[str, Any],
    config: dict,
    repo_root: Path,
    timeout_seconds: int = 120,
    max_retries: int = 2,
    provider=None,
) -> Dict[str, Any]:
    """Rerank filtered candidates per section using a hosted Claude model.

    Receives a pool with filtered_candidates per section; returns the same
    structure augmented with ranked_candidates chosen by the model.

    Args:
        filtered_pool: Pool with filtered_candidates per section
        config: Newsletter config dict
        repo_root: Repository root path for debug artifacts
        timeout_seconds: Timeout for provider calls
        max_retries: Max retry attempts
        provider: ModelProvider instance; when None, uses subprocess (backward compat)
    """
    debug_dir = _get_debug_dir(repo_root)
    profile = config["profile"]
    research_cfg = config.get("research", {})
    recent_headlines = filtered_pool.get("recent_headlines", [])

    ranked_sections = []
    for section in filtered_pool["sections"]:
        section_id = section["section_id"]
        candidates = section.get("filtered_candidates", [])
        ranking_profile = section.get("ranking_profile", f"{section_id}_default")
        sec_research = research_cfg.get("sections", {}).get(section_id, {})
        max_ranked = research_cfg.get("ranking", {}).get("sections", {}).get(section_id, {}).get(
            "max_ranked",
            research_cfg.get("ranking", {}).get("defaults", {}).get("max_ranked", 5),
        )

        if not candidates:
            ranked_sections.append({**section, "ranked_candidates": []})
            continue

        prompt = _build_ranker_prompt(section_id, candidates, profile, max_ranked, recent_headlines)
        prompt_file = debug_dir / f"last-ranker-prompt-{section_id}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")

        ranked = _run_model_ranker(
            prompt, section_id, candidates, max_ranked, debug_dir, timeout_seconds, max_retries, provider
        )

        if not ranked:
            # Model ranker failed — fall back to filtered ordering (preserves deterministic prefilter signal)
            print(f"model ranker fallback for {section_id}: using filtered ordering", file=sys.stderr)
            ranked = [dict(c) for c in candidates[:max_ranked]]
            for r in ranked:
                r.setdefault("reasons", ["fallback: model ranker unavailable"])
                r.setdefault("score", None)

        ranked_sections.append({**section, "ranked_candidates": ranked})

    return {**filtered_pool, "sections": ranked_sections}


def _build_ranker_prompt(
    section_id: str,
    candidates: List[Dict[str, Any]],
    profile: Dict[str, Any],
    max_ranked: int,
    recent_headlines: List[str],
) -> str:
    child_name = profile.get("name", "Sophie")
    age_band = profile.get("age_band", "4th-grade")
    interests = profile.get("interests", {}).get("active", [])

    compact = [
        {
            "index": i,
            "title": c.get("title", ""),
            "source": c.get("source", ""),
            "domain": c.get("domain", ""),
            "snippet": c.get("snippet", ""),
            "published_at": c.get("published_at"),
        }
        for i, c in enumerate(candidates)
    ]
    recent_headlines = recent_headlines[:8]
    recent_block = json.dumps(recent_headlines, ensure_ascii=False, indent=2)

    return f"""You are a ranking assistant for a children's newsletter called Sophie's World.

The newsletter is written for {child_name}, a {age_band} student living in Fremont, California
with a Singaporean family background. Active interests: {', '.join(interests)}.

Section: {section_id}

Your job is not just to pick individually good articles. Your job is to pick articles that will help produce a section that is:
- strong for this specific section
- easy and exciting for a smart 4th grader to understand
- meaningfully distinct from very recent issues
- not just the most obvious or generic headline in the pool

Important ranking priorities, in order:
1. strong fit for the section's editorial goal
2. kid-appropriate explanatory value
3. novelty relative to recent issues and recurring stale themes
4. freshness when the section is current-events oriented
5. source quality and specificity

Avoid picking candidates that are too similar to recent issue headlines, even if they look strong in isolation.
Also avoid obvious-but-generic picks when a more distinctive, teachable, section-appropriate candidate is available.
Prefer editorial distinctness over headline salience when the tradeoff is close.

Recent issue headlines to avoid repeating too closely:
{recent_block}

Return ONLY a JSON array of the top {max_ranked} candidates, each with:
- "index": the original candidate index (integer)
- "title": the candidate title (string)
- "reasons": short list of strings explaining why this candidate was selected, explicitly mentioning novelty/distinctness when relevant

Do not include commentary. Do not return prose. Return only valid JSON.

Candidates:
{json.dumps(compact, ensure_ascii=False, indent=2)}
"""


def _run_model_ranker(
    prompt: str,
    section_id: str,
    candidates: List[Dict[str, Any]],
    max_ranked: int,
    debug_dir: Path,
    timeout_seconds: int,
    max_retries: int,
    provider=None,
) -> List[Dict[str, Any]]:
    for attempt in range(max_retries + 1):
        if provider is not None:
            result = provider.generate(
                prompt,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
            stdout = result.get("result", "")
            (debug_dir / f"last-ranker-stdout-{section_id}-attempt{attempt}.txt").write_text(stdout, encoding="utf-8")
            if result.get("error"):
                # Provider already exhausted its own retries — don't retry again here.
                # Outer loop only retries on parse errors.
                print(f"model ranker failed for section {section_id} (provider error: {result['error']})", file=sys.stderr)
                return []
        else:
            try:
                result = subprocess.run(
                    [
                        "claude", "-p", prompt,
                        "--output-format", "json",
                        "--max-turns", "2",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                if attempt < max_retries:
                    continue
                print(f"model ranker timed out for section {section_id}", file=sys.stderr)
                return []

            stdout = result.stdout or ""
            (debug_dir / f"last-ranker-stdout-{section_id}-attempt{attempt}.txt").write_text(stdout, encoding="utf-8")

            if result.returncode != 0:
                if attempt < max_retries:
                    continue
                print(f"model ranker failed for section {section_id} (exit {result.returncode})", file=sys.stderr)
                return []

        try:
            ranked_selections = _parse_ranker_output(stdout, candidates)
            if ranked_selections:
                return ranked_selections[:max_ranked]
        except (ValueError, KeyError) as exc:
            if attempt < max_retries:
                print(f"model ranker output parse error for {section_id} (attempt {attempt + 1}): {exc}", file=sys.stderr)
                continue
            print(f"model ranker returned unparseable output for {section_id}: {exc}", file=sys.stderr)
            return []

    return []


def _parse_ranker_output(raw: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract and validate structured ranking selections from model output."""
    # Strip any leading non-JSON content (blank lines, warning messages, etc.)
    json_start = min(
        raw.find("{"),
        raw.find("["),
    )
    if json_start == -1:
        raise ValueError("ranker output does not contain a JSON object or array")
    raw = raw[json_start:]

    try:
        outer = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ranker output invalid envelope JSON: {exc}") from exc

    # Handle two formats:
    # 1. Envelope dict: {"result": "[{...}]"} from subprocess path
    # 2. Direct array string: "[{...}]" from provider.generate() result
    if isinstance(outer, list):
        # Provider path: raw is already the JSON array string, parsed to list
        selections = outer
        result_text = raw
    else:
        # Subprocess path: outer is the envelope dict
        result_text = outer.get("result", "")
        if not result_text:
            raise ValueError("ranker output has empty result field")

        result_text = result_text.strip()
        result_text = result_text.removeprefix("```json").removeprefix("```").strip()
        result_text = result_text.removesuffix("```").strip()

        # The model should return a JSON array
        start = result_text.find("[")
        end = result_text.rfind("]")
        if start == -1 or end == -1:
            raise ValueError("ranker output does not contain a JSON array")

        selections = json.loads(result_text[start:end + 1])
        if not isinstance(selections, list):
            raise ValueError("ranker output is not a list")

    ranked = []
    for sel in selections:
        idx = int(sel["index"])
        if idx < 0 or idx >= len(candidates):
            continue
        candidate = dict(candidates[idx])
        candidate["reasons"] = sel.get("reasons", [])
        candidate["score"] = None  # model ranker doesn't produce numeric scores
        ranked.append(candidate)

    return ranked


def _get_debug_dir(repo_root: Path) -> Path:
    path = repo_root / "artifacts" / "debug"
    path.mkdir(parents=True, exist_ok=True)
    return path
