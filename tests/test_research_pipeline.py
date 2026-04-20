"""Tests for the deterministic research pipeline: retrieval, filtering, ranking."""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import research_stage
import ranking_stage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_config():
    return {
        "profile": {
            "id": "sophie",
            "name": "Sophie",
            "age_band": "4th-grade",
            "location": "Fremont, California",
            "newsletter": {
                "active_sections": ["world_watch", "weird_but_true", "sophies_challenge"],
                "generation": {"content_provider": "hosted_integrated_search"},
            },
        },
        "sections": {
            "world_watch": {
                "title": "World Watch",
                "goal": "current events",
                "block_type": "story_list",
                "source_preferences": ["BBC Newsround"],
            },
            "weird_but_true": {
                "title": "Weird But True",
                "goal": "fun facts",
                "block_type": "fact_list",
                "source_preferences": ["Nat Geo Kids"],
            },
            "sophies_challenge": {
                "title": "Weekly Challenge",
                "goal": "math puzzle",
                "block_type": "challenge",
                "source_preferences": [],
            },
        },
        "research": {
            "ranking": {
                "defaults": {
                    "source_boost": 20,
                    "freshness_boost": 15,
                    "keyword_match_boost": 5,
                    "geography_boost": 8,
                    "kid_safe_boost": 10,
                    "novelty_penalty": 30,
                    "junk_penalty": 40,
                    "min_score": 0,
                    "max_ranked": 3,
                },
                "sections": {
                    "world_watch": {
                        "keywords": ["world", "news"],
                        "max_ranked": 2,
                    },
                    "weird_but_true": {
                        "keywords": ["animal", "weird"],
                    },
                },
            },
            "novelty": {
                "history_window": 3,
                "similarity_threshold": 0.4,
                "title_token_limit": 12,
            },
            "domains": {
                "kid_safe": ["kids.nationalgeographic.com", "bbc.co.uk"],
                "blocked": ["reddit.com", "twitter.com"],
            },
        },
    }


def _make_candidate(title, url="https://example.com/a", domain="example.com", snippet="some text"):
    return research_stage.make_candidate(title=title, url=url, domain=domain, snippet=snippet)


# ---------------------------------------------------------------------------
# research_stage: make_candidate / make_research_packet
# ---------------------------------------------------------------------------

def test_make_candidate_fields():
    c = research_stage.make_candidate(
        title="Test Title",
        url="https://example.com",
        domain="example.com",
        snippet="A snippet",
        source="Example",
        published_at="2026-04-18",
    )
    assert c["title"] == "Test Title"
    assert c["url"] == "https://example.com"
    assert c["domain"] == "example.com"
    assert c["published_at"] == "2026-04-18"


def test_make_research_packet_structure():
    sections = []
    packet = research_stage.make_research_packet(date(2026, 4, 20), sections, history_window=3)
    assert packet["issue_date"] == "2026-04-20"
    assert packet["history_window"]["similarity_method"] == "token_jaccard"
    assert packet["history_window"]["issues_considered"] == 3
    assert packet["sections"] == []


# ---------------------------------------------------------------------------
# research_stage: build_research_plan
# ---------------------------------------------------------------------------

def test_build_research_plan_returns_section_plans(minimal_config):
    plan = research_stage.build_research_plan(date(2026, 4, 20), minimal_config, [])
    ids = [sp["section_id"] for sp in plan["section_plans"]]
    assert "world_watch" in ids
    assert "weird_but_true" in ids


def test_build_research_plan_derived_sections_have_no_queries(minimal_config):
    plan = research_stage.build_research_plan(date(2026, 4, 20), minimal_config, [])
    challenge_plan = next(sp for sp in plan["section_plans"] if sp["section_id"] == "sophies_challenge")
    assert challenge_plan["queries"] == []
    assert challenge_plan["derived_from"] == "world_watch"


def test_build_research_plan_active_sections_have_queries(minimal_config):
    plan = research_stage.build_research_plan(date(2026, 4, 20), minimal_config, [])
    ww_plan = next(sp for sp in plan["section_plans"] if sp["section_id"] == "world_watch")
    assert len(ww_plan["queries"]) > 0


