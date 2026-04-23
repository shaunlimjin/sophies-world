#!/usr/bin/env python3
"""Generate a Sophie's World newsletter issue."""

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install it with: pip3 install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

from content_stage import build_content_prompt, parse_content_output, run_content_provider
from content_stage import build_packet_synthesis_prompt, run_packet_synthesis_provider
from issue_schema import validate_issue_artifact, write_issue_artifact
from render_stage import load_template, render_issue_html

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
NEWSLETTERS_DIR = REPO_ROOT / "newsletters"

# Content provider constants (what generates final issue JSON)
CONTENT_PROVIDER_INTEGRATED = "hosted_integrated_search"  # Mode A: Claude with integrated search
CONTENT_PROVIDER_PACKET = "hosted_packet_synthesis"        # Mode B: Claude from pre-ranked packet

# Ranker provider constants (what ranks Brave candidates before synthesis)
RANKER_HEURISTIC = "heuristic_ranker"
RANKER_HOSTED_MODEL = "hosted_model_ranker"

VALID_CONTENT_PROVIDERS = (CONTENT_PROVIDER_INTEGRATED, CONTENT_PROVIDER_PACKET)
VALID_RANKERS = (RANKER_HEURISTIC, RANKER_HOSTED_MODEL)


def load_config(repo_root: Path, env: str = "prod", approach: Optional[str] = None) -> dict:
    from env_resolver import resolve_config_file

    child_path = resolve_config_file(repo_root, env, approach, "children/sophie.yaml")
    if not child_path.exists():
        print(f"Error: child config not found: {child_path}", file=sys.stderr)
        sys.exit(1)
    profile = yaml.safe_load(child_path.read_text(encoding="utf-8"))

    pipeline_path = resolve_config_file(repo_root, env, approach, "pipelines/default.yaml")
    if not pipeline_path.exists():
        print(f"Error: pipeline config not found: {pipeline_path}", file=sys.stderr)
        sys.exit(1)
    pipeline = yaml.safe_load(pipeline_path.read_text(encoding="utf-8"))

    active_sections = profile.get("newsletter", {}).get("active_sections", [])
    sections = {}
    for section_id in active_sections:
        section_path = resolve_config_file(repo_root, env, approach, f"sections/{section_id}.yaml")
        if not section_path.exists():
            print(f"Error: section config not found: {section_path}", file=sys.stderr)
            sys.exit(1)
        sections[section_id] = yaml.safe_load(section_path.read_text(encoding="utf-8"))

    theme_name = profile.get("newsletter", {}).get("theme", "default")
    theme_path = resolve_config_file(repo_root, env, approach, f"themes/{theme_name}.yaml")
    if not theme_path.exists():
        print(f"Error: theme config not found: {theme_path}", file=sys.stderr)
        sys.exit(1)
    theme = yaml.safe_load(theme_path.read_text(encoding="utf-8"))

    return {"profile": profile, "pipeline": pipeline, "sections": sections, "theme": theme}


