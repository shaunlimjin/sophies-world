"""Ranking stage: deterministic prefilter and pluggable ranker dispatch."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from research_stage import DERIVED_SECTIONS

# Brave freshness param → max age in days
_FRESHNESS_DAYS = {"pd": 1, "pw": 7, "pm": 30, "py": 365}


def _get_blocked_domains(config: dict) -> List[str]:
    """Return blocked domains from pipeline config or legacy research config."""
    if "pipeline" in config:
        return config["pipeline"].get("global_domains", {}).get("blocked", [])
    return config.get("research", {}).get("domains", {}).get("blocked", [])


def _get_kid_safe_domains(config: dict) -> List[str]:
    """Return kid-safe domains from pipeline config or legacy research config."""
    if "pipeline" in config:
        return config["pipeline"].get("global_domains", {}).get("kid_safe", [])
    return config.get("research", {}).get("domains", {}).get("kid_safe", [])


def prefilter_candidates(raw_pool: Dict[str, Any], config: dict) -> Dict[str, Any]:
    """Apply deterministic prefilter to each section's raw candidate list."""
    blocked_domains = set(_get_blocked_domains(config))

    filtered_sections = []
    for section in raw_pool["sections"]:
        section_id = section["section_id"]
        if section_id in DERIVED_SECTIONS:
            filtered_sections.append({**section, "filtered_candidates": []})
            continue

        candidates = section.get("raw_candidates", [])
        seen_urls: set = set()
        seen_title_tokens: list = []
        filtered = []

        for c in candidates:
            url = c.get("url", "")
            domain = c.get("domain", "")
            title = c.get("title", "").strip()
            snippet = c.get("snippet", "").strip()

            # Safety: drop blocked domains
            if _is_blocked(domain, blocked_domains):
                continue

            # Safety: drop items with no title or snippet
            if not title or not snippet:
                continue

            # Dedup by exact URL
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Dedup by near-identical title (token overlap ≥ 0.8)
            tokens = _tokenize(title)
            if _is_near_duplicate(tokens, seen_title_tokens, threshold=0.8):
                continue
            seen_title_tokens.append(tokens)

            filtered.append(c)

        filtered_sections.append({**section, "filtered_candidates": filtered})

    return {**raw_pool, "sections": filtered_sections}


def rank_candidates(
    filtered_pool: Dict[str, Any],
    config: dict,
    ranker_provider: str,
    repo_root: Path,
    model_override: str | None = None,
) -> Dict[str, Any]:
    """Dispatch to the configured ranker and return the research packet."""
    if ranker_provider == "heuristic_ranker":
        return _heuristic_rank(filtered_pool, config, repo_root)
    if ranker_provider == "hosted_model_ranker":
        from providers.model_providers import make_provider
        from providers.model_presets import load_presets, resolve_model_config
        raw_cfg = (
            model_override
            or config.get("pipeline", {}).get("models", {}).get("ranking")
        )
        if not raw_cfg:
            raise ValueError(
                "hosted_model_ranker requires a model preset. "
                "Set 'pipeline.models.ranking' in config or pass model_override."
            )
        presets = load_presets(repo_root)
        resolved = resolve_model_config(raw_cfg, presets)
        provider = make_provider(resolved, repo_root=repo_root)
        from providers.llm_providers import model_rank_candidates
        return model_rank_candidates(filtered_pool, config, repo_root, provider=provider)
    raise ValueError(f"Unknown ranker_provider: '{ranker_provider}'")