# ---------------------------------------------------------------------------
# research_stage: artifact persistence
# ---------------------------------------------------------------------------

def test_save_and_load_research_packet(tmp_path):
    packet = {"issue_date": "2026-04-20", "sections": []}
    path = tmp_path / "research" / "sophie-2026-04-20.json"
    research_stage.save_research_packet(packet, path)
    assert path.exists()
    loaded = research_stage.load_research_packet(path)
    assert loaded["issue_date"] == "2026-04-20"


def test_get_research_artifact_path(tmp_path):
    path = research_stage.get_research_artifact_path(tmp_path, date(2026, 4, 20))
    assert path.name == "sophie-2026-04-20.json"
    assert "research" in str(path)


# ---------------------------------------------------------------------------
# ranking_stage: tokenize and jaccard
# ---------------------------------------------------------------------------

def test_tokenize_basic():
    tokens = ranking_stage._tokenize("Hello World 123!")
    assert "hello" in tokens
    assert "world" in tokens
    assert "123" in tokens


def test_jaccard_identical():
    a = ["cat", "dog", "fish"]
    assert ranking_stage._jaccard(a, a) == 1.0


def test_jaccard_disjoint():
    a = ["cat", "dog"]
    b = ["fish", "bird"]
    assert ranking_stage._jaccard(a, b) == 0.0


def test_jaccard_partial():
    a = ["cat", "dog", "fish"]
    b = ["cat", "dog", "bird"]
    score = ranking_stage._jaccard(a, b)
    assert 0 < score < 1


def test_is_near_duplicate_detects_match():
    tokens = ["earth", "day", "events", "ramp", "up"]
    seen = [["earth", "day", "events", "ramp", "globally"]]
    assert ranking_stage._is_near_duplicate(tokens, seen, threshold=0.5)


def test_is_near_duplicate_no_match():
    tokens = ["gymnastics", "competition", "highlights"]
    seen = [["earth", "day", "events", "climate"]]
    assert not ranking_stage._is_near_duplicate(tokens, seen, threshold=0.5)


# ---------------------------------------------------------------------------
# ranking_stage: prefilter
# ---------------------------------------------------------------------------

def _make_raw_pool(section_id, candidates, recent_headlines=None):
    return {
        "issue_date": "2026-04-20",
        "recent_headlines": recent_headlines or [],
        "sections": [
            research_stage.make_section_research(
                section_id=section_id,
                queries=["test query"],
                ranking_profile=f"{section_id}_default",
                raw_candidates=candidates,
            )
        ],
    }


def test_prefilter_removes_blocked_domains(minimal_config):
    candidates = [
        _make_candidate("Reddit Post", url="https://reddit.com/r/foo", domain="reddit.com", snippet="some content"),
        _make_candidate("Good Article", url="https://bbc.co.uk/news/1", domain="bbc.co.uk", snippet="real news"),
    ]
    pool = _make_raw_pool("world_watch", candidates)
    filtered = ranking_stage.prefilter_candidates(pool, minimal_config)
    fc = filtered["sections"][0]["filtered_candidates"]
    domains = [c["domain"] for c in fc]
    assert "reddit.com" not in domains
    assert "bbc.co.uk" in domains


def test_prefilter_removes_empty_title_or_snippet(minimal_config):
    candidates = [
        _make_candidate("", url="https://example.com/1", domain="example.com", snippet="content"),
        _make_candidate("Title", url="https://example.com/2", domain="example.com", snippet=""),
        _make_candidate("Valid", url="https://example.com/3", domain="example.com", snippet="valid content"),
    ]
    pool = _make_raw_pool("world_watch", candidates)
    filtered = ranking_stage.prefilter_candidates(pool, minimal_config)
    fc = filtered["sections"][0]["filtered_candidates"]
    assert len(fc) == 1
    assert fc[0]["title"] == "Valid"


def test_prefilter_removes_duplicate_urls(minimal_config):
    c1 = _make_candidate("Article A", url="https://example.com/same", domain="example.com", snippet="content a")
    c2 = _make_candidate("Article A copy", url="https://example.com/same", domain="example.com", snippet="content b")
    pool = _make_raw_pool("world_watch", [c1, c2])
    filtered = ranking_stage.prefilter_candidates(pool, minimal_config)
    assert len(filtered["sections"][0]["filtered_candidates"]) == 1


