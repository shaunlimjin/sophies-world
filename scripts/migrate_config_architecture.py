#!/usr/bin/env python3
"""One-off migration helper: split monolithic config into new structure.

Reads:
    config/sections.yaml      → config/sections/<section>.yaml (per section)
    config/research.yaml      → config/sections/<section>.yaml (per-section keys only)
                             + config/pipelines/default.yaml (global keys)

Writes:
    config/sections/weird_but_true.yaml
    config/sections/world_watch.yaml
    config/sections/singapore_spotlight.yaml
    config/sections/usa_corner.yaml
    config/sections/gymnastics_corner.yaml
    config/sections/kpop_corner.yaml
    config/sections/money_moves.yaml
    config/sections/sophies_challenge.yaml
    config/pipelines/default.yaml

Run from repo root:
    python3 scripts/migrate_config_architecture.py

This is a one-off migration tool. It does not need a maintenance tail.
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required.", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
SECTIONS_SRC = REPO_ROOT / "config" / "sections.yaml"
RESEARCH_SRC = REPO_ROOT / "config" / "research.yaml"
SECTIONS_DST_DIR = REPO_ROOT / "config" / "sections"
PIPELINES_DST = REPO_ROOT / "config" / "pipelines" / "default.yaml"


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def build_section_file(section_id: str, display_cfg: dict, research_cfg: dict) -> dict:
    """Merge display (from sections.yaml) + research/ranking (from research.yaml) into one section file."""
    section_research = research_cfg.get("sections", {}).get(section_id, {})
    section_ranking = research_cfg.get("ranking", {}).get("sections", {}).get(section_id, {})

    # Build research block
    research_block = {}
    if "queries" in section_research:
        research_block["queries"] = section_research["queries"]
    if "freshness" in section_research:
        research_block["freshness"] = section_research["freshness"]
    if "count" in section_research:
        research_block["count"] = section_research["count"]

    # Build ranking block (only non-default values)
    ranking_block = {}
    for key in ("freshness_boost", "keyword_match_boost", "geography_boost",
                "kid_safe_boost", "novelty_penalty", "junk_penalty", "min_score", "max_ranked"):
        if key in section_ranking:
            ranking_block[key] = section_ranking[key]
    if "keywords" in section_ranking:
        ranking_block["keywords"] = section_ranking["keywords"]

    result = {
        "id": section_id,
        "display": {
            "title": display_cfg.get("title"),
            "block_type": display_cfg.get("block_type"),
            "link_style": display_cfg.get("link_style"),
        },
        "editorial": {
            "goal": display_cfg.get("goal"),
            "content_rules": display_cfg.get("content_rules", []),
            "source_preferences": display_cfg.get("source_preferences", []),
        },
    }
    if research_block:
        result["research"] = research_block
    if ranking_block:
        result["ranking"] = ranking_block

    return result


def build_pipeline_config(sophie_yaml: dict, research_cfg: dict) -> dict:
    """Extract generation block + global domains/ranking defaults into pipeline config."""
    generation = sophie_yaml.get("newsletter", {}).get("generation", {})

    # Global domains from research.yaml
    global_domains = research_cfg.get("domains", {})

    # Global ranking defaults
    global_ranking = research_cfg.get("ranking", {}).get("defaults", {})

    # Novelty settings
    novelty = research_cfg.get("novelty", {})

    result = {
        "pipeline": {
            "research_provider": generation.get("research_provider"),
            "ranker_provider": generation.get("ranker_provider"),
            "content_provider": generation.get("content_provider"),
            "render_provider": generation.get("render_provider"),
            "fallback_content_provider": generation.get("fallback_content_provider"),
        },
        "models": {
            "synthesis": generation.get("providers", {}).get("synthesis"),
            "ranking": generation.get("providers", {}).get("ranking"),
        },
    }

    if global_domains:
        result["global_domains"] = global_domains
    if global_ranking:
        result["global_ranking_defaults"] = global_ranking
    if novelty:
        result["novelty"] = novelty

    return result


def main():
    if not SECTIONS_SRC.exists():
        print(f"Error: {SECTIONS_SRC} not found", file=sys.stderr)
        sys.exit(1)
    if not RESEARCH_SRC.exists():
        print(f"Error: {RESEARCH_SRC} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {SECTIONS_SRC}")
    sections_src = load_yaml(SECTIONS_SRC)

    print(f"Reading {RESEARCH_SRC}")
    research_src = load_yaml(RESEARCH_SRC)

    # Load sophie.yaml to get generation block
    sophie_path = REPO_ROOT / "config" / "children" / "sophie.yaml"
    if not sophie_path.exists():
        print(f"Error: {sophie_path} not found", file=sys.stderr)
        sys.exit(1)
    sophie_yaml = load_yaml(sophie_path)

    sections_catalog = sections_src.get("sections", {})

    # Migrate each section
    for section_id, display_cfg in sections_catalog.items():
        dst = SECTIONS_DST_DIR / f"{section_id}.yaml"
        section_file = build_section_file(section_id, display_cfg, research_src)
        print(f"  Writing {dst}")
        save_yaml(dst, section_file)

    # Write pipeline config
    PIPELINES_DST.parent.mkdir(parents=True, exist_ok=True)
    pipeline_cfg = build_pipeline_config(sophie_yaml, research_src)
    print(f"Writing {PIPELINES_DST}")
    save_yaml(PIPELINES_DST, pipeline_cfg)

    print("\nMigration complete.")
    print(f"  {len(sections_catalog)} section files → {SECTIONS_DST_DIR}/")
    print(f"  Pipeline config → {PIPELINES_DST}")


if __name__ == "__main__":
    main()