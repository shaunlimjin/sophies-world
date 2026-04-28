# Per-Stage Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the web UI pick a model preset (e.g. `claude-opus`, `minimax-m2`) per stage at run-creation time, separate from the existing strategy selection. Synthesis and ranking get model dropdowns; research/render do not (no model used).

**Architecture:** New `config/model_presets.yaml` registry maps preset names to `{provider, model, base_url?, api_key_env?}` dicts. A small `scripts/providers/model_presets.py` resolver dereferences names. `content_stage.py` and `ranking_stage.py` accept an optional `model_override` kwarg that takes priority over `pipelines/default.yaml.models.<stage>`. `web/api/routers/stages.py` merges per-run `settings.json` into trigger overrides so model picks reach the stage runner. The frontend adds filtered dropdowns and a `GET /api/model-presets` endpoint.

**Tech Stack:** Python 3 / pytest / FastAPI / TestClient / React + TypeScript / Vite.

**Reference spec:** `docs/superpowers/specs/2026-04-28-per-stage-model-selection-design.md`

---

## Task 1: Add preset registry file

**Files:**
- Create: `config/model_presets.yaml`

- [ ] **Step 1: Create the preset registry**

```yaml
# config/model_presets.yaml
# Named model presets. Each entry maps to {provider, model, base_url?, api_key_env?}
# accepted by scripts/providers/model_providers/make_provider().
#
# supports_tools: true means the preset works with tool-calling strategies
#   like hosted_integrated_search. Currently only Claude supports this.
# label is the human-readable name shown in the UI; falls back to the key.
presets:
  claude-opus:
    label: Claude Opus
    provider: claude
    model: opus
    supports_tools: true

  claude-sonnet:
    label: Claude Sonnet
    provider: claude
    model: sonnet
    supports_tools: true

  claude-haiku:
    label: Claude Haiku
    provider: claude
    model: haiku
    supports_tools: true

  minimax-m2:
    label: MiniMax M2
    provider: openai_compatible
    model: MiniMax-M2
    base_url: https://api.minimax.io/v1
    api_key_env: MINIMAX_API_KEY
    supports_tools: false

  local-lmstudio:
    label: Local (LM Studio)
    provider: openai_compatible
    model: local-model
    base_url: http://localhost:1234/v1
    supports_tools: false
```

- [ ] **Step 2: Commit**

```bash
git add config/model_presets.yaml
git commit -m "feat: add model preset registry"
```

---

## Task 2: Implement preset resolver module

**Files:**
- Create: `scripts/providers/model_presets.py`
- Create: `tests/providers/test_model_presets.py`

- [ ] **Step 1: Write the failing test file**

```python
# tests/providers/test_model_presets.py
"""Tests for the preset registry loader and resolver."""
import sys
from pathlib import Path
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from providers.model_presets import (
    load_presets,
    resolve_preset,
    resolve_model_config,
    STRATEGY_REQUIRES_TOOLS,
)


@pytest.fixture
def repo_with_presets(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "model_presets.yaml").write_text(yaml.safe_dump({
        "presets": {
            "claude-opus": {
                "label": "Claude Opus",
                "provider": "claude",
                "model": "opus",
                "supports_tools": True,
            },
            "minimax-m2": {
                "provider": "openai_compatible",
                "model": "MiniMax-M2",
                "base_url": "https://api.minimax.io/v1",
                "api_key_env": "MINIMAX_API_KEY",
                "supports_tools": False,
            },
        }
    }))
    return tmp_path


def test_load_presets_returns_dict(repo_with_presets):
    presets = load_presets(repo_with_presets)
    assert "claude-opus" in presets
    assert "minimax-m2" in presets


def test_load_presets_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_presets(tmp_path)


def test_resolve_preset_returns_provider_dict(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_preset("claude-opus", presets)
    assert resolved == {"provider": "claude", "model": "opus"}


def test_resolve_preset_includes_optional_fields(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_preset("minimax-m2", presets)
    assert resolved == {
        "provider": "openai_compatible",
        "model": "MiniMax-M2",
        "base_url": "https://api.minimax.io/v1",
        "api_key_env": "MINIMAX_API_KEY",
    }


def test_resolve_preset_strips_internal_fields(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_preset("claude-opus", presets)
    assert "supports_tools" not in resolved
    assert "label" not in resolved


def test_resolve_preset_unknown_name_raises(repo_with_presets):
    presets = load_presets(repo_with_presets)
    with pytest.raises(ValueError, match="not-a-preset"):
        resolve_preset("not-a-preset", presets)


def test_resolve_model_config_with_string_uses_preset(repo_with_presets):
    presets = load_presets(repo_with_presets)
    resolved = resolve_model_config("claude-opus", presets)
    assert resolved["provider"] == "claude"


def test_resolve_model_config_with_dict_passthrough(repo_with_presets):
    presets = load_presets(repo_with_presets)
    inline = {"provider": "claude", "model": "sonnet"}
    resolved = resolve_model_config(inline, presets)
    assert resolved == inline


def test_strategy_requires_tools_flags():
    assert STRATEGY_REQUIRES_TOOLS["hosted_integrated_search"] is True
    assert STRATEGY_REQUIRES_TOOLS["hosted_packet_synthesis"] is False
    assert STRATEGY_REQUIRES_TOOLS["hosted_model_ranker"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/providers/test_model_presets.py -v
```

Expected: ImportError / ModuleNotFoundError because `providers.model_presets` does not exist yet.

- [ ] **Step 3: Implement the resolver module**

