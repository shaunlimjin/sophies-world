# Staging/Production Environments + Approaches Implementation Plan

> **Status: Implemented** (merged PR #2, commit `f7b7c0d`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--env [prod|staging]` and `--approach <name>` flags to `generate.py`, backed by a layered overlay resolver, env-aware artifact paths, and a `promote.py` tool — giving a safe staging ring for config/script iteration without touching prod.

**Architecture:** A new `env_resolver.py` module handles all path resolution logic (config overlay: approach → staging → prod; output dir routing) and is imported by `generate.py`. `issue_schema.py` and `research_stage.py` gain an optional `artifacts_root` param so callers can redirect writes. `promote.py` diffs and copies files from one layer to the next with confirmation and auto-commit.

**Tech Stack:** Python 3, pathlib, shutil, subprocess (for git commit in promote.py), pytest

---

## Scope Note

Historical note: when this plan was written, the later config-architecture refactor was still out of scope. That refactor has since landed in PR #3 (`77681e6`) for the prod baseline. Some staging/approach snapshots may still reflect the older monolithic config shape until they are migrated.

---

## File Map

**New files:**
- `scripts/env_resolver.py` — overlay config resolution + output dir computation
- `scripts/promote.py` — approach → staging or staging → prod promotion
- `tests/test_env_resolver.py` — unit tests for env_resolver
- `tests/test_promote.py` — unit tests for promote.py

**Modified files:**
- `scripts/issue_schema.py` — add optional `artifacts_root` param to artifact path helpers
- `scripts/research_stage.py` — add optional `artifacts_root` param to `get_research_artifact_path`
- `scripts/generate.py` — add `--env`/`--approach` flags, wire env_resolver, update output routing
- `tests/test_generate.py` — add tests for new CLI flags and routing
- `tests/test_research_pipeline.py` — add `artifacts_root` test for `get_research_artifact_path`

**Directories created (by scaffolding task):**
- `staging/scripts/` — optional staging script overrides (empty to start)
- `staging/config/` — populated with a copy of `config/` as the staging starting point
- `staging/approaches/` — future named approach snapshots
- `newsletters/staging/` — staging HTML output

---

## Task 1: Directory scaffolding

**Files:**
- Create dirs: `staging/scripts/`, `staging/config/children/`, `staging/config/themes/`, `staging/approaches/`, `newsletters/staging/`
- Copy: `config/` → `staging/config/` (starting point for staging overrides)

- [ ] **Step 1: Create directories and copy prod config into staging**

```bash
cd /path/to/sophies-world   # replace with actual repo root

mkdir -p staging/scripts staging/approaches newsletters/staging
mkdir -p staging/config/children staging/config/themes

# Copy prod config as staging starting point
cp config/children/sophie.yaml staging/config/children/sophie.yaml
cp config/sections.yaml staging/config/sections.yaml
cp config/research.yaml staging/config/research.yaml
cp config/themes/default.yaml staging/config/themes/default.yaml
```

- [ ] **Step 2: Verify structure exists**

```bash
find staging/ -type f
# Expected:
# staging/config/children/sophie.yaml
# staging/config/sections.yaml
# staging/config/research.yaml
# staging/config/themes/default.yaml
```

- [ ] **Step 3: Add staging/.gitkeep files so empty dirs are tracked**

```bash
touch staging/scripts/.gitkeep staging/approaches/.gitkeep newsletters/staging/.gitkeep
```

- [ ] **Step 4: Commit**

```bash
git add staging/ newsletters/staging/
git commit -m "chore: scaffold staging directory structure"
```

---

## Task 2: `scripts/env_resolver.py` — overlay resolver and output dirs

**Files:**
- Create: `scripts/env_resolver.py`
- Create: `tests/test_env_resolver.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_env_resolver.py`:

```python
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import env_resolver


def test_get_artifacts_root_prod(tmp_path):
    result = env_resolver.get_artifacts_root(tmp_path, "prod")
    assert result == tmp_path / "artifacts"


def test_get_artifacts_root_staging(tmp_path):
    result = env_resolver.get_artifacts_root(tmp_path, "staging")
    assert result == tmp_path / "artifacts" / "staging"


def test_get_artifacts_root_approach(tmp_path):
    result = env_resolver.get_artifacts_root(tmp_path, "staging", "approach-b2-v2")
    assert result == tmp_path / "artifacts" / "approaches" / "approach-b2-v2"


def test_get_newsletters_dir_prod(tmp_path):
    result = env_resolver.get_newsletters_dir(tmp_path, "prod")
    assert result == tmp_path / "newsletters"


def test_get_newsletters_dir_staging(tmp_path):
    result = env_resolver.get_newsletters_dir(tmp_path, "staging")
    assert result == tmp_path / "newsletters" / "staging"


def test_get_newsletters_dir_approach(tmp_path):
    result = env_resolver.get_newsletters_dir(tmp_path, "staging", "approach-b2-v2")
    assert result == tmp_path / "artifacts" / "approaches" / "approach-b2-v2" / "newsletters"


def test_resolve_config_file_prod_returns_prod_path(tmp_path):
    # Create the prod config file
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("x: 1")

    result = env_resolver.resolve_config_file(tmp_path, "prod", None, "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"


def test_resolve_config_file_staging_no_override_falls_back_to_prod(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("x: 1")
    # staging/config does NOT have research.yaml

    result = env_resolver.resolve_config_file(tmp_path, "staging", None, "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"


def test_resolve_config_file_staging_uses_staging_override(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")

    result = env_resolver.resolve_config_file(tmp_path, "staging", None, "research.yaml")
    assert result == tmp_path / "staging" / "config" / "research.yaml"


def test_resolve_config_file_approach_prefers_approach_override(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")
    approach_dir = tmp_path / "staging" / "approaches" / "approach-b2-v2" / "config"
    approach_dir.mkdir(parents=True)
    (approach_dir / "research.yaml").write_text("approach: true")

    result = env_resolver.resolve_config_file(tmp_path, "staging", "approach-b2-v2", "research.yaml")
    assert result == approach_dir / "research.yaml"


def test_resolve_config_file_approach_falls_back_to_staging(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")
    # approach dir exists but does NOT have research.yaml
    approach_dir = tmp_path / "staging" / "approaches" / "approach-b2-v2" / "config"
    approach_dir.mkdir(parents=True)

    result = env_resolver.resolve_config_file(tmp_path, "staging", "approach-b2-v2", "research.yaml")
    assert result == tmp_path / "staging" / "config" / "research.yaml"


def test_resolve_config_file_approach_falls_back_to_prod(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    # neither staging nor approach override exists

    result = env_resolver.resolve_config_file(tmp_path, "staging", "approach-b2-v2", "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"


def test_resolve_config_file_prod_ignores_staging_overrides(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "research.yaml").write_text("prod: true")
    (tmp_path / "staging" / "config").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "research.yaml").write_text("staging: true")

    result = env_resolver.resolve_config_file(tmp_path, "prod", None, "research.yaml")
    assert result == tmp_path / "config" / "research.yaml"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/sophies-world
python3 -m pytest tests/test_env_resolver.py -v
```

Expected: `ModuleNotFoundError: No module named 'env_resolver'` (or similar)

- [ ] **Step 3: Create `scripts/env_resolver.py`**

```python
#!/usr/bin/env python3
"""Overlay resolution and output directory routing for prod/staging/approach environments."""

from pathlib import Path
from typing import Optional

ENV_PROD = "prod"
ENV_STAGING = "staging"


def get_artifacts_root(repo_root: Path, env: str, approach: Optional[str] = None) -> Path:
    if approach:
        return repo_root / "artifacts" / "approaches" / approach
    if env == ENV_STAGING:
        return repo_root / "artifacts" / "staging"
    return repo_root / "artifacts"


def get_newsletters_dir(repo_root: Path, env: str, approach: Optional[str] = None) -> Path:
    if approach:
        return repo_root / "artifacts" / "approaches" / approach / "newsletters"
    if env == ENV_STAGING:
        return repo_root / "newsletters" / "staging"
    return repo_root / "newsletters"


def resolve_config_file(
    repo_root: Path, env: str, approach: Optional[str], relative: str
) -> Path:
    """Return the config file path using overlay resolution: approach > staging > prod.

    For prod env, always returns the prod baseline. For staging/approach envs,
    checks each layer in order and returns the first existing file. Falls back
    to the prod baseline path (even if it doesn't exist — the caller handles missing files).
    """
    prod_path = repo_root / "config" / relative

    if env == ENV_PROD:
        print(f"  [config] {relative} → config/{relative}")
        return prod_path

    candidates: list[tuple[str, Path]] = []
    if approach:
        candidates.append((
            f"staging/approaches/{approach}/config/{relative}",
            repo_root / "staging" / "approaches" / approach / "config" / relative,
        ))
    candidates.append((
        f"staging/config/{relative}",
        repo_root / "staging" / "config" / relative,
    ))

    for label, path in candidates:
        if path.exists():
            print(f"  [config] {relative} → {label}")
            return path

    print(f"  [config] {relative} → config/{relative} (prod baseline fallback)")
    return prod_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_env_resolver.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/env_resolver.py tests/test_env_resolver.py
git commit -m "feat: add env_resolver for overlay config resolution and output dir routing"
```

---

## Task 3: Update `issue_schema.py` — env-aware artifact paths

**Files:**
- Modify: `scripts/issue_schema.py`
- Modify: `tests/test_generate.py` (add new artifact path tests)

- [ ] **Step 1: Write failing tests — add to `tests/test_generate.py`**

Add these tests at the end of `tests/test_generate.py`:

```python
def test_issue_artifact_path_staging(tmp_path):
    artifacts_root = tmp_path / "artifacts" / "staging"
    result = issue_schema.get_issue_artifact_path(tmp_path, "sophie", "2026-04-23", artifacts_root=artifacts_root)
    assert result == artifacts_root / "issues" / "sophie-2026-04-23.json"


def test_issue_artifact_path_approach(tmp_path):
    artifacts_root = tmp_path / "artifacts" / "approaches" / "approach-b1"
    result = issue_schema.get_issue_artifact_path(tmp_path, "sophie", "2026-04-23", artifacts_root=artifacts_root)
    assert result == artifacts_root / "issues" / "sophie-2026-04-23.json"


def test_write_issue_artifact_staging(tmp_path):
    issue = {
        "issue_date": "2026-04-23",
        "issue_number": 5,
        "child_id": "sophie",
        "theme_id": "default",
        "editorial": {},
        "child_name": "Sophie",
        "greeting_text": "Hello!",
        "sections": [{"id": "weird_but_true", "title": "A", "render_title": "A", "block_type": "fact_list", "items": [{"title": "x", "body": "y"}], "links": [], "link_style": "link-purple"}],
        "footer": {"issue_number": 5, "issue_date_display": "April 23, 2026", "tagline": "x", "location_line": "y"}
    }
    artifacts_root = tmp_path / "artifacts" / "staging"
    out_path = issue_schema.write_issue_artifact(tmp_path, issue, artifacts_root=artifacts_root)
    assert out_path == artifacts_root / "issues" / "sophie-2026-04-23.json"
    assert out_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_generate.py::test_issue_artifact_path_staging tests/test_generate.py::test_issue_artifact_path_approach tests/test_generate.py::test_write_issue_artifact_staging -v
```

Expected: FAIL with `TypeError: unexpected keyword argument 'artifacts_root'`

- [ ] **Step 3: Update `scripts/issue_schema.py`**

Replace the current `get_issue_artifacts_dir`, `get_issue_artifact_path`, and `write_issue_artifact` functions:

```python
def get_issue_artifacts_dir(repo_root: Path, artifacts_root: Optional[Path] = None) -> Path:
    root = artifacts_root if artifacts_root is not None else repo_root / ARTIFACTS_DIRNAME
    return root / ISSUES_DIRNAME


def get_issue_artifact_path(
    repo_root: Path,
    child_id: str,
    issue_date: str,
    run_tag: Optional[str] = None,
    artifacts_root: Optional[Path] = None,
) -> Path:
    filename = f"{child_id}-{issue_date}"
    if run_tag:
        filename += f"-{run_tag}"
    filename += ".json"
    return get_issue_artifacts_dir(repo_root, artifacts_root) / filename


def write_issue_artifact(
    repo_root: Path,
    issue: Dict[str, Any],
    run_tag: Optional[str] = None,
    artifacts_root: Optional[Path] = None,
) -> Path:
    child_id = issue.get("child_id")
    issue_date = issue.get("issue_date")
    if not child_id or not issue_date:
        raise ValueError("issue artifact requires child_id and issue_date")
    out_dir = get_issue_artifacts_dir(repo_root, artifacts_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = get_issue_artifact_path(repo_root, child_id, issue_date, run_tag, artifacts_root)
    out_path.write_text(json.dumps(issue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path
```

Also add `Optional` to the imports at the top: `from typing import Any, Dict, Optional`

- [ ] **Step 4: Run all tests to verify new tests pass and nothing broke**

```bash
python3 -m pytest tests/test_generate.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/issue_schema.py tests/test_generate.py
git commit -m "feat: add artifacts_root param to issue_schema artifact path helpers"
```

---

## Task 4: Update `research_stage.py` — env-aware research artifact paths

**Files:**
- Modify: `scripts/research_stage.py`
- Modify: `tests/test_research_pipeline.py` (add new test)

- [ ] **Step 1: Write failing test — add to `tests/test_research_pipeline.py`**

```python
def test_get_research_artifact_path_with_artifacts_root(tmp_path):
    artifacts_root = tmp_path / "artifacts" / "staging"
    path = research_stage.get_research_artifact_path(
        tmp_path, date(2026, 4, 20), artifacts_root=artifacts_root
    )
    assert path == artifacts_root / "research" / "sophie-2026-04-20.json"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_research_pipeline.py::test_get_research_artifact_path_with_artifacts_root -v
```

Expected: FAIL with `TypeError: unexpected keyword argument 'artifacts_root'`

- [ ] **Step 3: Update `get_research_artifact_path` in `scripts/research_stage.py`**

Find the current `get_research_artifact_path` function (line ~266) and replace it:

```python
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
```

- [ ] **Step 4: Run tests to verify new test passes and existing tests still pass**

```bash
python3 -m pytest tests/test_research_pipeline.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/research_stage.py tests/test_research_pipeline.py
git commit -m "feat: add artifacts_root param to get_research_artifact_path"
```

---

## Task 5: Update `generate.py` — `--env`/`--approach` flags and output routing

**Files:**
- Modify: `scripts/generate.py`
- Modify: `tests/test_generate.py` (add routing and validation tests)

- [ ] **Step 1: Write failing tests — add to `tests/test_generate.py`**

Add these tests at the end of `tests/test_generate.py`:

```python
def test_load_config_with_staging_overlay(tmp_path):
    """Staging config overlay takes precedence over prod."""
    # Set up prod config
    make_config(tmp_path, VALID_SOPHIE_YAML)
    # Set up staging config with a different reading level in sophie.yaml
    staging_sophie = VALID_SOPHIE_YAML.replace("4th grade", "5th grade")
    (tmp_path / "staging" / "config" / "children").mkdir(parents=True)
    (tmp_path / "staging" / "config" / "children" / "sophie.yaml").write_text(staging_sophie)
    # Staging sections.yaml not present — falls back to prod

    config = generate.load_config(tmp_path, env="staging")
    editorial = config["profile"]["newsletter"]["editorial"]
    assert editorial["reading_level"] == "5th grade"
    # sections still loaded from prod baseline (no staging override)
    assert "weird_but_true" in config["sections"]


def test_load_config_default_env_is_prod(tmp_path):
    make_config(tmp_path, VALID_SOPHIE_YAML)
    config = generate.load_config(tmp_path)  # no env arg
    assert config["profile"]["name"] == "Sophie"
```

- [ ] **Step 2: Run failing tests**

```bash
python3 -m pytest tests/test_generate.py::test_load_config_with_staging_overlay tests/test_generate.py::test_load_config_default_env_is_prod -v
```

Expected: `test_load_config_default_env_is_prod` PASSES (load_config already works), `test_load_config_with_staging_overlay` FAILS with no overlay support yet.

- [ ] **Step 3: Update `load_config` in `scripts/generate.py` to use env_resolver**

Replace the `load_config` function:

```python
def load_config(repo_root: Path, env: str = "prod", approach: Optional[str] = None) -> dict:
    from env_resolver import resolve_config_file

    child_path = resolve_config_file(repo_root, env, approach, "children/sophie.yaml")
    if not child_path.exists():
        print(f"Error: child config not found: {child_path}", file=sys.stderr)
        sys.exit(1)
    profile = yaml.safe_load(child_path.read_text(encoding="utf-8"))

    sections_path = resolve_config_file(repo_root, env, approach, "sections.yaml")
    if not sections_path.exists():
        print(f"Error: sections config not found: {sections_path}", file=sys.stderr)
        sys.exit(1)
    sections_data = yaml.safe_load(sections_path.read_text(encoding="utf-8"))
    sections = sections_data.get("sections", {})

    theme_name = profile.get("newsletter", {}).get("theme", "default")
    theme_path = resolve_config_file(repo_root, env, approach, f"themes/{theme_name}.yaml")
    if not theme_path.exists():
        print(f"Error: theme config not found: {theme_path}", file=sys.stderr)
        sys.exit(1)
    theme = yaml.safe_load(theme_path.read_text(encoding="utf-8"))

    active_sections = profile.get("newsletter", {}).get("active_sections", [])
    missing = [s for s in active_sections if s not in sections]
    if missing:
        print(f"Error: active_sections reference unknown section IDs: {missing}", file=sys.stderr)
        sys.exit(1)

    research_config = _load_research_config_resolved(repo_root, env, approach)

    return {"profile": profile, "sections": sections, "theme": theme, "research": research_config}
```

Add a new helper beneath `_load_research_config`:

```python
def _load_research_config_resolved(repo_root: Path, env: str = "prod", approach: Optional[str] = None) -> dict:
    from env_resolver import resolve_config_file
    research_path = resolve_config_file(repo_root, env, approach, "research.yaml")
    if not research_path.exists():
        return {}
    return yaml.safe_load(research_path.read_text(encoding="utf-8")) or {}
```

Also add `Optional` to the imports: `from typing import List, Optional`

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_generate.py::test_load_config_with_staging_overlay tests/test_generate.py::test_load_config_default_env_is_prod -v
```

Expected: both PASS

- [ ] **Step 5: Update `run_mode_b` to accept and pass `artifacts_root`**

Replace the `run_mode_b` function signature and its internal `get_research_artifact_path` call:

```python
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
    raw_output = run_packet_synthesis_provider(prompt, repo_root)
    issue = parse_content_output(raw_output, repo_root)
    validate_issue_artifact(issue)
    return issue
```

- [ ] **Step 6: Update `main()` in `scripts/generate.py`**

Replace the `main()` function:

```python
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
    )
    parser.add_argument(
        "--ranker",
        choices=list(VALID_RANKERS),
        default=None,
    )
    parser.add_argument(
        "--refresh-research",
        action="store_true",
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
```

- [ ] **Step 7: Run full test suite to confirm nothing broke**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 8: Smoke-test the new flag parses correctly (no network needed)**

```bash
python3 scripts/generate.py --help
# Verify --env and --approach appear in the output

python3 scripts/generate.py --approach approach-b1 2>&1 | grep "error"
# Expected: error: --approach requires --env staging
```

- [ ] **Step 9: Commit**

```bash
git add scripts/generate.py tests/test_generate.py
git commit -m "feat: add --env and --approach flags to generate.py with overlay config and output routing"
```

---

## Task 6: `scripts/promote.py` — approach → staging or staging → prod

**Files:**
- Create: `scripts/promote.py`
- Create: `tests/test_promote.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_promote.py`:

```python
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import promote


def test_validate_promotion_approach_to_prod_raises(capsys):
    with pytest.raises(SystemExit):
        promote.validate_promotion("approach-b2-v2", "prod")
    captured = capsys.readouterr()
    assert "directly to prod" in captured.err


def test_validate_promotion_approach_to_staging_ok():
    promote.validate_promotion("approach-b2-v2", "staging")  # should not raise


def test_validate_promotion_staging_to_prod_ok():
    promote.validate_promotion("staging", "prod")  # should not raise


def test_get_source_dir_staging(tmp_path):
    result = promote.get_source_dir(tmp_path, "staging")
    assert result == tmp_path / "staging"


def test_get_source_dir_approach(tmp_path):
    result = promote.get_source_dir(tmp_path, "approach-b2-v2")
    assert result == tmp_path / "staging" / "approaches" / "approach-b2-v2"


def test_get_dest_dir_staging(tmp_path):
    result = promote.get_dest_dir(tmp_path, "staging")
    assert result == tmp_path / "staging"


def test_get_dest_dir_prod(tmp_path):
    result = promote.get_dest_dir(tmp_path, "prod")
    assert result == tmp_path


def test_compute_diff_detects_new_file(tmp_path):
    src = tmp_path / "staging" / "approaches" / "approach-b1"
    (src / "config").mkdir(parents=True)
    (src / "config" / "research.yaml").write_text("new: true")

    dest = tmp_path  # prod root — config/research.yaml doesn't exist yet
    (dest / "config").mkdir(parents=True)

    changes = promote.compute_diff(src, dest)
    assert len(changes) == 1
    action, src_path, dest_path = changes[0]
    assert action == "add"
    assert dest_path == dest / "config" / "research.yaml"


def test_compute_diff_detects_modified_file(tmp_path):
    src = tmp_path / "staging" / "approaches" / "approach-b1"
    (src / "config").mkdir(parents=True)
    (src / "config" / "research.yaml").write_text("new: true")

    dest = tmp_path
    (dest / "config").mkdir(parents=True)
    (dest / "config" / "research.yaml").write_text("old: true")

    changes = promote.compute_diff(src, dest)
    assert len(changes) == 1
    assert changes[0][0] == "modify"


def test_compute_diff_no_changes_when_identical(tmp_path):
    src = tmp_path / "staging" / "approaches" / "approach-b1"
    (src / "config").mkdir(parents=True)
    (src / "config" / "research.yaml").write_text("same: true")

    dest = tmp_path
    (dest / "config").mkdir(parents=True)
    (dest / "config" / "research.yaml").write_text("same: true")

    changes = promote.compute_diff(src, dest)
    assert changes == []


def test_apply_promotion_copies_files(tmp_path):
    src_file = tmp_path / "src" / "config" / "research.yaml"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("new: true")
    dest_file = tmp_path / "dest" / "config" / "research.yaml"

    promote.apply_promotion([("add", src_file, dest_file)])
    assert dest_file.exists()
    assert dest_file.read_text() == "new: true"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_promote.py -v
```

Expected: `ModuleNotFoundError: No module named 'promote'`

- [ ] **Step 3: Create `scripts/promote.py`**

```python
#!/usr/bin/env python3
"""Promote an approach to staging, or staging to prod.

Usage:
    python3 scripts/promote.py --from approach-b2-v2 --to staging
    python3 scripts/promote.py --from staging --to prod
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).parent.parent


def validate_promotion(source: str, dest: str) -> None:
    if source != "staging" and dest == "prod":
        print(
            f"Error: cannot promote approach '{source}' directly to prod. "
            "Promote to staging first with --to staging.",
            file=sys.stderr,
        )
        sys.exit(1)


def get_source_dir(repo_root: Path, source: str) -> Path:
    if source == "staging":
        return repo_root / "staging"
    return repo_root / "staging" / "approaches" / source


def get_dest_dir(repo_root: Path, dest: str) -> Path:
    if dest == "prod":
        return repo_root
    return repo_root / "staging"


def compute_diff(source_dir: Path, dest_dir: Path) -> List[Tuple[str, Path, Path]]:
    """Return (action, src_path, dest_path) for files that differ between source and dest.

    Only inspects scripts/ and config/ subdirectories of source_dir.
    """
    changes: List[Tuple[str, Path, Path]] = []
    for subdir in ("scripts", "config"):
        src_sub = source_dir / subdir
        if not src_sub.exists():
            continue
        for src_file in sorted(src_sub.rglob("*")):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(source_dir)
            dest_file = dest_dir / rel
            if not dest_file.exists():
                changes.append(("add", src_file, dest_file))
            elif src_file.read_bytes() != dest_file.read_bytes():
                changes.append(("modify", src_file, dest_file))
    return changes


def apply_promotion(changes: List[Tuple[str, Path, Path]]) -> None:
    for _action, src, dest in changes:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def auto_commit(repo_root: Path, source: str, dest: str) -> None:
    msg = f"chore: promote {source} to {dest}"
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo_root, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote approach → staging or staging → prod")
    parser.add_argument("--from", dest="source", required=True, help="Source: 'staging' or an approach name")
    parser.add_argument("--to", dest="dest", required=True, choices=["staging", "prod"])
    args = parser.parse_args()

    validate_promotion(args.source, args.dest)

    source_dir = get_source_dir(REPO_ROOT, args.source)
    if not source_dir.exists():
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    dest_dir = get_dest_dir(REPO_ROOT, args.dest)
    changes = compute_diff(source_dir, dest_dir)

    if not changes:
        print("Nothing to promote — source and destination are already identical.")
        return

    print(f"\nPromotion: {args.source} → {args.dest}")
    for action, _src, dest_file in changes:
        print(f"  {action:6s}  {dest_file.relative_to(REPO_ROOT)}")

    answer = input("\nApply promotion? [y/N] ")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return

    apply_promotion(changes)
    auto_commit(REPO_ROOT, args.source, args.dest)
    print(f"\nDone. Promoted {args.source} → {args.dest}.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_promote.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/promote.py tests/test_promote.py
git commit -m "feat: add promote.py for approach → staging → prod promotion with diff and confirmation"
```

---

## Task 7: Phase 2 — create approach-b1 snapshot and verify end-to-end

**Files:**
- Create: `staging/approaches/approach-b1/` (snapshot of current prod baseline)

This is the Phase 2 verification from the spec: copy current prod baseline into a named approach and confirm `--env staging --approach approach-b1` routes outputs correctly.

- [ ] **Step 1: Snapshot current prod baseline as approach-b1**

```bash
cd /path/to/sophies-world

mkdir -p staging/approaches/approach-b1
cp -r scripts/ staging/approaches/approach-b1/scripts/
cp -r config/ staging/approaches/approach-b1/config/
```

- [ ] **Step 2: Verify the snapshot exists**

```bash
ls staging/approaches/approach-b1/scripts/
# Expected: generate.py  content_stage.py  research_stage.py  ... etc.

ls staging/approaches/approach-b1/config/
# Expected: children/  sections.yaml  research.yaml  themes/
```

- [ ] **Step 3: Run smoke test with approach-b1**

This verifies that `--env staging --approach approach-b1 --test` resolves config from the approach layer and writes output to `artifacts/approaches/approach-b1/newsletters/`.

```bash
python3 scripts/generate.py --env staging --approach approach-b1 --test
```

Expected output lines:
```
Environment: staging / approach: approach-b1
  [config] children/sophie.yaml → staging/approaches/approach-b1/config/children/sophie.yaml
  ...
Written: artifacts/approaches/approach-b1/newsletters/sophies-world-YYYY-MM-DD.html
```

Verify the file was written:

```bash
ls artifacts/approaches/approach-b1/newsletters/
# Expected: sophies-world-YYYY-MM-DD.html
```

- [ ] **Step 4: Run smoke test with plain staging**

```bash
python3 scripts/generate.py --env staging --test
```

Expected:
```
Environment: staging
  [config] children/sophie.yaml → staging/config/children/sophie.yaml
  ...
Written: newsletters/staging/sophies-world-YYYY-MM-DD.html
```

Verify:

```bash
ls newsletters/staging/
# Expected: sophies-world-YYYY-MM-DD.html
```

- [ ] **Step 5: Confirm prod behavior is unchanged**

```bash
python3 scripts/generate.py --test
```

Expected behavior: identical to before this plan — writes to `newsletters/test/`, logs `Environment: prod`.

- [ ] **Step 6: Commit**

```bash
git add staging/approaches/approach-b1/
git commit -m "feat: add approach-b1 snapshot as first named staging experiment"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered by |
|---|---|
| `--env [prod\|staging]` flag | Task 5 |
| `--approach <name>` flag | Task 5 |
| `--approach` without `--env staging` raises error | Task 5 Step 6 |
| Overlay resolution: approach > staging > prod | Task 2 |
| Logging of resolved config paths | Task 2 (print statements in resolve_config_file) |
| Output routing table (prod/staging/approach) | Task 2 + Task 5 |
| `promote.py` with diff summary and confirmation | Task 6 |
| `promote.py` rejects approach → prod directly | Task 6 |
| `promote.py` auto-commits | Task 6 |
| `staging/scripts/`, `staging/config/`, `staging/approaches/` dirs | Task 1 |
| `newsletters/staging/` dir | Task 1 |
| `artifacts/staging/`, `artifacts/approaches/<name>/` paths | Task 3 + Task 4 |
| Phase 1 verify: staging --test → newsletters/staging/ | Task 7 Step 4 |
| Phase 2: approach-b1 snapshot | Task 7 |
| Phase 2 verify: approach-b1 --test → artifacts/approaches/approach-b1/newsletters/ | Task 7 Step 3 |
| Prod behavior unchanged | Task 7 Step 5 |

### Placeholder scan

No TBD, TODO, "implement later", or "similar to Task N" patterns found. All code blocks are complete.

### Type consistency

- `artifacts_root: Optional[Path]` — used consistently in `issue_schema.py`, `research_stage.py`, `generate.py`
- `env: str`, `approach: Optional[str]` — consistent across `env_resolver.py`, `load_config`, `main()`
- `get_source_dir`, `get_dest_dir`, `compute_diff`, `apply_promotion`, `auto_commit` — all use `repo_root: Path` as first param, consistent with rest of codebase