def get_template_path(repo_root: Path, theme: dict) -> Path:
    template_rel = theme.get("template_path")
    if not template_rel:
        print("Error: theme config missing required field: template_path", file=sys.stderr)
        sys.exit(1)
    template_path = repo_root / template_rel
    if not template_path.exists():
        print(f"Error: template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)
    return template_path


def get_next_issue_number(newsletters_dir: Path) -> int:
    existing = list(newsletters_dir.glob("sophies-world-*.html"))
    return len(existing) + 1


def get_recent_headlines(newsletters_dir: Path, today: date) -> List[str]:
    today_name = f"sophies-world-{today.strftime('%Y-%m-%d')}.html"
    files = sorted(newsletters_dir.glob("sophies-world-*.html"))
    previous = [f for f in files if f.name != today_name]
    if not previous:
        return []
    content = previous[-1].read_text(encoding="utf-8")
    raw = re.findall(r"<h3[^>]*>(.*?)</h3>", content, re.DOTALL)
    return [re.sub(r"<[^>]+>", "", h).strip() for h in raw if h.strip()]


def get_output_path(newsletters_dir: Path, issue_date: date, suffix: Optional[str] = None) -> Path:
    filename = f"sophies-world-{issue_date.strftime('%Y-%m-%d')}"
    if suffix:
        filename += f"-{suffix}"
    filename += ".html"
    return newsletters_dir / filename


def check_output_exists(output_path: Path) -> bool:
    if output_path.exists():
        print(f"Output already exists, skipping: {output_path}")
        return True
    return False


def resolve_providers(config: dict, content_provider_override: Optional[str], ranker_override: Optional[str]) -> tuple:
    """Return (content_provider, ranker_provider) from config with optional CLI overrides."""
    pipeline_cfg = config.get("pipeline", {}).get("pipeline", {})
    content_provider = content_provider_override or pipeline_cfg.get("content_provider", CONTENT_PROVIDER_INTEGRATED)
    ranker_provider = ranker_override or pipeline_cfg.get("ranker_provider", RANKER_HEURISTIC)
    return content_provider, ranker_provider


def run_mode_a(today: date, issue_num: int, config: dict, recent_headlines: List[str], repo_root: Path) -> dict:
    """Mode A: hosted provider with integrated search (baseline path)."""
    from providers.model_providers import make_provider
    synthesis_provider_cfg = config.get("pipeline", {}).get("models", {}).get("synthesis")
    synthesis_provider = make_provider(synthesis_provider_cfg) if synthesis_provider_cfg else None

    print("Mode A: hosted provider with integrated search")
    prompt = build_content_prompt(today, issue_num, config, recent_headlines)

    if synthesis_provider is not None:
        raw_output = run_content_provider(
            prompt, repo_root,
            provider=synthesis_provider,
            allowed_tools="WebSearch,WebFetch",
            max_turns=10,
        )
    else:
        raw_output = run_content_provider(prompt, repo_root)

    issue = parse_content_output(raw_output, repo_root)
    validate_issue_artifact(issue)
    return issue


def run_mode_b(
    today: date,
    issue_num: int,
    config: dict,
    recent_headlines: List[str],
    repo_root: Path,
    ranker_provider: str,
    refresh_research: bool,
    run_tag: Optional[str] = None,
    artifacts_root: Optional[Path] = None,
) -> dict:
    """Mode B: deterministic retrieval + configurable ranking + hosted packet synthesis."""
    from providers.model_providers import make_provider
    synthesis_provider_cfg = config.get("pipeline", {}).get("models", {}).get("synthesis")
    synthesis_provider = make_provider(synthesis_provider_cfg) if synthesis_provider_cfg else None

    from research_stage import (
        build_research_plan, run_research,
        load_research_packet, save_research_packet,
        get_research_artifact_path, compute_research_config_hash,
    )
    from ranking_stage import prefilter_candidates, rank_candidates

    print(f"Mode B: deterministic retrieval + {ranker_provider} + hosted packet synthesis")

    artifact_path = get_research_artifact_path(repo_root, today, run_tag, artifacts_root)
    config_hash = compute_research_config_hash(config)

    needs_research = True
    if not refresh_research and artifact_path.exists():
        cached = load_research_packet(artifact_path)
        if cached.get("config_hash") == config_hash:
            print(f"Reusing cached research packet: {artifact_path}")
            packet = cached
            needs_research = False
        else:
            print(
                f"Research packet config hash mismatch — rerunning research "
                f"(cached={cached.get('config_hash', 'none')}, current={config_hash})"
            )

    if needs_research:
        print("Running Brave research stage...")
        plan = build_research_plan(today, config, recent_headlines)
        raw_candidates = run_research(plan, repo_root)
        filtered = prefilter_candidates(raw_candidates, config)
        packet = rank_candidates(filtered, config, ranker_provider, repo_root)
        packet["config_hash"] = config_hash
        save_research_packet(packet, artifact_path)
        print(f"Research packet saved: {artifact_path}")

    prompt = build_packet_synthesis_prompt(today, issue_num, config, packet)
    raw_output = run_packet_synthesis_provider(prompt, repo_root, provider=synthesis_provider)
    issue = parse_content_output(raw_output, repo_root)
    validate_issue_artifact(issue)
    return issue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Always regenerate; skip idempotency check")
    parser.add_argument("--env", choices=["prod", "staging"], default="prod", dest="env")
    parser.add_argument("--approach", default=None, help="Named approach (requires --env staging)")
    parser.add_argument(
        "--run-tag",
        default=None,
        help="Optional tag appended to HTML, issue artifact, and research packet filenames",
    )
    parser.add_argument(
        "--content-provider",
        choices=list(VALID_CONTENT_PROVIDERS),
        default=None,
        dest="content_provider",
        help="Override content provider (default: from config)",
    )
    parser.add_argument(
        "--ranker",
        choices=list(VALID_RANKERS),
        default=None,
        help="Override ranker provider for Mode B (default: from config)",
    )
    parser.add_argument(
        "--refresh-research",
        action="store_true",
        help="Re-run Brave retrieval even if a cached research packet exists",
    )
    args = parser.parse_args()

    if args.approach and args.env != "staging":
        parser.error("--approach requires --env staging")

    from env_resolver import get_artifacts_root, get_newsletters_dir

    env = args.env
    approach = args.approach
    artifacts_root = get_artifacts_root(REPO_ROOT, env, approach)
    newsletters_dir = get_newsletters_dir(REPO_ROOT, env, approach)

    # Legacy: prod + --test writes to newsletters/test/ (unchanged behavior)
    if env == "prod" and args.test:
        newsletters_dir = REPO_ROOT / "newsletters" / "test"

    newsletters_dir.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    today = date.today()
    # Issue number and recent headlines always reference prod newsletters
    issue_num = get_next_issue_number(NEWSLETTERS_DIR)
    recent_headlines = get_recent_headlines(NEWSLETTERS_DIR, today)

    output_path = get_output_path(newsletters_dir, today, args.run_tag)

    if not args.test and check_output_exists(output_path):
        return

    print(f"Environment: {env}" + (f" / approach: {approach}" if approach else ""))
    config = load_config(REPO_ROOT, env, approach)
    template_path = get_template_path(REPO_ROOT, config["theme"])
    template_html = load_template(template_path)

    content_provider, ranker_provider = resolve_providers(config, args.content_provider, args.ranker)
    print(f"Generating Issue #{issue_num} (content_provider={content_provider}, ranker={ranker_provider})...")

    if content_provider == CONTENT_PROVIDER_INTEGRATED:
        issue = run_mode_a(today, issue_num, config, recent_headlines, REPO_ROOT)
    elif content_provider == CONTENT_PROVIDER_PACKET:
        issue = run_mode_b(
            today, issue_num, config, recent_headlines, REPO_ROOT,
            ranker_provider, args.refresh_research, args.run_tag,
            artifacts_root=artifacts_root,
        )
    else:
        print(f"Error: unknown content_provider '{content_provider}'", file=sys.stderr)
        sys.exit(1)

    artifact_path = write_issue_artifact(REPO_ROOT, issue, args.run_tag, artifacts_root)

    print(f"Rendering HTML from artifact: {artifact_path}")
    html = render_issue_html(template_html, issue)
    output_path.write_text(html, encoding="utf-8")
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
