# Per-Stage Model Selection — Design Spec

**Date:** 2026-04-28
**Status:** Draft — pending implementation plan

## Problem

The web UI's run-creation form (`web/ui/src/pages/RunsPage.tsx:6-11`) lets the user pick a *pipeline strategy* per stage (e.g. `hosted_packet_synthesis` vs `hosted_integrated_search` for synthesis), but it does not let the user pick *which model* runs that strategy. The model is fixed in `config/pipelines/default.yaml` under `pipeline.models.<stage>` and is only swappable today by creating a config-overlay approach — clunky for casual experimentation (e.g. "use MiniMax for synthesis on this run, Claude on the next").

This spec adds per-run model selection for the synthesis and ranking stages, backed by a named-preset registry. Research and render stages are out of scope (no model is invoked).

## Goals

- A user creating a run from the web UI can pick which model runs synthesis and which model runs ranking, independently of the pipeline strategy.
- The chosen models are persisted with the run and visible on the run list.
- Old runs and CLI invocations continue to work unchanged (additive, backward compatible).
- A single source of truth defines what `claude-opus`, `minimax-m2`, etc. mean — no duplication between UI presets and pipeline defaults.

## Non-goals

- No new model providers. The supported set stays `claude`, `openai_compatible`, `openai_agentic`.
- No UI for editing presets. Presets are authored in YAML; reload happens on server start.
- No per-stage model selection for research (Brave only) or render (local renderer only).

## Architecture

### Components

1. **New** `config/model_presets.yaml` — flat catalog of named presets.
2. **Modified** `config/pipelines/default.yaml` — `pipeline.models.<stage>` is migrated from inline `{provider, model}` to a preset-name string.
3. **New** `scripts/providers/model_presets.py` — loader and resolver helpers.
4. **Modified** `scripts/content_stage.py`, `scripts/ranking_stage.py` — accept an optional `model_override` parameter that takes priority over the on-disk default.
5. **Modified** `scripts/providers/model_providers/openai_compatible.py` — drop the hard-coded `MINIMAX_API_KEY` special case; use the preset's `api_key_env` instead.
6. **Modified** `web/api/services/stage_runner.py` — read `synthesis_model` / `ranking_model` from `provider_overrides` and thread them into the stage functions.
7. **Modified** `web/api/services/run_service.py` — validate model preset references at run-create time.
8. **New** `web/api/routers/model_presets.py` — `GET /api/model-presets` returns the preset catalog and strategy requirements.
9. **Modified** `web/ui/src/pages/RunsPage.tsx` — add filtered model dropdowns; default values from pipeline defaults.
10. **Unchanged** `web/ui/src/components/RunList.tsx` — existing `settings`-chip rendering picks up the new keys automatically.

### Data flow

```
UI (RunsPage)
  └─ fetches GET /api/model-presets   →  populates model dropdowns
  └─ POST /api/runs  with { provider_overrides: { synthesis_model: "minimax-m2", ... } }
       └─ run_service.create_run validates preset refs, writes settings.json

User clicks "Run synthesis"
  └─ stages router reads settings.json, merges into provider_overrides
       └─ stage_runner._dispatch_stage extracts synthesis_model
            └─ run_synthesis_stage(model_override="minimax-m2")
                 └─ resolve_preset("minimax-m2", ...) → {provider, model, base_url, api_key_env}
                      └─ make_provider(...) → OpenAICompatibleProvider
```

## Detailed design

### Preset registry — `config/model_presets.yaml`

```yaml
presets:
  claude-opus:
    provider: claude
    model: opus
    supports_tools: true

  claude-sonnet:
    provider: claude
    model: sonnet
    supports_tools: true

  claude-haiku:
    provider: claude
    model: haiku
    supports_tools: true

  minimax-m2:
    provider: openai_compatible
    model: MiniMax-M2
    base_url: https://api.minimax.io/v1
    api_key_env: MINIMAX_API_KEY
    supports_tools: false

  local-lmstudio:
    provider: openai_compatible
    model: local-model
    base_url: http://localhost:1234/v1
    supports_tools: false
```

**Schema:**
- Top-level key is the preset name. Used by `pipelines/default.yaml` and `settings.json` as a string reference.
- `provider` (required) — one of `claude`, `openai_compatible`, `openai_agentic`. Maps to `make_provider()` config.
- `model` (required) — model identifier passed through to the provider.
- `base_url` (optional) — for `openai_compatible` / `openai_agentic`. Omitted for `claude`.
- `api_key_env` (optional) — name of env var to read for credentials. If absent, provider uses its own default behavior.
- `supports_tools` (required) — boolean. Used to filter dropdown options when a strategy requires tool-calling (e.g. `hosted_integrated_search`).
- `label` (optional) — human-readable display name. Defaults to the preset name if absent.

### Resolver — `scripts/providers/model_presets.py`