```python
# scripts/providers/model_presets.py
"""Preset registry loader and resolver.

A preset is a named model configuration that maps to the {provider, model,
base_url?, api_key_env?} dict accepted by make_provider(). Presets live in
config/model_presets.yaml and are referenced by name from
config/pipelines/default.yaml and from per-run settings.json.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

# Internal-only fields that should not be passed to make_provider().
_INTERNAL_FIELDS = {"supports_tools", "label"}

# Strategy → does it need a tool-calling-capable model.
# Used by the API and UI to filter incompatible preset choices.
STRATEGY_REQUIRES_TOOLS: dict[str, bool] = {
    "hosted_integrated_search": True,
    "hosted_packet_synthesis": False,
    "hosted_model_ranker": False,
}


def load_presets(repo_root: Path) -> dict[str, dict]:
    """Read config/model_presets.yaml. Returns {name: preset_dict}.

    Raises:
        FileNotFoundError: if config/model_presets.yaml is missing.
    """
    path = Path(repo_root) / "config" / "model_presets.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Preset registry not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("presets", {}) or {}


def resolve_preset(name: str, presets: dict) -> dict:
    """Return {provider, model, base_url?, api_key_env?} for make_provider().

    Strips internal-only fields (supports_tools, label).

    Raises:
        ValueError: if preset name not found.
    """
    if name not in presets:
        raise ValueError(
            f"Unknown model preset: {name!r}. "
            f"Available: {sorted(presets.keys())}"
        )
    src = presets[name]
    return {k: v for k, v in src.items() if k not in _INTERNAL_FIELDS}


def resolve_model_config(value: Union[str, dict], presets: dict) -> dict:
    """Accept either a preset name (str) or an inline dict.

    String values are dereferenced via resolve_preset. Dict values are
    returned unchanged so existing inline-dict configs (e.g. in staging/
    overlays) keep working.
    """
    if isinstance(value, str):
        return resolve_preset(value, presets)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Expected preset name (str) or inline dict, got {type(value).__name__}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/test_model_presets.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_presets.py tests/providers/test_model_presets.py
git commit -m "feat: add preset registry loader and resolver"
```

---

## Task 3: Migrate `config/pipelines/default.yaml` to preset names

**Files:**
- Modify: `config/pipelines/default.yaml:7-13`

- [ ] **Step 1: Replace inline model dicts with preset names**

In `config/pipelines/default.yaml`, replace lines 7-13:

```yaml
# Was:
models:
  synthesis:
    provider: claude
    model: opus
  ranking:
    provider: claude
    model: sonnet

# Becomes:
models:
  synthesis: claude-opus
  ranking: claude-sonnet
```

- [ ] **Step 2: Verify no other prod code reads the inline shape**

```bash
grep -rn "pipeline.*models.*synthesis\|pipeline.*models.*ranking" scripts/ web/ 2>/dev/null
```

Expected: hits only in `scripts/content_stage.py:523` and `scripts/ranking_stage.py:90`. Both are updated in later tasks. No other readers.

- [ ] **Step 3: Commit**

```bash
git add config/pipelines/default.yaml
git commit -m "feat: migrate pipeline default models to preset names"
```

---

## Task 4: Wire resolver into `content_stage.py`

**Files:**
- Modify: `scripts/content_stage.py:509-525`
- Modify: `tests/test_content_stage.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_content_stage.py` (append at bottom):

```python
def test_run_synthesis_stage_uses_model_override(tmp_path, monkeypatch):
    """When model_override is set, that preset is resolved and used regardless of pipeline default."""
    import sys
    from datetime import date
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

    # Stub out the network-dependent parts of run_synthesis_stage.
    captured = {}

    def fake_make_provider(cfg, repo_root=None):
        captured["cfg"] = cfg
        class _P:
            name = cfg["provider"]
            def generate(self, prompt, **kw):
                return {"result": '{"date":"2026-04-28","sections":[]}'}
        return _P()

    def fake_run_packet(prompt, repo_root, provider=None):
        captured["called_with_provider"] = provider.name if provider else None
        return '{"date":"2026-04-28","sections":[]}'

    def fake_validate(issue): pass
    def fake_write(repo_root, issue, artifacts_root=None): return None
    def fake_parse(text, repo_root=None): return {"date": "2026-04-28", "sections": []}

    # Set up minimal repo with preset registry + ranked packet.
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "model_presets.yaml").write_text(
        "presets:\n"
        "  claude-opus:\n"
        "    provider: claude\n"
        "    model: opus\n"
        "    supports_tools: true\n"
        "  minimax-m2:\n"
        "    provider: openai_compatible\n"
        "    model: MiniMax-M2\n"
        "    supports_tools: false\n"
    )
    today = date.today()
    ar = tmp_path / "artifacts"
    (ar / "research").mkdir(parents=True)
    (ar / "research" / f"sophie-{today.isoformat()}.json").write_text('{"sections":[]}')

    # Patch the imports inside content_stage.
    monkeypatch.setattr("providers.model_providers.make_provider", fake_make_provider)
    import content_stage
    monkeypatch.setattr(content_stage, "run_packet_synthesis_provider", fake_run_packet)
    monkeypatch.setattr(content_stage, "parse_content_output", fake_parse)
    monkeypatch.setattr("issue_schema.validate_issue_artifact", fake_validate)
    monkeypatch.setattr("issue_schema.write_issue_artifact", fake_write)

    # Pipeline default says claude-opus, override says minimax-m2.
    config = {"pipeline": {"models": {"synthesis": "claude-opus"}}}
    content_stage.run_synthesis_stage(
        config=config, today=today, issue_num=1, recent_headlines=[],
        repo_root=tmp_path, artifacts_root=ar,
        synthesis_provider_name="hosted_packet_synthesis",
        model_override="minimax-m2",
        log=lambda _: None,
    )
    assert captured["cfg"]["provider"] == "openai_compatible"
    assert captured["called_with_provider"] == "openai_compatible"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_content_stage.py::test_run_synthesis_stage_uses_model_override -v
```