def run_ranking_stage(
    config: dict,
    today: date,
    repo_root: Path,
    artifacts_root: Path,
    ranker_provider: str,
    model_override: str | None = None,
    log: Callable[[str], None] = print,
) -> dict:
    """Read -raw.json, prefilter + rank, persist ranked packet, return it."""
    from research_stage import (
        get_raw_research_artifact_path,
        get_research_artifact_path,
        load_research_packet,
        save_research_packet,
    )
    raw_path = get_raw_research_artifact_path(repo_root, today, artifacts_root)
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw research packet not found: {raw_path}. Run research stage first."
        )
    log(f"Loading raw research packet...")
    raw_packet = load_research_packet(raw_path)

    log("Prefiltering candidates...")
    filtered = prefilter_candidates(raw_packet, config)

    log(f"Ranking with {ranker_provider}...")
    ranked = rank_candidates(filtered, config, ranker_provider, repo_root, model_override=model_override)

    ranked_path = get_research_artifact_path(repo_root, today, artifacts_root=artifacts_root)
    save_research_packet(ranked, ranked_path)
    log(f"Ranked packet saved: {ranked_path}")
    return ranked


# ---------------------------------------------------------------------------
# Heuristic ranker
# ---------------------------------------------------------------------------

def _heuristic_rank(pool: Dict[str, Any], config: dict, repo_root: Path) -> Dict[str, Any]:
    pipeline_cfg = config.get("pipeline", {})
    global_ranking_defaults = pipeline_cfg.get("global_ranking_defaults", {})
    novelty_cfg = pipeline_cfg.get("novelty", {})
    kid_safe_domains = set(_get_kid_safe_domains(config))
    sections_catalog = config.get("sections", {})

    recent_headlines = pool.get("recent_headlines", [])
    issue_history_titles = _load_issue_history_titles(repo_root, novelty_cfg.get("history_window", 3))
    all_recent_titles = [_tokenize(h) for h in recent_headlines + issue_history_titles]

    ranked_sections = []
    for section in pool["sections"]:
        section_id = section["section_id"]
        if section_id in DERIVED_SECTIONS:
            ranked_sections.append({**section, "ranked_candidates": []})
            continue

        sec_cfg = _get_section_ranking_config(section_id, global_ranking_defaults, sections_catalog)
        # Expose freshness window (in days) to scorer; None means no window enforcement
        raw_freshness = sections_catalog.get(section_id, {}).get("research", {}).get("freshness")
        sec_cfg["freshness_window_days"] = _FRESHNESS_DAYS.get(raw_freshness) if raw_freshness else None
        candidates = section.get("filtered_candidates", [])
        ranking_profile = section.get("ranking_profile", f"{section_id}_default")

        scored = []
        for c in candidates:
            score, reasons = _score_candidate(c, sec_cfg, kid_safe_domains, all_recent_titles, novelty_cfg)
            if score >= sec_cfg.get("min_score", 0):
                scored.append({**c, "score": score, "reasons": reasons})

        scored.sort(key=lambda x: x["score"], reverse=True)
        max_ranked = sec_cfg.get("max_ranked", 5)
        ranked_sections.append({
            **section,
            "ranked_candidates": scored[:max_ranked],
        })

    return {**pool, "sections": ranked_sections}


def _get_section_ranking_config(section_id: str, global_defaults: dict, sections_catalog: dict) -> dict:
    """Merge global defaults with section-local ranking overrides."""
    sec_ranking = sections_catalog.get(section_id, {}).get("ranking", {})
    return {**global_defaults, **sec_ranking}


