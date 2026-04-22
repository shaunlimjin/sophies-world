"""Integration-style tests for mode wiring, cache identity, derived-section packets,
and ranker failure fallback."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import generate
import research_stage
import ranking_stage
import content_stage


# ---------------------------------------------------------------------------
# Mode wiring: resolve_providers
# ---------------------------------------------------------------------------

def _make_config(content_provider="hosted_integrated_search", ranker_provider="heuristic_ranker"):
    return {
        "profile": {
            "newsletter": {
                "generation": {
                    "content_provider": content_provider,
                    "ranker_provider": ranker_provider,
                }
            }
        },
        "research": {},
    }


def test_resolve_providers_returns_config_defaults():
    config = _make_config("hosted_integrated_search", "heuristic_ranker")
    cp, rp = generate.resolve_providers(config, None, None)
    assert cp == "hosted_integrated_search"
    assert rp == "heuristic_ranker"


def test_resolve_providers_cli_overrides_config():
    config = _make_config("hosted_integrated_search", "heuristic_ranker")
    cp, rp = generate.resolve_providers(config, "hosted_packet_synthesis", "hosted_model_ranker")
    assert cp == "hosted_packet_synthesis"
    assert rp == "hosted_model_ranker"


def test_resolve_providers_partial_override():
    config = _make_config("hosted_integrated_search", "heuristic_ranker")
    cp, rp = generate.resolve_providers(config, "hosted_packet_synthesis", None)
    assert cp == "hosted_packet_synthesis"
    assert rp == "heuristic_ranker"  # from config, not overridden


def test_mode_a_constant_is_integrated_search():
    assert generate.CONTENT_PROVIDER_INTEGRATED == "hosted_integrated_search"


def test_mode_b_constant_is_packet_synthesis():
    assert generate.CONTENT_PROVIDER_PACKET == "hosted_packet_synthesis"


def test_ranker_constants_are_separate_from_content_providers():
    # Ranker values must not overlap with content provider values
    assert generate.RANKER_HEURISTIC not in generate.VALID_CONTENT_PROVIDERS
    assert generate.RANKER_HOSTED_MODEL not in generate.VALID_CONTENT_PROVIDERS


# ---------------------------------------------------------------------------
# Cache identity: compute_research_config_hash
# ---------------------------------------------------------------------------

def _base_research_config():
    return {
        "profile": {
            "id": "sophie",
            "name": "Sophie",
            "age_band": "4th-grade",
            "location": "Fremont, California",
            "cultural_context": [],
            "interests": {"active": []},
            "newsletter": {
                "active_sections": ["world_watch", "weird_but_true"],
                "editorial": {},
                "generation": {
                    "content_provider": "hosted_packet_synthesis",
                    "ranker_provider": "heuristic_ranker",
                },
            },
        },
        "sections": {},  # section catalog; empty because tests use empty research packets
        "research": {
            "sections": {
                "world_watch": {
                    "queries": ["world news kids {date}"],
                    "count": 10,
                    "freshness": "pw",
                },
                "weird_but_true": {
                    "queries": ["weird animal facts kids"],
                    "count": 8,
                    "freshness": None,
                },
            }
        },
    }


def test_config_hash_is_stable():
    config = _base_research_config()
    h1 = research_stage.compute_research_config_hash(config)
    h2 = research_stage.compute_research_config_hash(config)
    assert h1 == h2


def test_config_hash_changes_when_query_changes():
    config = _base_research_config()
    h1 = research_stage.compute_research_config_hash(config)
    config["research"]["sections"]["world_watch"]["queries"] = ["different query"]
    h2 = research_stage.compute_research_config_hash(config)
    assert h1 != h2


def test_config_hash_changes_when_active_sections_change():
    config = _base_research_config()
    h1 = research_stage.compute_research_config_hash(config)
    config["profile"]["newsletter"]["active_sections"] = ["world_watch"]
    h2 = research_stage.compute_research_config_hash(config)
    assert h1 != h2


def test_config_hash_changes_when_count_changes():
    config = _base_research_config()
    h1 = research_stage.compute_research_config_hash(config)
    config["research"]["sections"]["world_watch"]["count"] = 20
    h2 = research_stage.compute_research_config_hash(config)
    assert h1 != h2


def test_config_hash_length():
    config = _base_research_config()
    h = research_stage.compute_research_config_hash(config)
    assert len(h) == 16  # truncated SHA256 hex


def _fake_issue():
    return {
        "issue_date": "2026-04-20", "issue_number": 1, "child_id": "sophie",
        "child_name": "Sophie", "theme_id": "default", "editorial": {},
        "greeting_text": "hi", "sections": [],
        "footer": {"issue_number": 1, "issue_date_display": "April 20, 2026", "tagline": "", "location_line": ""},
    }


def _run_mode_b_patched(config, tmp_path, refresh_research, artifact_path, research_calls):
    """Run run_mode_b with all external calls stubbed out.

    Patches functions in generate's own namespace (for top-level imports) and
    in research_stage/ranking_stage (imported inside the function body).
    """
    import generate as gen_mod
    import research_stage as rs_mod
    import ranking_stage as rank_mod

    def fake_build_plan(*a, **kw):
        research_calls.append("plan")
        return {"section_plans": [], "issue_date": "2026-04-20", "recent_headlines": []}

    def fake_run_research(plan, repo_root):
        research_calls.append("run")
        return {"issue_date": "2026-04-20", "recent_headlines": [], "sections": []}

    # research_stage and ranking_stage are imported inside run_mode_b's body,
    # so patching the module attributes is sufficient for those.
    # build_packet_synthesis_prompt / parse_content_output / validate_issue_artifact
    # are imported at generate.py's module level, so patch generate's namespace.
    orig_plan = rs_mod.build_research_plan
    orig_run = rs_mod.run_research
    orig_pre = rank_mod.prefilter_candidates
    orig_rank = rank_mod.rank_candidates
    orig_prompt = gen_mod.build_packet_synthesis_prompt
    orig_synth = gen_mod.run_packet_synthesis_provider
    orig_parse = gen_mod.parse_content_output
    orig_validate = gen_mod.validate_issue_artifact

    rs_mod.build_research_plan = fake_build_plan
    rs_mod.run_research = fake_run_research
    rank_mod.prefilter_candidates = lambda pool, cfg: pool
    rank_mod.rank_candidates = lambda pool, cfg, ranker, repo_root: pool
    gen_mod.build_packet_synthesis_prompt = lambda *a, **kw: "prompt"
    gen_mod.run_packet_synthesis_provider = lambda prompt, repo_root, provider=None, **kwargs: "raw"
    gen_mod.parse_content_output = lambda raw, repo_root=None: _fake_issue()
    gen_mod.validate_issue_artifact = lambda issue: None
    try:
        gen_mod.run_mode_b(date(2026, 4, 20), 1, config, [], tmp_path, "heuristic_ranker", refresh_research=refresh_research)
    finally:
        rs_mod.build_research_plan = orig_plan
        rs_mod.run_research = orig_run
        rank_mod.prefilter_candidates = orig_pre
        rank_mod.rank_candidates = orig_rank
        gen_mod.build_packet_synthesis_prompt = orig_prompt
        gen_mod.run_packet_synthesis_provider = orig_synth
        gen_mod.parse_content_output = orig_parse
        gen_mod.validate_issue_artifact = orig_validate


def test_matching_hash_reuses_cache(tmp_path):
    """When cached packet hash matches current config, run_mode_b reuses it without calling research."""
    config = _base_research_config()
    config_hash = research_stage.compute_research_config_hash(config)
    packet = {"issue_date": "2026-04-20", "sections": [], "config_hash": config_hash}
    artifact_path = research_stage.get_research_artifact_path(tmp_path, date(2026, 4, 20))
    research_stage.save_research_packet(packet, artifact_path)

    research_calls = []
    _run_mode_b_patched(config, tmp_path, refresh_research=False, artifact_path=artifact_path, research_calls=research_calls)

    assert research_calls == [], f"Expected no research calls on hash match, got: {research_calls}"


def test_mismatched_hash_reruns_research(tmp_path):
    """When cached packet has a different hash, run_mode_b reruns research and overwrites the artifact."""
    config = _base_research_config()
    stale_packet = {"issue_date": "2026-04-20", "sections": [], "config_hash": "stale000deadbeef"}
    artifact_path = research_stage.get_research_artifact_path(tmp_path, date(2026, 4, 20))
    research_stage.save_research_packet(stale_packet, artifact_path)

    research_calls = []
    _run_mode_b_patched(config, tmp_path, refresh_research=False, artifact_path=artifact_path, research_calls=research_calls)

    assert "plan" in research_calls, "Expected research to rerun on hash mismatch"
    fresh = research_stage.load_research_packet(artifact_path)
    assert fresh.get("config_hash") == research_stage.compute_research_config_hash(config)


def test_refresh_research_flag_forces_rerun_even_with_matching_hash(tmp_path):
    """--refresh-research reruns research even when the cached hash matches."""
    config = _base_research_config()
    config_hash = research_stage.compute_research_config_hash(config)
    fresh_packet = {"issue_date": "2026-04-20", "sections": [], "config_hash": config_hash}
    artifact_path = research_stage.get_research_artifact_path(tmp_path, date(2026, 4, 20))
    research_stage.save_research_packet(fresh_packet, artifact_path)

    research_calls = []
    _run_mode_b_patched(config, tmp_path, refresh_research=True, artifact_path=artifact_path, research_calls=research_calls)

    assert "plan" in research_calls, "Expected research to rerun with --refresh-research even on hash match"


# ---------------------------------------------------------------------------
# Derived-section packet: sophies_challenge gets world_watch candidates
# ---------------------------------------------------------------------------

def _make_research_packet_with_sections(world_watch_candidates, include_challenge=True):
    sections = [
        {
            "section_id": "world_watch",
            "queries": ["world news kids"],
            "ranking_profile": "world_watch_default",
            "raw_candidates": [],
            "filtered_candidates": world_watch_candidates,
            "ranked_candidates": world_watch_candidates,
            "derived_from": None,
        }
    ]
    if include_challenge:
        sections.append({
            "section_id": "sophies_challenge",
            "queries": [],
            "ranking_profile": "sophies_challenge_default",
            "raw_candidates": [],
            "filtered_candidates": [],
            "ranked_candidates": [],
            "derived_from": "world_watch",
        })
    return {"issue_date": "2026-04-20", "sections": sections}


def _make_test_config():
    return {
        "profile": {
            "id": "sophie",
            "name": "Sophie",
            "age_band": "4th-grade",
            "location": "Fremont, California",
            "cultural_context": [],
            "interests": {"active": ["gymnastics"]},
            "newsletter": {
                "active_sections": ["world_watch", "sophies_challenge"],
                "editorial": {},
            },
        },
        "sections": {
            "world_watch": {"title": "World Watch", "goal": "current events", "block_type": "story_list",
                            "content_rules": [], "source_preferences": [], "link_style": "link-green"},
            "sophies_challenge": {"title": "Weekly Challenge", "goal": "puzzle", "block_type": "challenge",
                                  "content_rules": [], "source_preferences": [], "link_style": "link-orange"},
        },
    }


def test_derived_section_receives_source_candidates_in_prompt():
    """sophies_challenge entry in the prompt packet must contain world_watch source_candidates."""
    world_watch_candidates = [
        {
            "title": f"Story {i}",
            "url": f"https://bbc.co.uk/{i}",
            "domain": "bbc.co.uk",
            "snippet": f"A long enough snippet about topic {i} for testing purposes yes.",
            "source": "BBC Newsround",
            "published_at": None,
            "query_source": None,
        }
        for i in range(3)
    ]
    packet = _make_research_packet_with_sections(world_watch_candidates)
    config = _make_test_config()

    prompt = content_stage.build_packet_synthesis_prompt(date(2026, 4, 20), 5, config, packet)

    # The prompt should contain source_candidates for sophies_challenge
    assert "source_candidates" in prompt
    # And not empty — world_watch content should be there
    assert "Story 0" in prompt or "Story 1" in prompt or "Story 2" in prompt


def test_derived_section_note_appears_in_prompt():
    """sophies_challenge packet entry should include the derivation note."""
    world_watch_candidates = [
        {
            "title": "Tariffs Explained for Kids",
            "url": "https://timeforkids.com/1",
            "domain": "timeforkids.com",
            "snippet": "Tariffs are taxes on things a country buys from other countries.",
            "source": "Time for Kids",
            "published_at": None,
            "query_source": None,
        }
    ]
    packet = _make_research_packet_with_sections(world_watch_candidates)
    config = _make_test_config()
    prompt = content_stage.build_packet_synthesis_prompt(date(2026, 4, 20), 5, config, packet)
    assert "derived_from" in prompt
    assert "world_watch" in prompt


def test_section_without_candidates_omitted_from_prompt():
    """A non-derived section with zero candidates is omitted from the packet in the prompt."""
    packet = _make_research_packet_with_sections([], include_challenge=False)
    config = _make_test_config()
    # world_watch has no candidates
    prompt = content_stage.build_packet_synthesis_prompt(date(2026, 4, 20), 5, config, packet)
    # world_watch section should not appear in section_packets since it has no candidates
    assert '"section_id": "world_watch"' not in prompt


# ---------------------------------------------------------------------------
# Ranker failure fallback
# ---------------------------------------------------------------------------

def _make_filtered_pool(section_id, candidates):
    return {
        "issue_date": "2026-04-20",
        "recent_headlines": [],
        "sections": [
            {
                "section_id": section_id,
                "queries": ["test"],
                "ranking_profile": f"{section_id}_default",
                "raw_candidates": [],
                "filtered_candidates": candidates,
                "ranked_candidates": [],
                "derived_from": None,
            }
        ],
    }


def _long_snippet(n):
    return f"This is a sufficiently long snippet number {n} about an interesting topic suitable for children."


def test_model_ranker_falls_back_to_filtered_when_model_returns_empty(tmp_path):
    """When _run_model_ranker returns [], fallback to filtered ordering."""
    candidates = [
        {"title": f"Story {i}", "url": f"https://example.com/{i}", "domain": "example.com",
         "snippet": _long_snippet(i), "source": "Example", "published_at": None, "query_source": None}
        for i in range(4)
    ]
    pool = _make_filtered_pool("world_watch", candidates)
    config = {
        "profile": {"name": "Sophie", "age_band": "4th-grade", "interests": {"active": []}},
        "research": {"ranking": {"defaults": {"max_ranked": 3}, "sections": {}}},
    }

    from providers import llm_providers as hosted_llm_provider

    with patch.object(hosted_llm_provider, "_run_model_ranker", return_value=[]):
        result = hosted_llm_provider.model_rank_candidates(pool, config, tmp_path)

    ranked = result["sections"][0]["ranked_candidates"]
    # Fallback: should get filtered candidates, not empty
    assert len(ranked) > 0
    assert len(ranked) <= 3  # capped at max_ranked
    # Should be tagged as fallback
    assert any("fallback" in r for reason in ranked for r in reason.get("reasons", []))


def test_model_ranker_fallback_preserves_filtered_order(tmp_path):
    """Fallback preserves the order from the prefilter stage (first N candidates)."""
    candidates = [
        {"title": f"Article {i}", "url": f"https://example.com/{i}", "domain": "example.com",
         "snippet": _long_snippet(i), "source": "Example", "published_at": None, "query_source": None}
        for i in range(6)
    ]
    pool = _make_filtered_pool("weird_but_true", candidates)
    config = {
        "profile": {"name": "Sophie", "age_band": "4th-grade", "interests": {"active": []}},
        "research": {"ranking": {"defaults": {"max_ranked": 3}, "sections": {}}},
    }

    from providers import llm_providers as hosted_llm_provider

    with patch.object(hosted_llm_provider, "_run_model_ranker", return_value=[]):
        result = hosted_llm_provider.model_rank_candidates(pool, config, tmp_path)

    ranked = result["sections"][0]["ranked_candidates"]
    assert [r["title"] for r in ranked] == ["Article 0", "Article 1", "Article 2"]


def test_model_ranker_prompt_includes_recent_headlines_and_distinctness_guidance():
    from providers import llm_providers as hosted_llm_provider

    candidates = [
        {"title": "Moon mission update", "url": "https://example.com/1", "domain": "example.com",
         "snippet": _long_snippet(1), "source": "Example", "published_at": "2026-04-20", "query_source": None}
    ]
    prompt = hosted_llm_provider._build_ranker_prompt(
        "world_watch",
        candidates,
        {"name": "Sophie", "age_band": "4th-grade", "interests": {"active": ["gymnastics"]}},
        3,
        ["NASA's Artemis II Crew Splashes Down", "Singapore's Hawker Centers Are a UNESCO World Treasure"],
    )

    assert "Recent issue headlines to avoid repeating too closely" in prompt
    assert "editorial distinctness" in prompt
    assert "not just the most obvious or generic headline" in prompt
    assert "Artemis II" in prompt


# ---------------------------------------------------------------------------
# Freshness scoring
# ---------------------------------------------------------------------------

def test_parse_date_iso():
    d = ranking_stage._parse_date("2026-04-18")
    assert d == date(2026, 4, 18)


def test_parse_date_brave_format():
    d = ranking_stage._parse_date("Apr 18, 2026")
    assert d == date(2026, 4, 18)


def test_parse_date_relative_days():
    d = ranking_stage._parse_date("3 days ago")
    expected = date.today() - __import__("datetime").timedelta(days=3)
    assert d == expected


def test_parse_date_unparseable_returns_none():
    assert ranking_stage._parse_date("some random text") is None
    assert ranking_stage._parse_date("") is None


def _base_score_cfg():
    return {
        "source_boost": 20,
        "freshness_boost": 20,
        "keyword_match_boost": 5,
        "geography_boost": 8,
        "kid_safe_boost": 10,
        "novelty_penalty": 30,
        "junk_penalty": 40,
        "min_score": 0,
        "max_ranked": 5,
        "keywords": [],
    }


def test_fresh_result_gets_boost():
    """A result published within the window gets the freshness boost."""
    import datetime
    recent_date = (date.today() - datetime.timedelta(days=3)).isoformat()
    cfg = {**_base_score_cfg(), "freshness_window_days": 7}
    c = research_stage.make_candidate(
        "Breaking News", url="https://bbc.co.uk/1", domain="bbc.co.uk",
        snippet="A sufficiently long snippet about breaking world news for young readers today.",
        published_at=recent_date,
    )
    _, reasons = ranking_stage._score_candidate(c, cfg, {"bbc.co.uk"}, [], {})
    assert any("fresh" in r for r in reasons)


def test_stale_result_gets_penalty():
    """A result outside the freshness window gets penalised, not boosted."""
    import datetime
    old_date = (date.today() - datetime.timedelta(days=60)).isoformat()
    cfg = {**_base_score_cfg(), "freshness_window_days": 7}
    c = research_stage.make_candidate(
        "Old Story", url="https://bbc.co.uk/2", domain="bbc.co.uk",
        snippet="A sufficiently long snippet about an old story that appeared many weeks ago.",
        published_at=old_date,
    )
    _, reasons = ranking_stage._score_candidate(c, cfg, set(), [], {})
    assert any("stale" in r for r in reasons)


def test_junk_penalty_applied_for_short_snippet():
    cfg = {**_base_score_cfg()}
    c = research_stage.make_candidate(
        "Some Article", url="https://example.com/1", domain="example.com",
        snippet="Too short.",
    )
    _, reasons = ranking_stage._score_candidate(c, cfg, set(), [], {})
    assert any("short snippet" in r for r in reasons)
