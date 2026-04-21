#!/usr/bin/env python3
"""Research stage: deterministic Brave retrieval and research packet management."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

ARTIFACTS_DIR_NAME = "artifacts"
RESEARCH_DIR_NAME = "research"

# Sections that derive from other sections rather than running independent queries
DERIVED_SECTIONS = {"sophies_challenge"}


# ---------------------------------------------------------------------------
# Schema types (plain dicts with documented shapes)
# ---------------------------------------------------------------------------

def make_candidate(
    title: str,
    url: str,
    domain: str,
    snippet: str,
    source: str = "",
    published_at: Optional[str] = None,
    query_source: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "title": title,
        "url": url,
        "domain": domain,
        "snippet": snippet,
        "source": source,
        "published_at": published_at,
        "query_source": query_source,
    }


def make_section_research(
    section_id: str,
    queries: List[str],
    ranking_profile: str,
    raw_candidates: List[Dict[str, Any]],
    filtered_candidates: Optional[List[Dict[str, Any]]] = None,
    ranked_candidates: Optional[List[Dict[str, Any]]] = None,
    derived_from: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "section_id": section_id,
        "queries": queries,
        "ranking_profile": ranking_profile,
        "raw_candidates": raw_candidates,
        "filtered_candidates": filtered_candidates or [],
        "ranked_candidates": ranked_candidates or [],
        "derived_from": derived_from,
    }


def make_research_packet(
    issue_date: date,
    sections: List[Dict[str, Any]],
    history_window: int = 3,
) -> Dict[str, Any]:
    return {
        "issue_date": issue_date.isoformat(),
        "history_window": {
            "issues_considered": history_window,
            "similarity_method": "token_jaccard",
        },
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# Research plan
# ---------------------------------------------------------------------------

def build_research_plan(today: date, config: dict, recent_headlines: List[str]) -> Dict[str, Any]:
    """Build a deterministic research plan: per-section queries and parameters."""
    profile = config["profile"]
    sections_catalog = config["sections"]
    research_cfg = config.get("research", {})
    active_section_ids = profile.get("newsletter", {}).get("active_sections", [])

    section_plans = []
    for section_id in active_section_ids:
        if section_id in DERIVED_SECTIONS:
            section_plans.append({
                "section_id": section_id,
                "derived_from": _get_dependency(section_id),
                "queries": [],
                "freshness": None,
                "count": 0,
                "ranking_profile": section_id + "_default",
                "safesearch": "strict",
            })
            continue

        section_cfg = sections_catalog.get(section_id, {})
        queries = _build_queries(section_id, section_cfg, research_cfg, today)
        freshness = _get_freshness(section_id, research_cfg)
        count = _get_result_count(section_id, research_cfg)
        ranking_profile = _get_ranking_profile(section_id, research_cfg)

        section_plans.append({
            "section_id": section_id,
            "derived_from": None,
            "queries": queries,
            "freshness": freshness,
            "count": count,
            "ranking_profile": ranking_profile,
            "safesearch": "strict",
        })

    return {
        "issue_date": today.isoformat(),
        "recent_headlines": recent_headlines,
        "section_plans": section_plans,
    }


def _get_dependency(section_id: str) -> Optional[str]:
    dependencies = {"sophies_challenge": "world_watch"}
    return dependencies.get(section_id)


def _build_queries(section_id: str, section_cfg: dict, research_cfg: dict, today: date) -> List[str]:
    """Return template queries for a section from research config or built-in defaults."""
    section_research = research_cfg.get("sections", {}).get(section_id, {})
    configured_queries = section_research.get("queries", [])
    if configured_queries:
        return [q.format(date=today.strftime("%B %Y")) for q in configured_queries]
    return _default_queries(section_id, today)


def _default_queries(section_id: str, today: date) -> List[str]:
    month_year = today.strftime("%B %Y")
    defaults: Dict[str, List[str]] = {
        "world_watch": [
            f"world news for kids {month_year}",
            "site:bbc.co.uk/newsround current events",
            "site:timeforkids.com current events",
            "site:newsforkids.net world news",
        ],
        "weird_but_true": [
            "site:kids.nationalgeographic.com weird animal facts",
            "site:kids.britannica.com surprising science facts",
            "amazing weird animal facts for kids",
        ],
        "singapore_spotlight": [
            "singapore interesting facts kids",
            "site:kids.britannica.com singapore",
            "singapore culture history fun facts",
        ],
        "usa_corner": [
            f"california kids news {month_year}",
            f"USA science culture kids {month_year}",
            "site:timeforkids.com usa news",
        ],
        "gymnastics_corner": [
            "gymnastics news athletes kids",
            "site:olympics.com gymnastics",
            f"gymnastics competition highlights {month_year}",
        ],
        "money_moves": [
            "kid entrepreneur story saving money",
            "kids business ideas entrepreneurship",
            "financial literacy kids saving",
        ],
    }
    return defaults.get(section_id, [f"{section_id} kids news {month_year}"])


def _get_freshness(section_id: str, research_cfg: dict) -> Optional[str]:
    """Return Brave freshness parameter for a section (pd/pw/pm/py or None)."""
    section_research = research_cfg.get("sections", {}).get(section_id, {})
    if "freshness" in section_research:
        return section_research["freshness"]
    # Sections that need current content
    current_sections = {"world_watch", "usa_corner", "gymnastics_corner"}
    return "pm" if section_id in current_sections else None


def _get_result_count(section_id: str, research_cfg: dict) -> int:
    section_research = research_cfg.get("sections", {}).get(section_id, {})
    return section_research.get("count", 10)


def _get_ranking_profile(section_id: str, research_cfg: dict) -> str:
    section_research = research_cfg.get("sections", {}).get(section_id, {})
    return section_research.get("ranking_profile", f"{section_id}_default")


# ---------------------------------------------------------------------------
# Research execution
# ---------------------------------------------------------------------------

def run_research(plan: Dict[str, Any], repo_root: Path) -> Dict[str, Any]:
    """Execute the research plan via Brave and return raw candidate pools per section."""
    from providers.brave_search import BraveSearchClient

    api_key = _load_brave_api_key(repo_root)
    client = BraveSearchClient(api_key)

    section_results: List[Dict[str, Any]] = []
    for sp in plan["section_plans"]:
        section_id = sp["section_id"]
        if sp.get("derived_from"):
            section_results.append(make_section_research(
                section_id=section_id,
                queries=[],
                ranking_profile=sp["ranking_profile"],
                raw_candidates=[],
                derived_from=sp["derived_from"],
            ))
            continue

        raw_candidates: List[Dict[str, Any]] = []
        for query in sp["queries"]:
            results = client.search(
                q=query,
                count=sp["count"],
                freshness=sp.get("freshness"),
                safesearch=sp.get("safesearch", "strict"),
            )
            for r in results:
                r["query_source"] = query
            raw_candidates.extend(results)

        section_results.append(make_section_research(
            section_id=section_id,
            queries=sp["queries"],
            ranking_profile=sp["ranking_profile"],
            raw_candidates=raw_candidates,
        ))

    return {
        "issue_date": plan["issue_date"],
        "recent_headlines": plan.get("recent_headlines", []),
        "sections": section_results,
    }


def _load_brave_api_key(repo_root: Path) -> str:
    env_path = repo_root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("BRAVE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    import os
    key = os.environ.get("BRAVE_API_KEY", "")
    if not key:
        raise RuntimeError("BRAVE_API_KEY not found in .env or environment")
    return key


# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------

def get_research_artifact_path(
    repo_root: Path,
    issue_date: date,
    run_tag: Optional[str] = None,
    artifacts_root: Optional[Path] = None,
) -> Path:
    filename = f"sophie-{issue_date.isoformat()}"
    if run_tag:
        filename += f"-{run_tag}"
    filename += ".json"
    root = artifacts_root if artifacts_root is not None else repo_root / ARTIFACTS_DIR_NAME
    return root / RESEARCH_DIR_NAME / filename


def compute_research_config_hash(config: dict) -> str:
    """Stable fingerprint of the inputs that determine what retrieval produces.

    Covers: active sections, per-section query templates, counts, and freshness
    settings. Changing any of these makes a cached packet potentially stale.
    """
    profile = config["profile"]
    active_sections = profile.get("newsletter", {}).get("active_sections", [])
    research_cfg = config.get("research", {})
    sections_cfg = research_cfg.get("sections", {})

    fingerprint = {
        "active_sections": active_sections,
        "section_queries": {
            sid: {
                "queries": sections_cfg.get(sid, {}).get("queries", []),
                "count": sections_cfg.get(sid, {}).get("count"),
                "freshness": sections_cfg.get(sid, {}).get("freshness"),
            }
            for sid in active_sections
        },
    }
    canonical = json.dumps(fingerprint, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def save_research_packet(packet: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")


def load_research_packet(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
