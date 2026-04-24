# MiniMax Test Approaches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create four staging approach overlays (`approach-minimax-rank`, `approach-minimax-synth`, `approach-minimax-both`, `approach-minimax-mode-a`) under `staging/approaches/`, each with a minimal `config/pipelines/default.yaml` that routes MiniMax-M2.7 through the appropriate pipeline phase.

**Architecture:** Each approach is a narrow overlay on the existing staging baseline. Approach-local config inherits staging defaults by omission — only the pipeline/model settings needed for that specific MiniMax test are overridden. No script overrides expected.

**Tech Stack:** YAML config, `scripts/generate.py --env staging --approach <name> --test`

---

## File Structure

```
staging/approaches/
  approach-minimax-rank/
    config/pipelines/default.yaml    # MiniMax ranking only
  approach-minimax-synth/
    config/pipelines/default.yaml    # MiniMax synthesis only
  approach-minimax-both/
    config/pipelines/default.yaml    # MiniMax ranking + synthesis
  approach-minimax-mode-a/
    config/pipelines/default.yaml    # MiniMax via openai_agentic path
```

Each approach owns **only** `config/pipelines/default.yaml`. No `children/`, `sections/`, `themes/`, or other directories unless implementation proves a specific override is required.

---

## Task 1: Create `approach-minimax-rank`

**Files:**
- Create: `staging/approaches/approach-minimax-rank/config/pipelines/default.yaml`

- [ ] **Step 1: Write the approach config**

```yaml
pipeline:
  research_provider: brave_deterministic
  ranker_provider: hosted_model_ranker
  content_provider: hosted_packet_synthesis
  render_provider: local_renderer
  fallback_content_provider: hosted_integrated_search

models:
  synthesis:
    provider: claude
    model: sonnet
  ranking:
    provider: openai_compatible
    base_url: https://api.minimax.io/v1
    model: MiniMax-M2.7
```

- [ ] **Step 2: Verify the directory structure was created**

Run: `ls staging/approaches/approach-minimax-rank/config/pipelines/`
Expected: `default.yaml` exists

- [ ] **Step 3: Commit**

```bash
git add staging/approaches/approach-minimax-rank/
git commit -m "feat: add approach-minimax-rank for MiniMax ranking phase"
```

---

## Task 2: Create `approach-minimax-synth`

**Files:**
- Create: `staging/approaches/approach-minimax-synth/config/pipelines/default.yaml`

- [ ] **Step 1: Write the approach config**

```yaml
pipeline:
  research_provider: brave_deterministic
  ranker_provider: heuristic_ranker
  content_provider: hosted_packet_synthesis
  render_provider: local_renderer
  fallback_content_provider: hosted_integrated_search

models:
  synthesis:
    provider: openai_compatible
    base_url: https://api.minimax.io/v1
    model: MiniMax-M2.7
  ranking:
    provider: claude
    model: sonnet
```

- [ ] **Step 2: Verify the directory structure was created**

Run: `ls staging/approaches/approach-minimax-synth/config/pipelines/`
Expected: `default.yaml` exists

- [ ] **Step 3: Commit**

```bash
git add staging/approaches/approach-minimax-synth/
git commit -m "feat: add approach-minimax-synth for MiniMax synthesis phase"
```

---

## Task 3: Create `approach-minimax-both`

**Files:**
- Create: `staging/approaches/approach-minimax-both/config/pipelines/default.yaml`

- [ ] **Step 1: Write the approach config**

```yaml
pipeline:
  research_provider: brave_deterministic
  ranker_provider: hosted_model_ranker
  content_provider: hosted_packet_synthesis
  render_provider: local_renderer
  fallback_content_provider: hosted_integrated_search

models:
  synthesis:
    provider: openai_compatible
    base_url: https://api.minimax.io/v1
    model: MiniMax-M2.7
  ranking:
    provider: openai_compatible
    base_url: https://api.minimax.io/v1
    model: MiniMax-M2.7
```

- [ ] **Step 2: Verify the directory structure was created**

Run: `ls staging/approaches/approach-minimax-both/config/pipelines/`
Expected: `default.yaml` exists

- [ ] **Step 3: Commit**