```python
def load_presets(repo_root: Path) -> dict[str, dict]:
    """Read config/model_presets.yaml. Returns {name: preset_dict}.
       Raises FileNotFoundError if the file is missing."""

def resolve_preset(name: str, presets: dict) -> dict:
    """Return {provider, model, base_url?, api_key_env?} suitable for make_provider().
       Raises ValueError if preset name not found."""

def resolve_model_config(value: str | dict, presets: dict) -> dict:
    """Accepts either a preset name (str) or an inline dict, returns the resolved
       dict suitable for make_provider(). Used by stages so existing overlay
       configs (staging/, approaches/) that still use the inline-dict form keep
       working without migration."""

STRATEGY_REQUIRES_TOOLS = {
    "hosted_integrated_search": True,
    "hosted_packet_synthesis": False,
    "hosted_model_ranker": False,
}
```

`resolve_preset` strips internal-only fields (`supports_tools`, `label`) before returning so the dict can be passed straight to `make_provider()`.

`resolve_model_config` is what the stages call. It dispatches on type: a string is treated as a preset name and resolved via `resolve_preset`; a dict is passed through directly (assumed to already be in `make_provider()` shape).

### Default-config migration — `config/pipelines/default.yaml`

Before:
```yaml
models:
  synthesis: { provider: claude, model: opus }
  ranking:   { provider: claude, model: sonnet }
```

After:
```yaml
models:
  synthesis: claude-opus
  ranking:   claude-sonnet
```

### Stage integration — `content_stage.py` / `ranking_stage.py`

Each affected stage function gets a new optional kwarg `model_override: str | None = None`.

In `content_stage.py:523` (and equivalent in `ranking_stage.py`):

```python
# Was:
synthesis_cfg = config.get("pipeline", {}).get("models", {}).get("synthesis")
provider = make_provider(synthesis_cfg, repo_root=repo_root) if synthesis_cfg else None

# Becomes:
raw = model_override or config.get("pipeline", {}).get("models", {}).get("synthesis")
resolved = resolve_model_config(raw, load_presets(repo_root)) if raw else None
provider = make_provider(resolved, repo_root=repo_root) if resolved else None
```

`resolve_model_config` accepts either a preset name (the new form, used by `pipelines/default.yaml` after migration and by UI run overrides) or an inline `{provider, model, ...}` dict (the legacy form, still present in `staging/` and `approaches/` overlays). This means no overlay migration is required for this change to land — existing inline-dict configs keep working.

CLI usage (`generate.py`) does not pass `model_override`, so it falls back to the on-disk config — no behavior change for existing CLI runs.

### MiniMax key special-case removal

`scripts/providers/model_providers/openai_compatible.py:30-31` currently has:

```python
if "minimax.io" in base_url and (api_key == "not-needed" or api_key == ""):
    api_key = load_api_key("MINIMAX_API_KEY", repo_root)
```

Replace with: if config provides `api_key_env`, call `load_api_key(api_key_env, repo_root)`. The MiniMax-specific URL check is removed; the preset's `api_key_env: MINIMAX_API_KEY` field carries the equivalent intent.

### Run settings — `settings.json`

Two new optional keys on `provider_overrides` / `settings.json`:

```json
{
  "research_provider":  "brave_deterministic",
  "ranking_provider":   "hosted_model_ranker",
  "synthesis_provider": "hosted_packet_synthesis",
  "render_provider":    "local_renderer",

  "synthesis_model":    "minimax-m2",
  "ranking_model":      "claude-sonnet"
}
```

If a model key is absent, the stage falls back to `pipelines/default.yaml`. Existing runs without these keys continue to work unchanged.

The UI **always includes** `synthesis_model` and `ranking_model` (when applicable to the chosen strategy) in the saved settings, so the run is self-describing — viewing an old run's settings shows exactly what model ran, regardless of what the pipeline default was at the time.

### API — `GET /api/model-presets`

New router file `web/api/routers/model_presets.py`. Response shape:

```json
{
  "presets": [
    { "name": "claude-opus",   "label": "Claude Opus",   "provider": "claude",
      "supports_tools": true },
    { "name": "claude-sonnet", "label": "Claude Sonnet", "provider": "claude",
      "supports_tools": true },
    { "name": "minimax-m2",    "label": "MiniMax M2",    "provider": "openai_compatible",
      "supports_tools": false }
  ],
  "strategy_requirements": {
    "hosted_integrated_search": { "requires_tools": true },
    "hosted_packet_synthesis":  { "requires_tools": false },
    "hosted_model_ranker":      { "requires_tools": false }
  },
  "defaults": {
    "synthesis": "claude-opus",
    "ranking":   "claude-sonnet"
  }
}
```

`defaults` is sourced from `pipelines/default.yaml.models` so the UI can pre-select pipeline defaults without a second fetch.

### API — `run_service.create_run` validation

When a `synthesis_model` or `ranking_model` is present in the overrides, validate:
1. The preset name exists in `model_presets.yaml`.
2. The preset's `supports_tools` satisfies the strategy's `requires_tools`.