def test_prefilter_removes_near_duplicate_titles(minimal_config):
    c1 = _make_candidate("Earth Day Events Around the World", url="https://example.com/1", domain="example.com", snippet="great")
    c2 = _make_candidate("Earth Day Events Around the World Today", url="https://example.com/2", domain="example.com", snippet="also")
    pool = _make_raw_pool("world_watch", [c1, c2])
    filtered = ranking_stage.prefilter_candidates(pool, minimal_config)
    assert len(filtered["sections"][0]["filtered_candidates"]) == 1


def test_prefilter_skips_derived_sections(minimal_config):
    candidates = [_make_candidate("Challenge Hint", domain="example.com", snippet="some math")]
    pool = {
        "issue_date": "2026-04-20",
        "recent_headlines": [],
        "sections": [
            research_stage.make_section_research(
                section_id="sophies_challenge",
                queries=[],
                ranking_profile="sophies_challenge_default",
                raw_candidates=candidates,
                derived_from="world_watch",
            )
        ],
    }
    filtered = ranking_stage.prefilter_candidates(pool, minimal_config)
    # Derived sections pass through with empty filtered_candidates
    assert filtered["sections"][0]["filtered_candidates"] == []


# ---------------------------------------------------------------------------
# ranking_stage: heuristic scoring
# ---------------------------------------------------------------------------

def test_score_candidate_kid_safe_boost(minimal_config):
    cfg = minimal_config["research"]["ranking"]["defaults"]
    kid_safe = {"bbc.co.uk"}
    snippet = "A major world news story covered in depth by BBC Newsround for young readers this week."
    c = research_stage.make_candidate("News Story", url="https://bbc.co.uk/1", domain="bbc.co.uk", snippet=snippet)
    score, reasons = ranking_stage._score_candidate(c, {**cfg, "keywords": ["news"]}, kid_safe, [], {})
    assert score > 0
    assert any("kid-safe" in r for r in reasons)


def test_score_candidate_novelty_penalty(minimal_config):
    cfg = minimal_config["research"]["ranking"]["defaults"]
    kid_safe = set()
    recent = [ranking_stage._tokenize("Earth Day Events Around the World")]
    c = research_stage.make_candidate(
        "Earth Day Events Around the World",
        url="https://example.com/1",
        domain="example.com",
        snippet="earth day news",
    )
    score, reasons = ranking_stage._score_candidate(
        c, {**cfg, "keywords": []}, kid_safe, recent,
        {"similarity_threshold": 0.4}
    )
    assert any("similar to recent headline" in r for r in reasons)


def test_heuristic_rank_caps_max_ranked(minimal_config, tmp_path):
    candidates = [
        _make_candidate(f"Story {i}", url=f"https://example.com/{i}", domain="example.com", snippet=f"content {i}")
        for i in range(10)
    ]
    pool = {
        "issue_date": "2026-04-20",
        "recent_headlines": [],
        "sections": [
            research_stage.make_section_research(
                section_id="world_watch",
                queries=["test"],
                ranking_profile="world_watch_default",
                raw_candidates=[],
                filtered_candidates=candidates,
            )
        ],
    }
    # Patch _load_issue_history_titles to return empty
    original = ranking_stage._load_issue_history_titles
    ranking_stage._load_issue_history_titles = lambda *a: []
    try:
        result = ranking_stage._heuristic_rank(pool, minimal_config, tmp_path)
    finally:
        ranking_stage._load_issue_history_titles = original

    ranked = result["sections"][0]["ranked_candidates"]
    assert len(ranked) <= 2  # world_watch max_ranked=2 in minimal_config


# ---------------------------------------------------------------------------
# ranking_stage: is_blocked
# ---------------------------------------------------------------------------

def test_is_blocked_exact_match():
    assert ranking_stage._is_blocked("reddit.com", {"reddit.com"})


def test_is_blocked_subdomain():
    assert ranking_stage._is_blocked("old.reddit.com", {"reddit.com"})


def test_is_blocked_no_match():
    assert not ranking_stage._is_blocked("bbc.co.uk", {"reddit.com"})