def _score_candidate(
    candidate: Dict[str, Any],
    cfg: Dict[str, Any],
    kid_safe_domains: set,
    recent_title_tokens: List[List[str]],
    novelty_cfg: dict,
) -> tuple:
    score = 0
    reasons = []
    title = candidate.get("title", "")
    snippet = candidate.get("snippet", "")
    domain = candidate.get("domain", "")
    text = (title + " " + snippet).lower()

    # Junk penalty: very short snippets are a low-quality signal
    junk_penalty = cfg.get("junk_penalty", 40)
    if len(snippet.strip()) < 60:
        score -= junk_penalty
        reasons.append(f"very short snippet (-{junk_penalty})")

    # Kid-safe source boost (only for explicitly known child-safe publishers)
    if domain in kid_safe_domains:
        boost = cfg.get("kid_safe_boost", 10)
        score += boost
        reasons.append(f"kid-safe source (+{boost})")

    # Freshness: apply boost only when published_at parses to within the section window.
    # If the section has no freshness window, boost unconditionally for having a date.
    freshness_boost = cfg.get("freshness_boost", 15)
    if freshness_boost > 0:
        published_at = candidate.get("published_at")
        freshness_window_days = cfg.get("freshness_window_days")
        if published_at:
            parsed_date = _parse_date(published_at)
            if parsed_date is not None:
                if freshness_window_days is None:
                    # Section has no recency requirement — reward having a date at all
                    score += freshness_boost // 2
                    reasons.append(f"has publish date (+{freshness_boost // 2})")
                else:
                    age_days = (date.today() - parsed_date).days
                    if age_days <= freshness_window_days:
                        score += freshness_boost
                        reasons.append(f"fresh ({age_days}d ≤ {freshness_window_days}d window) (+{freshness_boost})")
                    else:
                        stale_penalty = freshness_boost
                        score -= stale_penalty
                        reasons.append(f"stale ({age_days}d > {freshness_window_days}d window) (-{stale_penalty})")

    # Keyword match boost
    keywords = cfg.get("keywords", [])
    keyword_boost = cfg.get("keyword_match_boost", 5)
    matched = [kw for kw in keywords if kw.lower() in text]
    if matched:
        kw_score = min(keyword_boost * len(matched), keyword_boost * 3)
        score += kw_score
        reasons.append(f"keyword match: {', '.join(matched[:3])} (+{kw_score})")

    # Geography boost
    geography_boost = cfg.get("geography_boost", 8)
    geo_terms = ["california", "fremont", "bay area", "singapore", "usa", "america"]
    geo_matches = [t for t in geo_terms if t in text]
    if geo_matches:
        score += geography_boost
        reasons.append(f"geo match: {', '.join(geo_matches[:2])} (+{geography_boost})")

    # Novelty penalty
    title_tokens = _tokenize(title)
    similarity_threshold = novelty_cfg.get("similarity_threshold", 0.4)
    novelty_penalty = cfg.get("novelty_penalty", 30)
    for recent_tokens in recent_title_tokens:
        sim = _jaccard(title_tokens, recent_tokens)
        if sim >= similarity_threshold:
            score -= novelty_penalty
            reasons.append(f"similar to recent headline (-{novelty_penalty})")
            break

    return score, reasons


def _parse_date(value: str) -> Optional[date]:
    """Try to parse a date string into a date object. Returns None if unparseable."""
    if not value:
        return None
    value = value.strip()
    # Try ISO format first
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    # Common Brave formats: "Apr 18, 2026"
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    # Relative: "N days ago", "N hours ago" — approximate
    m = re.match(r"(\d+)\s+day", value, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        from datetime import timedelta
        return date.today() - timedelta(days=days)
    m = re.match(r"(\d+)\s+hour", value, re.IGNORECASE)
    if m:
        return date.today()
    return None


# ---------------------------------------------------------------------------
# Novelty / issue history
# ---------------------------------------------------------------------------

def _load_issue_history_titles(repo_root: Path, window: int) -> List[str]:
    artifacts_dir = repo_root / "artifacts" / "issues"
    if not artifacts_dir.exists():
        return []
    files = sorted(artifacts_dir.glob("sophie-*.json"))
    titles = []
    for f in files[-window:]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for section in data.get("sections", []):
                for item in section.get("items", []):
                    t = item.get("headline") or item.get("title") or ""
                    if t:
                        titles.append(t)
        except Exception:
            pass
    return titles


# ---------------------------------------------------------------------------
# String/token utilities
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    import re
    return re.findall(r"[a-z0-9]+", text.lower())


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _is_near_duplicate(tokens: List[str], seen: List[List[str]], threshold: float) -> bool:
    for existing in seen:
        if _jaccard(tokens, existing) >= threshold:
            return True
    return False


def _is_blocked(domain: str, blocked_domains: set) -> bool:
    for blocked in blocked_domains:
        if domain == blocked or domain.endswith("." + blocked):
            return True
    return False