Raise `HTTPException(400, "Preset 'X' is incompatible with strategy 'Y' (tool-calling required)")` on failure. The UI's filtering prevents this for normal use; the validation catches direct API misuse and config drift.

### Stage runner plumbing — `web/api/services/stage_runner.py`

In `_dispatch_stage`:

```python
elif stage == "ranking":
    ranker = provider_overrides.get("ranker_provider", "heuristic_ranker")
    model_override = provider_overrides.get("ranking_model")
    run_ranking_stage(
        config=config, today=today, repo_root=repo_root,
        artifacts_root=artifacts_root, ranker_provider=ranker,
        model_override=model_override,
        log=log,
    )

elif stage == "synthesis":
    synthesis_provider = provider_overrides.get("synthesis_provider", "hosted_packet_synthesis")
    model_override = provider_overrides.get("synthesis_model")
    run_synthesis_stage(
        ...,
        synthesis_provider_name=synthesis_provider,
        model_override=model_override,
        log=log,
    )
```

Verify the stages router (`web/api/routers/stages.py`) loads `settings.json` for the run and merges into `provider_overrides` before calling `trigger()`. If it does not, add a single `_read_settings()` call there. Without this, the model overrides written at create time would not reach stage execution.

### UI — `web/ui/src/pages/RunsPage.tsx`

**Layout:** add a second row of dropdowns under the existing strategy row.

```
Strategy:   research [▼ brave]   ranking [▼ heuristic]   synthesis [▼ packet]   render [▼ local]
Model:                            ranking [▼ —]          synthesis [▼ claude-opus]
```

**Behavior:**
- On mount, fetch `GET /api/model-presets` once and store `presets`, `strategy_requirements`, `defaults` in state.
- The **ranking model** dropdown is visible only when `ranking_provider === 'hosted_model_ranker'`. Hidden (and not submitted) when `heuristic_ranker` is selected.
- The **synthesis model** dropdown is always visible. Its options are filtered by the chosen synthesis strategy:
  - `hosted_packet_synthesis` → all presets.
  - `hosted_integrated_search` → presets with `supports_tools: true` only. Show inline helper text: *"This model also does the search and ranking inline."*
- Default selections: pipeline defaults from the API response.
- When a strategy change makes the current model selection incompatible, auto-select the first compatible preset and show a small `(reset)` indicator next to the field for one second.
- On submit, always include `synthesis_model` and (when applicable) `ranking_model` in the saved overrides.

**Run-list display:** no code change. `RunList.tsx:33-41` already iterates `Object.entries(run.settings)` and renders chips, so new keys appear automatically.

## Backward compatibility

- `config/pipelines/default.yaml.models` migrates from inline dicts to preset names. The resolver (`resolve_model_config`) accepts either form, so existing overlay configs under `staging/config/` and `staging/approaches/*/config/` — which still use the inline-dict form — keep working without any migration.
- Existing run `settings.json` files that lack `synthesis_model` / `ranking_model` keys are unaffected — stages fall back to the pipeline default.
- CLI runs (`python3 scripts/generate.py`) do not pass `model_override`, so they read from `pipelines/default.yaml` unchanged.
- The MiniMax key special-case is removed at the same time `model_presets.yaml` lands. Because the new `minimax-m2` preset declares `api_key_env: MINIMAX_API_KEY`, behavior for MiniMax callers is unchanged. The matching change in `openai_compatible.py` reads `api_key_env` from the config dict — when overlays pass an inline dict that includes `base_url: https://api.minimax.io/...` but no `api_key_env`, the provider falls through with `api_key="not-needed"` and the call fails with a clear auth error. Overlay authors who relied on the implicit special case need to add `api_key_env: MINIMAX_API_KEY` to their overlay (one line) or migrate the overlay to the preset reference `synthesis: minimax-m2`. This is a small, one-time fix per overlay; an alternative is to retain the implicit special case in `openai_compatible.py` for one release as a deprecation buffer (decide in the implementation plan).

## Testing strategy

- **Unit tests** for the resolver: preset loading, preset resolution, error on unknown name, `STRATEGY_REQUIRES_TOOLS` lookup.
- **Unit tests** for `run_service.create_run` validation: incompatible preset/strategy raises 400.
- **Integration test** for `stage_runner._dispatch_stage` with a `synthesis_model` override: confirm the right `ModelProvider` subclass is instantiated.
- **Existing tests** (`tests/test_content_stage.py`, etc.) must continue to pass without modification, confirming CLI behavior is unchanged.
- **Manual UI test:** open the run-creation form, pick `hosted_integrated_search` for synthesis, confirm the model dropdown filters to Claude-only presets and shows the helper text. Switch to `hosted_packet_synthesis`, confirm MiniMax appears.

## Open questions

None at present. Remaining decisions are implementation-mechanical (e.g. exact YAML loading idiom, whether to colocate `STRATEGY_REQUIRES_TOOLS` with the resolver or a separate constants module — both are fine; pick one in the plan).