Expected: TypeError on `model_override` (kwarg doesn't exist yet).

- [ ] **Step 3: Modify `scripts/content_stage.py`**

Replace the `run_synthesis_stage` function (currently at line 509). The full updated function:

```python
def run_synthesis_stage(
    config: dict,
    today: date,
    issue_num: int,
    recent_headlines: List[str],
    repo_root: Path,
    artifacts_root: Path,
    synthesis_provider_name: str,
    model_override: str | None = None,
    log: Callable[[str], None] = print,
) -> dict:
    """Synthesize newsletter issue. Returns issue dict."""
    from providers.model_providers import make_provider
    from providers.model_presets import load_presets, resolve_model_config
    from issue_schema import validate_issue_artifact, write_issue_artifact

    raw_cfg = (
        model_override
        or config.get("pipeline", {}).get("models", {}).get("synthesis")
    )
    presets = load_presets(repo_root) if raw_cfg else {}
    resolved = resolve_model_config(raw_cfg, presets) if raw_cfg else None
    provider = make_provider(resolved, repo_root=repo_root) if resolved else None

    log(f"Running synthesis stage (provider: {synthesis_provider_name})...")

    if synthesis_provider_name == "hosted_packet_synthesis":
        from research_stage import get_research_artifact_path, load_research_packet
        ranked_path = get_research_artifact_path(repo_root, today, artifacts_root=artifacts_root)
        if not ranked_path.exists():
            raise FileNotFoundError(
                f"Ranked research packet not found: {ranked_path}. Run ranking stage first."
            )
        packet = load_research_packet(ranked_path)
        prompt = build_packet_synthesis_prompt(today, issue_num, config, packet)
        log("Calling packet synthesis provider...")
        raw_output = run_packet_synthesis_provider(prompt, repo_root, provider=provider)
    elif synthesis_provider_name == "hosted_integrated_search":
        prompt = build_content_prompt(today, issue_num, config, recent_headlines)
        log("Calling integrated search provider...")
        raw_output = run_content_provider(
            prompt, repo_root, provider=provider,
            allowed_tools="WebSearch,WebFetch", max_turns=10,
        )
    else:
        raise ValueError(f"Unknown synthesis provider: {synthesis_provider_name}")

    issue = parse_content_output(raw_output, repo_root)
    validate_issue_artifact(issue)
    write_issue_artifact(repo_root, issue, artifacts_root=artifacts_root)
    log("Issue artifact written.")
    return issue
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_content_stage.py::test_run_synthesis_stage_uses_model_override -v
```

Expected: PASS.

- [ ] **Step 5: Run the full content_stage test file**

```bash
pytest tests/test_content_stage.py -v
```

Expected: all tests pass (no regression).

- [ ] **Step 6: Commit**

```bash
git add scripts/content_stage.py tests/test_content_stage.py
git commit -m "feat: synthesis stage accepts model_override preset"
```

---

## Task 5: Wire resolver into `ranking_stage.py`

**Files:**
- Modify: `scripts/ranking_stage.py:79-134`
- Modify: `tests/test_research_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_research_pipeline.py`:

```python
def test_rank_candidates_uses_model_override(tmp_path, monkeypatch):
    """When model_override is set, the chosen preset is resolved and used."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

    captured = {}

    def fake_make_provider(cfg, repo_root=None):
        captured["cfg"] = cfg
        class _P:
            name = cfg["provider"]
            def generate(self, *a, **kw): return {"result": "{}"}
        return _P()

    def fake_model_rank(filtered, config, repo_root, provider):
        captured["used_provider"] = provider.name
        return {**filtered, "ranked": True}

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "model_presets.yaml").write_text(
        "presets:\n"
        "  claude-sonnet:\n"
        "    provider: claude\n"
        "    model: sonnet\n"
        "    supports_tools: true\n"
        "  minimax-m2:\n"
        "    provider: openai_compatible\n"
        "    model: MiniMax-M2\n"
        "    supports_tools: false\n"
    )

    monkeypatch.setattr("providers.model_providers.make_provider", fake_make_provider)
    monkeypatch.setattr("providers.llm_providers.model_rank_candidates", fake_model_rank)

    import ranking_stage
    config = {"pipeline": {"models": {"ranking": "claude-sonnet"}}}
    ranking_stage.rank_candidates(
        filtered_pool={"sections": []},
        config=config,
        ranker_provider="hosted_model_ranker",
        repo_root=tmp_path,
        model_override="minimax-m2",
    )
    assert captured["cfg"]["provider"] == "openai_compatible"
    assert captured["used_provider"] == "openai_compatible"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_research_pipeline.py::test_rank_candidates_uses_model_override -v
```

Expected: TypeError on `model_override` kwarg.

- [ ] **Step 3: Update `scripts/ranking_stage.py`**

Replace `rank_candidates` (line 79) and `run_ranking_stage` (line 102):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_research_pipeline.py tests/test_pipeline_integration.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/ranking_stage.py tests/test_research_pipeline.py
git commit -m "feat: ranking stage accepts model_override preset"
```

---

## Task 6: Replace MiniMax api_key special-case in `openai_compatible.py`

**Files:**
- Modify: `scripts/providers/model_providers/openai_compatible.py:23-32`
- Modify: `tests/providers/test_model_providers.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/providers/test_model_providers.py`:

```python
def test_openai_compatible_loads_api_key_from_env_var(tmp_path, monkeypatch):
    """When api_key_env is in config, the named env var is read for the key."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from providers.model_providers.openai_compatible import OpenAICompatibleProvider

    monkeypatch.setenv("MY_TEST_KEY", "secret-value")
    p = OpenAICompatibleProvider({
        "provider": "openai_compatible",
        "model": "test-model",
        "base_url": "https://example.com/v1",
        "api_key_env": "MY_TEST_KEY",
    }, repo_root=tmp_path)
    # The OpenAI client is constructed with the resolved key.
    assert p.client.api_key == "secret-value"


def test_openai_compatible_no_minimax_url_special_case(tmp_path, monkeypatch):
    """Without api_key_env, MiniMax URL no longer triggers implicit key loading."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from providers.model_providers.openai_compatible import OpenAICompatibleProvider

    # Make sure MINIMAX_API_KEY is not present.
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    p = OpenAICompatibleProvider({
        "provider": "openai_compatible",
        "model": "MiniMax-M2",
        "base_url": "https://api.minimax.io/v1",
        # api_key_env intentionally absent
    }, repo_root=tmp_path)
    # Should fall through with the default placeholder, not load_api_key.
    assert p.client.api_key == "not-needed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/providers/test_model_providers.py::test_openai_compatible_loads_api_key_from_env_var tests/providers/test_model_providers.py::test_openai_compatible_no_minimax_url_special_case -v
```

Expected: the second test fails because the special case still kicks in.

- [ ] **Step 3: Update `scripts/providers/model_providers/openai_compatible.py`**

Replace the `__init__` method (lines 23-32):

```python
def __init__(self, config: dict, repo_root: Optional[Path] = None):
    super().__init__(config)
    base_url = config.get("base_url", "http://localhost:1234/v1")
    api_key = config.get("api_key", "not-needed")
    self.model = config.get("model")
    if not self.model:
        raise ValueError("OpenAICompatibleProvider requires 'model' in config")
    api_key_env = config.get("api_key_env")
    if api_key_env and (api_key == "not-needed" or api_key == ""):
        api_key = load_api_key(api_key_env, repo_root)
    self.client = OpenAI(base_url=base_url, api_key=api_key)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/providers/ -v
```

Expected: all provider tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/providers/model_providers/openai_compatible.py tests/providers/test_model_providers.py
git commit -m "refactor: drop minimax url special-case, use api_key_env"
```

---

## Task 7: Plumb model overrides through `stage_runner._dispatch_stage`

**Files:**
- Modify: `web/api/services/stage_runner.py:158-176`
- Modify: `tests/test_stage_runner.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_stage_runner.py`:

```python
def test_dispatch_stage_passes_model_override_to_synthesis(tmp_path, monkeypatch):
    """When provider_overrides has synthesis_model, it is forwarded to run_synthesis_stage."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    sys.path.insert(0, str(Path(__file__).parent.parent))

    captured = {}
    def fake_run_synthesis(**kwargs):
        captured.update(kwargs)
    def fake_recent(*a, **kw): return []
    def fake_issue_num(*a, **kw): return 1

    monkeypatch.setattr("content_stage.run_synthesis_stage", fake_run_synthesis)
    monkeypatch.setattr("generate.get_recent_headlines", fake_recent)
    monkeypatch.setattr("generate.get_next_issue_number", fake_issue_num)

    # Minimal config dir.
    (tmp_path / "config" / "children").mkdir(parents=True)
    (tmp_path / "config" / "pipelines").mkdir(parents=True)
    (tmp_path / "config" / "themes").mkdir(parents=True)
    (tmp_path / "config" / "children" / "sophie.yaml").write_text("newsletter:\n  active_sections: []\n")
    (tmp_path / "config" / "pipelines" / "default.yaml").write_text("pipeline: {}\n")
    (tmp_path / "config" / "themes" / "default.yaml").write_text("template_path: x\n")

    from web.api.services.stage_runner import _dispatch_stage
    ar = tmp_path / "artifacts" / "approaches" / "my-run"
    ar.mkdir(parents=True)
    overrides = {"synthesis_provider": "hosted_packet_synthesis", "synthesis_model": "minimax-m2"}
    _dispatch_stage("synthesis", tmp_path, ar, overrides, log=lambda _: None)
    assert captured["model_override"] == "minimax-m2"
    assert captured["synthesis_provider_name"] == "hosted_packet_synthesis"


def test_dispatch_stage_passes_model_override_to_ranking(tmp_path, monkeypatch):
    """When provider_overrides has ranking_model, it is forwarded to run_ranking_stage."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    sys.path.insert(0, str(Path(__file__).parent.parent))

    captured = {}
    def fake_run_ranking(**kwargs):
        captured.update(kwargs)
    monkeypatch.setattr("ranking_stage.run_ranking_stage", fake_run_ranking)

    (tmp_path / "config" / "children").mkdir(parents=True)
    (tmp_path / "config" / "pipelines").mkdir(parents=True)
    (tmp_path / "config" / "themes").mkdir(parents=True)
    (tmp_path / "config" / "children" / "sophie.yaml").write_text("newsletter:\n  active_sections: []\n")
    (tmp_path / "config" / "pipelines" / "default.yaml").write_text("pipeline: {}\n")
    (tmp_path / "config" / "themes" / "default.yaml").write_text("template_path: x\n")

    from web.api.services.stage_runner import _dispatch_stage
    ar = tmp_path / "artifacts" / "approaches" / "my-run"
    ar.mkdir(parents=True)
    overrides = {"ranker_provider": "hosted_model_ranker", "ranking_model": "claude-sonnet"}
    _dispatch_stage("ranking", tmp_path, ar, overrides, log=lambda _: None)
    assert captured["model_override"] == "claude-sonnet"
    assert captured["ranker_provider"] == "hosted_model_ranker"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_stage_runner.py -v
```

Expected: the two new tests fail (kwargs not forwarded).

- [ ] **Step 3: Update `web/api/services/stage_runner.py`**

In `_dispatch_stage`, replace the `ranking` and `synthesis` branches (lines 157-176):

```python
elif stage == "ranking":
    from ranking_stage import run_ranking_stage
    ranker = provider_overrides.get("ranker_provider", "heuristic_ranker")
    model_override = provider_overrides.get("ranking_model")
    run_ranking_stage(
        config=config, today=today, repo_root=repo_root,
        artifacts_root=artifacts_root, ranker_provider=ranker,
        model_override=model_override, log=log,
    )

elif stage == "synthesis":
    from content_stage import run_synthesis_stage
    from generate import get_recent_headlines, get_next_issue_number, NEWSLETTERS_DIR
    synthesis_provider = provider_overrides.get("synthesis_provider", "hosted_packet_synthesis")
    model_override = provider_overrides.get("synthesis_model")
    recent = get_recent_headlines(NEWSLETTERS_DIR, today)
    issue_num = get_next_issue_number(NEWSLETTERS_DIR)
    run_synthesis_stage(
        config=config, today=today, issue_num=issue_num,
        recent_headlines=recent, repo_root=repo_root,
        artifacts_root=artifacts_root,
        synthesis_provider_name=synthesis_provider,
        model_override=model_override, log=log,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_stage_runner.py -v
```

Expected: all stage runner tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/api/services/stage_runner.py tests/test_stage_runner.py
git commit -m "feat: stage runner forwards model overrides to stages"
```

---

## Task 8: Merge run `settings.json` into trigger overrides

**Files:**
- Modify: `web/api/routers/stages.py:26-44`
- Modify: `tests/test_web_api.py`

**Why:** Today, `RunDetail.tsx:26` calls `triggerStage(runName, stage)` with no overrides. The router passes `body.provider_overrides` (an empty dict) to `runner.trigger()`, so the per-run settings written at create time never reach stage execution. We fix this by reading `settings.json` server-side and merging it into the trigger body.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_api.py`:

```python
def test_trigger_stage_merges_settings_json_into_overrides(client, repo_root, monkeypatch):
    """The trigger endpoint should pass settings.json values to the runner."""
    import json
    captured = {}

    class FakeRunner:
        def __init__(self, *a, **kw): pass
        def trigger(self, name, stage, overrides):
            captured["overrides"] = overrides
        def is_running(self, name, stage): return False

    monkeypatch.setattr("web.api.services.stage_runner.StageRunner", FakeRunner)

    # Pre-create a run with settings.
    ar = repo_root / "artifacts" / "approaches" / "test-run"
    ar.mkdir(parents=True)
    (ar / "settings.json").write_text(json.dumps({
        "synthesis_provider": "hosted_packet_synthesis",
        "synthesis_model": "minimax-m2",
    }))

    resp = client.post("/api/runs/test-run/stages/synthesis", json={"provider_overrides": {}})
    assert resp.status_code == 200
    assert captured["overrides"]["synthesis_model"] == "minimax-m2"
    assert captured["overrides"]["synthesis_provider"] == "hosted_packet_synthesis"


def test_trigger_stage_request_overrides_win_over_settings(client, repo_root, monkeypatch):
    """When the trigger body sets a key, it overrides settings.json."""
    import json
    captured = {}

    class FakeRunner:
        def __init__(self, *a, **kw): pass
        def trigger(self, name, stage, overrides):
            captured["overrides"] = overrides
        def is_running(self, name, stage): return False

    monkeypatch.setattr("web.api.services.stage_runner.StageRunner", FakeRunner)

    ar = repo_root / "artifacts" / "approaches" / "test-run"
    ar.mkdir(parents=True)
    (ar / "settings.json").write_text(json.dumps({"synthesis_model": "claude-opus"}))

    resp = client.post(
        "/api/runs/test-run/stages/synthesis",
        json={"provider_overrides": {"synthesis_model": "minimax-m2"}},
    )
    assert resp.status_code == 200
    assert captured["overrides"]["synthesis_model"] == "minimax-m2"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_web_api.py::test_trigger_stage_merges_settings_json_into_overrides tests/test_web_api.py::test_trigger_stage_request_overrides_win_over_settings -v
```

Expected: tests fail (settings.json is not read by the trigger endpoint).

- [ ] **Step 3: Update `web/api/routers/stages.py`**

Replace the `trigger_stage` handler:

```python
import json

@router.post("/{name}/stages/{stage}")
async def trigger_stage(
    name: str,
    stage: str,
    body: TriggerBody,
    request: Request,
    repo_root: Path = Depends(get_repo_root),
):
    if stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")
    ar = repo_root / "artifacts" / "approaches" / name
    if not ar.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {name}")

    # Merge persisted settings.json with request-time overrides; request wins.
    settings: dict = {}
    settings_path = ar / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = {}
    merged = {**settings, **body.provider_overrides}

    runner = _get_runner(request, repo_root)
    try:
        runner.trigger(name, stage, merged)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"accepted": True, "run": name, "stage": stage}
```

Add `import json` near the top of the file (alongside the existing imports).

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_web_api.py -v
```

Expected: all web API tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/api/routers/stages.py tests/test_web_api.py
git commit -m "fix: trigger endpoint merges settings.json into stage overrides"
```

---

## Task 9: Validate model presets at run-create time

**Files:**
- Modify: `web/api/services/run_service.py:108-120`
- Modify: `web/api/routers/runs.py:13-30`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_api.py`:

```python
def test_create_run_accepts_valid_synthesis_model(client, repo_root):
    """Valid preset name in synthesis_model is accepted."""
    (repo_root / "config" / "model_presets.yaml").write_text(
        "presets:\n"
        "  claude-opus:\n"
        "    provider: claude\n"
        "    model: opus\n"
        "    supports_tools: true\n"
    )
    resp = client.post("/api/runs", json={
        "name": "valid-run",
        "provider_overrides": {
            "synthesis_provider": "hosted_packet_synthesis",
            "synthesis_model": "claude-opus",
        },
    })
    assert resp.status_code == 200


def test_create_run_rejects_unknown_synthesis_model(client, repo_root):
    """Unknown preset name returns 400."""
    (repo_root / "config" / "model_presets.yaml").write_text(
        "presets:\n"
        "  claude-opus:\n"
        "    provider: claude\n"
        "    model: opus\n"
        "    supports_tools: true\n"
    )
    resp = client.post("/api/runs", json={
        "name": "bad-run",
        "provider_overrides": {"synthesis_model": "made-up-preset"},
    })
    assert resp.status_code == 400
    assert "made-up-preset" in resp.json()["detail"]


def test_create_run_rejects_incompatible_preset_for_integrated_search(client, repo_root):
    """A preset without supports_tools cannot pair with hosted_integrated_search."""
    (repo_root / "config" / "model_presets.yaml").write_text(
        "presets:\n"
        "  minimax-m2:\n"
        "    provider: openai_compatible\n"
        "    model: MiniMax-M2\n"
        "    supports_tools: false\n"
    )
    resp = client.post("/api/runs", json={
        "name": "bad-combo",
        "provider_overrides": {
            "synthesis_provider": "hosted_integrated_search",
            "synthesis_model": "minimax-m2",
        },
    })
    assert resp.status_code == 400
    assert "tool" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_web_api.py::test_create_run_accepts_valid_synthesis_model tests/test_web_api.py::test_create_run_rejects_unknown_synthesis_model tests/test_web_api.py::test_create_run_rejects_incompatible_preset_for_integrated_search -v
```

Expected: rejection tests fail (validation doesn't exist yet).

- [ ] **Step 3: Add a validation helper in `web/api/services/run_service.py`**

Append to `run_service.py`:

```python
def _validate_model_overrides(repo_root: Path, overrides: dict) -> None:
    """Raise ValueError if any model preset name is unknown or strategy-incompatible."""
    import sys
    from pathlib import Path as _P
    sys.path.insert(0, str(_P(__file__).parent.parent.parent.parent / "scripts"))
    from providers.model_presets import load_presets, STRATEGY_REQUIRES_TOOLS

    pairs = [
        ("synthesis_model", "synthesis_provider"),
        ("ranking_model", "ranker_provider"),
    ]
    relevant = [(m, s) for m, s in pairs if m in overrides]
    if not relevant:
        return

    presets = load_presets(repo_root)
    for model_key, strategy_key in relevant:
        name = overrides[model_key]
        if name not in presets:
            raise ValueError(
                f"Unknown model preset: {name!r}. "
                f"Available: {sorted(presets.keys())}"
            )
        strategy = overrides.get(strategy_key)
        if strategy and STRATEGY_REQUIRES_TOOLS.get(strategy):
            if not presets[name].get("supports_tools"):
                raise ValueError(
                    f"Preset {name!r} is incompatible with strategy {strategy!r} "
                    f"(tool-calling required)."
                )
```

Modify `create_run` to call validation before writing:

```python
def create_run(repo_root: Path, name: str, overrides: dict[str, str] = None) -> RunSummary:
    ar = _artifacts_root(repo_root, name)
    if ar.exists():
        raise FileExistsError(f"Run already exists: {name}")
    if overrides:
        _validate_model_overrides(repo_root, overrides)
    ar.mkdir(parents=True)
    if overrides:
        (ar / "settings.json").write_text(json.dumps(overrides), encoding="utf-8")
    return RunSummary(
        name=name,
        created_at=str(int(ar.stat().st_mtime)),
        stage_statuses={s: "pending" for s in STAGES},
        settings=overrides or {},
    )
```

- [ ] **Step 4: Convert ValueError to HTTP 400 in the router**

Modify `web/api/routers/runs.py:25-30`:

```python
@router.post("")
def create_run(body: CreateRunBody, repo_root: Path = Depends(get_repo_root)):
    from web.api.services.run_service import create_run as _create
    try:
        return _create(repo_root, body.name, body.provider_overrides)
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Run already exists: {body.name}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_web_api.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/api/services/run_service.py web/api/routers/runs.py tests/test_web_api.py
git commit -m "feat: validate model presets at run-create time"
```

---

## Task 10: Add `GET /api/model-presets` endpoint

**Files:**
- Create: `web/api/routers/model_presets.py`
- Modify: `web/api/main.py:27-32`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_api.py`:

```python
def test_get_model_presets_returns_catalog(client, repo_root):
    """The endpoint returns presets, strategy_requirements, and defaults."""
    (repo_root / "config" / "model_presets.yaml").write_text(
        "presets:\n"
        "  claude-opus:\n"
        "    label: Claude Opus\n"
        "    provider: claude\n"
        "    model: opus\n"
        "    supports_tools: true\n"
        "  minimax-m2:\n"
        "    provider: openai_compatible\n"
        "    model: MiniMax-M2\n"
        "    supports_tools: false\n"
    )
    (repo_root / "config" / "pipelines" / "default.yaml").write_text(
        "pipeline:\n"
        "  content_provider: hosted_packet_synthesis\n"
        "models:\n"
        "  synthesis: claude-opus\n"
        "  ranking: claude-opus\n"
    )
    resp = client.get("/api/model-presets")
    assert resp.status_code == 200
    body = resp.json()
    names = [p["name"] for p in body["presets"]]
    assert "claude-opus" in names
    assert "minimax-m2" in names
    # Label fallback when absent
    minimax = next(p for p in body["presets"] if p["name"] == "minimax-m2")
    assert minimax["label"] == "minimax-m2"
    # Strategy requirements present
    assert body["strategy_requirements"]["hosted_integrated_search"]["requires_tools"] is True
    # Defaults sourced from pipelines/default.yaml
    assert body["defaults"]["synthesis"] == "claude-opus"
    assert body["defaults"]["ranking"] == "claude-opus"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_web_api.py::test_get_model_presets_returns_catalog -v
```

Expected: 404 — endpoint doesn't exist.

- [ ] **Step 3: Create the router**

```python
# web/api/routers/model_presets.py
"""Model preset catalog endpoint."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends

from web.api.deps import get_repo_root

router = APIRouter(prefix="/api/model-presets", tags=["model-presets"])


@router.get("")
def get_model_presets(repo_root: Path = Depends(get_repo_root)):
    sys.path.insert(0, str(repo_root / "scripts"))
    from providers.model_presets import load_presets, STRATEGY_REQUIRES_TOOLS

    presets_raw = load_presets(repo_root)
    presets_out = [
        {
            "name": name,
            "label": p.get("label", name),
            "provider": p.get("provider"),
            "supports_tools": bool(p.get("supports_tools", False)),
        }
        for name, p in presets_raw.items()
    ]

    # Pipeline defaults (synthesis/ranking model names) for UI pre-selection.
    defaults: dict = {}
    pipeline_path = repo_root / "config" / "pipelines" / "default.yaml"
    if pipeline_path.exists():
        data = yaml.safe_load(pipeline_path.read_text(encoding="utf-8")) or {}
        models = data.get("models", {}) or {}
        for stage in ("synthesis", "ranking"):
            value = models.get(stage)
            # Only include if it's already a preset name (string). Inline dicts
            # are legacy and not surfaced as defaults to the UI.
            if isinstance(value, str):
                defaults[stage] = value

    return {
        "presets": presets_out,
        "strategy_requirements": {
            strategy: {"requires_tools": requires}
            for strategy, requires in STRATEGY_REQUIRES_TOOLS.items()
        },
        "defaults": defaults,
    }
```

- [ ] **Step 4: Register the router in `web/api/main.py`**

Replace lines 27-32:

```python
    from web.api.routers import configs, runs, stages, compare, promote, model_presets
    app.include_router(configs.router)
    app.include_router(runs.router)
    app.include_router(stages.router)
    app.include_router(compare.router)
    app.include_router(promote.router)
    app.include_router(model_presets.router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_web_api.py -v
```

Expected: all web API tests pass.

- [ ] **Step 6: Commit**

```bash
git add web/api/routers/model_presets.py web/api/main.py tests/test_web_api.py
git commit -m "feat: add GET /api/model-presets endpoint"
```

---

## Task 11: Extend frontend API client with preset types and fetcher

**Files:**
- Modify: `web/ui/src/api/client.ts:1-93`

- [ ] **Step 1: Add types and the fetch helper**

In `web/ui/src/api/client.ts`, add the new types after the existing `RunSummary` interface (around line 20):

```typescript
export interface ModelPreset {
  name: string
  label: string
  provider: string
  supports_tools: boolean
}

export interface ModelPresetCatalog {
  presets: ModelPreset[]
  strategy_requirements: Record<string, { requires_tools: boolean }>
  defaults: { synthesis?: string; ranking?: string }
}
```

In the `api` object literal (around line 90, after the `compare` entry), add:

```typescript
  modelPresets: () => request<ModelPresetCatalog>('/model-presets'),
```

The full updated `api` literal (showing context):

```typescript
export const api = {
  configs: { /* ... unchanged ... */ },
  runs: { /* ... unchanged ... */ },
  compare: (a: string, b: string, stage: string) =>
    request<CompareResult>(`/compare?a=${a}&b=${b}&stage=${stage}`),
  modelPresets: () => request<ModelPresetCatalog>('/model-presets'),
}
```

- [ ] **Step 2: Run the typescript build to verify**

```bash
cd web/ui && npx tsc --noEmit && cd ../..
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/ui/src/api/client.ts
git commit -m "feat: client.ts supports model preset catalog"
```

---

## Task 12: Add model dropdowns to `RunsPage.tsx`

**Files:**
- Modify: `web/ui/src/pages/RunsPage.tsx`

This is a larger UI edit. Replace the entire file with the version below.

- [ ] **Step 1: Replace `web/ui/src/pages/RunsPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api, type RunSummary, type ModelPresetCatalog } from '../api/client'
import RunList from '../components/RunList'
import RunDetail from '../components/RunDetail'

const PROVIDER_OPTIONS: Record<string, string[]> = {
  research: ['brave_deterministic'],
  ranking: ['heuristic_ranker', 'hosted_model_ranker'],
  synthesis: ['hosted_packet_synthesis', 'hosted_integrated_search'],
  render: ['local_renderer'],
}

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [openRun, setOpenRun] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<ModelPresetCatalog | null>(null)

  const refresh = () => api.runs.list().then(setRuns)
  useEffect(() => {
    refresh()
    api.modelPresets().then(setCatalog).catch(e => console.error('preset load failed', e))
  }, [])

  const synthesisStrategy = overrides.synthesis_provider ?? PROVIDER_OPTIONS.synthesis[0]
  const rankingStrategy = overrides.ranking_provider ?? PROVIDER_OPTIONS.ranking[0]

  // Filter presets compatible with the selected synthesis strategy.
  const compatibleSynthesisPresets = (() => {
    if (!catalog) return []
    const requiresTools = catalog.strategy_requirements[synthesisStrategy]?.requires_tools
    return catalog.presets.filter(p => !requiresTools || p.supports_tools)
  })()

  // Ranking model presets — model_ranker has no tool requirement; show all.
  const rankingPresets = catalog?.presets ?? []

  // Auto-correct synthesis_model when the strategy changes and current pick is incompatible.
  useEffect(() => {
    if (!catalog) return
    const current = overrides.synthesis_model
    const stillCompatible = current && compatibleSynthesisPresets.some(p => p.name === current)
    if (!stillCompatible && compatibleSynthesisPresets.length > 0) {
      const fallback = catalog.defaults.synthesis && compatibleSynthesisPresets.some(p => p.name === catalog.defaults.synthesis)
        ? catalog.defaults.synthesis
        : compatibleSynthesisPresets[0].name
      setOverrides(prev => ({ ...prev, synthesis_model: fallback }))
    }
  }, [synthesisStrategy, catalog])

  // Initialize defaults once catalog arrives.
  useEffect(() => {
    if (!catalog) return
    setOverrides(prev => {
      const next = { ...prev }
      if (!next.synthesis_model && catalog.defaults.synthesis) next.synthesis_model = catalog.defaults.synthesis
      if (!next.ranking_model && catalog.defaults.ranking) next.ranking_model = catalog.defaults.ranking
      return next
    })
  }, [catalog])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    setError(null)

    const fullOverrides: Record<string, string> = { ...overrides }
    for (const [stage, opts] of Object.entries(PROVIDER_OPTIONS)) {
      const key = `${stage}_provider`
      if (!fullOverrides[key]) fullOverrides[key] = opts[0]
    }

    // Drop ranking_model when ranking strategy is heuristic (no model used).
    if (fullOverrides.ranking_provider === 'heuristic_ranker') {
      delete fullOverrides.ranking_model
    }

    try {
      await api.runs.create(newName.trim(), fullOverrides)
      setNewName('')
      // Keep current overrides so the next run inherits the same picks.
      await refresh()
      setOpenRun(newName.trim())
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setCreating(false)
    }
  }

  if (openRun) {
    return (
      <div>
        <button onClick={() => { setOpenRun(null); refresh() }} style={{ margin: 12 }}>
          ← Back to runs
        </button>
        <RunDetail runName={openRun} />
      </div>
    )
  }

  const showRankingModel = rankingStrategy === 'hosted_model_ranker'

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginTop: 0 }}>Runs</h2>

      {/* New run form */}
      <div style={{ marginBottom: 24, padding: 16, background: '#11111b', borderRadius: 8 }}>
        <h3 style={{ marginTop: 0, fontSize: 14 }}>New Run</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="run name (e.g. approach-b1)"
            style={{ flex: 1, padding: '6px 10px', background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
          />
          <button onClick={handleCreate} disabled={creating || !newName.trim()}>
            {creating ? 'Creating…' : 'Create'}
          </button>
        </div>

        {/* Strategy row */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: '#6c7086', alignSelf: 'center' }}>Strategy:</span>
          {Object.entries(PROVIDER_OPTIONS).map(([stage, opts]) => (
            <label key={stage} style={{ fontSize: 12, color: '#6c7086' }}>
              {stage}:&nbsp;
              <select
                value={overrides[`${stage}_provider`] ?? opts[0]}
                onChange={e => setOverrides(prev => ({ ...prev, [`${stage}_provider`]: e.target.value }))}
                style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
              >
                {opts.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
          ))}
        </div>

        {/* Model row */}
        {catalog && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: '#6c7086' }}>Model:</span>
            {showRankingModel && (
              <label style={{ fontSize: 12, color: '#6c7086' }}>
                ranking:&nbsp;
                <select
                  value={overrides.ranking_model ?? catalog.defaults.ranking ?? ''}
                  onChange={e => setOverrides(prev => ({ ...prev, ranking_model: e.target.value }))}
                  style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
                >
                  {rankingPresets.map(p => <option key={p.name} value={p.name}>{p.label}</option>)}
                </select>
              </label>
            )}
            <label style={{ fontSize: 12, color: '#6c7086' }}>
              synthesis:&nbsp;
              <select
                value={overrides.synthesis_model ?? catalog.defaults.synthesis ?? ''}
                onChange={e => setOverrides(prev => ({ ...prev, synthesis_model: e.target.value }))}
                style={{ background: '#1e1e2e', color: '#cdd6f4', border: '1px solid #313244', borderRadius: 4 }}
              >
                {compatibleSynthesisPresets.map(p => <option key={p.name} value={p.name}>{p.label}</option>)}
              </select>
            </label>
            {synthesisStrategy === 'hosted_integrated_search' && (
              <span style={{ fontSize: 11, color: '#a6adc8', fontStyle: 'italic' }}>
                This model also does the search and ranking inline.
              </span>
            )}
          </div>
        )}
        {error && <div style={{ color: '#f38ba8', fontSize: 13, marginTop: 8 }}>{error}</div>}
      </div>

      <RunList runs={runs} onOpen={setOpenRun} />
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd web/ui && npx tsc --noEmit && cd ../..
```

Expected: no errors.

- [ ] **Step 3: Verify Vite production build succeeds**

```bash
cd web/ui && npm run build && cd ../..
```

Expected: build success, no errors.

- [ ] **Step 4: Commit**

```bash
git add web/ui/src/pages/RunsPage.tsx
git commit -m "feat: add per-stage model dropdowns to run creation"
```

---

## Task 13: End-to-end smoke test

**Files:** none — this is a manual verification task.

This task is non-automated. The goal is to confirm the full path works in a real browser.

- [ ] **Step 1: Run all tests**

```bash
pytest -v
```

Expected: every test passes.

- [ ] **Step 2: Start the dev server**

```bash
bash web/dev.sh &
```

(or whichever command starts both API and UI; check `web/dev.sh`).

Expected: the API runs on :8000 and the UI on :5173.

- [ ] **Step 3: Smoke-test in the browser**

Open `http://localhost:5173` and:
1. Confirm the run-creation form has a "Strategy:" row and a "Model:" row.
2. Pick `hosted_packet_synthesis` for synthesis, then change the synthesis model dropdown — verify all presets including `minimax-m2` appear.
3. Switch synthesis strategy to `hosted_integrated_search`. Verify:
   - The synthesis model dropdown filters to Claude-only presets.
   - The italic helper text appears: *"This model also does the search and ranking inline."*
4. Switch ranking strategy to `heuristic_ranker`. Verify the ranking model dropdown disappears.
5. Switch ranking strategy to `hosted_model_ranker`. Verify the ranking model dropdown appears.
6. Create a run with name `smoke-minimax`, synthesis = `hosted_packet_synthesis`, synthesis_model = `minimax-m2`.
7. Confirm the run appears in the run list with chips showing `synthesis_model: minimax-m2`.

Note: do not actually trigger the synthesis stage unless you want to spend MiniMax/Brave quota. The validation that `minimax-m2` reaches `make_provider` is already covered by the unit tests.

- [ ] **Step 4: Stop the dev server**

```bash
# Ctrl+C in the dev.sh terminal, or:
pkill -f "uvicorn web.api.main"
pkill -f "vite"
```

- [ ] **Step 5: Final commit (if anything was tweaked during smoke testing)**

```bash
git status
# If anything changed, commit it. Otherwise skip.
```

---

## Summary

After all tasks are complete, the following should be true:

1. `config/model_presets.yaml` exists with five presets (`claude-opus`, `claude-sonnet`, `claude-haiku`, `minimax-m2`, `local-lmstudio`).
2. `config/pipelines/default.yaml` references `claude-opus` and `claude-sonnet` by preset name.
3. `scripts/providers/model_presets.py` provides `load_presets`, `resolve_preset`, `resolve_model_config`, and `STRATEGY_REQUIRES_TOOLS`.
4. `content_stage.run_synthesis_stage` and `ranking_stage.run_ranking_stage` accept a `model_override` kwarg.
5. `openai_compatible.py` no longer hard-codes the MiniMax URL check; it reads `api_key_env` from the config dict.
6. `web/api/services/stage_runner.py` forwards `synthesis_model` and `ranking_model` to the stage functions.
7. `web/api/routers/stages.py` merges per-run `settings.json` into trigger overrides before dispatching.
8. `web/api/services/run_service.py` validates preset names and tool-compatibility at create time.
9. `GET /api/model-presets` returns the catalog, strategy requirements, and defaults.
10. The web UI's run-creation form has filtered model dropdowns with helper text and a `(reset)`-equivalent auto-correct when strategies change.
11. CLI runs (`python3 scripts/generate.py`) continue to work unchanged.
12. Existing tests still pass; new tests cover the new behavior.