```bash
git add staging/approaches/approach-minimax-both/
git commit -m "feat: add approach-minimax-both for MiniMax ranking + synthesis"
```

---

## Task 4: Create `approach-minimax-mode-a`

**Files:**
- Create: `staging/approaches/approach-minimax-mode-a/config/pipelines/default.yaml`

- [ ] **Step 1: Write the approach config**

```yaml
pipeline:
  research_provider: brave_deterministic
  ranker_provider: heuristic_ranker
  content_provider: hosted_integrated_search
  render_provider: local_renderer
  fallback_content_provider: hosted_integrated_search

models:
  synthesis:
    provider: openai_agentic
    base_url: https://api.minimax.io/v1
    model: MiniMax-M2.7
  ranking:
    provider: claude
    model: sonnet
```

- [ ] **Step 2: Verify the directory structure was created**

Run: `ls staging/approaches/approach-minimax-mode-a/config/pipelines/`
Expected: `default.yaml` exists

- [ ] **Step 3: Commit**

```bash
git add staging/approaches/approach-minimax-mode-a/
git commit -m "feat: add approach-minimax-mode-a for MiniMax agentic path"
```

---

## Task 5: Resolution Sanity Check

**Files:**
- Verify: All four approach configs resolve correctly

- [ ] **Step 1: Smoke-test each approach resolves without FileNotFoundError**

For each approach, confirm that `resolve_config_file` finds `pipelines/default.yaml`:

```bash
python3 -c "
from scripts.generate import load_config
from pathlib import Path
REPO_ROOT = Path('.')

for approach in ['approach-minimax-rank', 'approach-minimax-synth', 'approach-minimax-both', 'approach-minimax-mode-a']:
    try:
        cfg = load_config(REPO_ROOT, 'staging', approach)
        print(f'{approach}: OK — pipeline={cfg[\"pipeline"]}')
    except Exception as e:
        print(f'{approach}: FAIL — {e}')
"
```

Expected: All four print `OK` with their respective pipeline settings.

- [ ] **Step 2: Verify no accidental config drift — only pipeline/model keys differ from staging baseline**

```bash
python3 -c "
from scripts.generate import load_config
from pathlib import Path
import json
REPO_ROOT = Path('.')

staging = load_config(REPO_ROOT, 'staging', None)
for approach in ['approach-minimax-rank', 'approach-minimax-synth', 'approach-minimax-both', 'approach-minimax-mode-a']:
    cfg = load_config(REPO_ROOT, 'staging', approach)
    diff_keys = set(cfg.keys()) - set(staging.keys())
    if diff_keys:
        print(f'{approach}: extraneous keys in approach config: {diff_keys}')
    else:
        print(f'{approach}: no extraneous keys — OK')
"
```

Expected: All four print `no extraneous keys — OK`.

- [ ] **Step 3: Commit resolution check if no issues found**

```bash
git add staging/
git commit -m "test: verify all MiniMax approach configs resolve correctly"
```

---

## Test Commands (for hand-off to Marvin/Calvin)

After all tasks complete, these commands should be run in order:

```bash
python3 scripts/generate.py --env staging --approach approach-minimax-rank --test
python3 scripts/generate.py --env staging --approach approach-minimax-synth --test
python3 scripts/generate.py --env staging --approach approach-minimax-both --test
python3 scripts/generate.py --env staging --approach approach-minimax-mode-a --test
```

---

## Self-Review Checklist

1. **Spec coverage:** Each of the four approaches in Section 4 of the spec has a corresponding task with the exact YAML from Section 6.
2. **Placeholder scan:** No TODOs, no "TBD", no vague steps — every step shows actual YAML or actual commands.
3. **Type consistency:** All pipeline keys (`research_provider`, `ranker_provider`, `content_provider`, `render_provider`, `fallback_content_provider`) and model keys (`provider`, `model`, `base_url`) are consistent across all four tasks and match the spec's Section 6 definitions.
4. **Narrow overlays:** Each approach owns only `config/pipelines/default.yaml` as specified in Section 8.1 of the spec.
5. **API key note:** Remind user to confirm `MINIMAX_API_KEY` is set in `.env` before running the test commands.
