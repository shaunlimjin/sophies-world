# Issue Generation, Output, and Logging Playbook

**Date:** 2026-04-22  
**Status:** Draft spec  
**Scope:** Sophie’s World single-child app, with staging/prod environments and named approaches  
**Purpose:** Clean up the operational playbook for generating issues, storing outputs, and capturing logs/debug artifacts as experimentation frequency increases.

---

## 1. Problem

Sophie’s World started as a simple weekly generation flow. It now supports:

- prod vs staging environments
- named approaches in staging
- multiple generation modes (A / B1 / B2)
- tagged comparison runs
- more frequent experimental runs

The current filesystem is starting to get messy and hard to reason about.

### Current pain points

1. **Debug artifacts are flat and lossy**
   - `artifacts/debug/last-*` files overwrite each other
   - hard to understand which run produced which prompt/stdout/stderr
   - no durable run identity

2. **Output conventions are inconsistent across envs**
   - prod/test/staging/approach outputs all land in different places with different naming logic
   - artifacts and newsletters are partially grouped by environment, partially by date, partially by mode

3. **There is no first-class run record**
   - we have outputs, but not a clean per-run bundle
   - hard to answer: "what exactly happened in this run?"

4. **Comparison workflow is more manual than it should be**
   - tagged runs help, but the operator still has to mentally stitch together HTML, issue JSON, research JSON, and debug logs

5. **Frequent experimentation will amplify the mess**
   - multiple issues per day
   - multiple approaches
   - retries / parser failures / alternate prompts
   - more need for reproducibility and traceability

---

## 2. Goal

Create a cleaner, explicit operational playbook for:

- issue generation
- output storage
- per-run logging
- debug artifact retention
- experiment comparison

The system should support higher-frequency experimentation without turning the repo into a junk drawer.

---

## 3. Product principles

### 3.1 Runs should be first-class
A generation attempt should be treated as a **run** with a durable identity.

A run is not just an HTML file or an issue JSON. It is a bundle containing:
- metadata
- inputs/config resolution
- outputs
- logs
- debug artifacts
- status

### 3.2 Stable outputs and ephemeral debug are different things
Not all artifacts deserve equal permanence.

We should separate:
- **durable product outputs** (issue JSON, research packet, final HTML)
- **run diagnostics** (stdout, stderr, prompts, parse inputs)
- **ephemeral scratch/debug** (latest pointers, transient logs)

### 3.3 Operator workflow should be obvious
Given a run, it should be easy to answer:
- what environment was this?
- what approach was this?
- what mode/ranker/provider was used?
- what files were produced?
- what failed, if anything?

### 3.4 Naming should encode identity, not just convenience
Filenames and directories should reflect:
- date
- environment
- approach (if any)
- run tag (if any)
- run id

### 3.5 Keep the repo human-legible
This is still a single-child, file-driven app. We do **not** need a database yet.
We do need better filesystem hygiene.

---

## 4. Recommendation

### Recommendation: introduce a **run-centric output model**

Every generate invocation should produce a **run directory** with a manifest and logs, while still writing canonical durable outputs to their existing environment-level locations.

This preserves the current product surface while creating a clean experiment/debug surface.

*(Note: `artifacts/runs/` should be added to `.gitignore` to prevent committing heavy debug logs).*

---

## 5. Proposed model

## 5.1 Two layers of outputs

### Layer A — Canonical durable outputs
These remain easy to find and represent the current authoritative files.

Examples:
- `artifacts/issues/...`
- `artifacts/research/...`
- `artifacts/staging/issues/...`
- `newsletters/...`
- `newsletters/staging/...`
- `artifacts/approaches/<approach>/...`

These are the files other tooling can continue to rely on.

### Layer B — Per-run bundles
Each invocation also writes a durable run bundle under a new root:

```text
artifacts/runs/<run-id>/
```

Each bundle contains:
- `manifest.json`
- `logs/stdout.txt`
- `logs/stderr.txt`
- `debug/...`
- `links.json` (pointers to canonical outputs)

This gives us traceability without forcing all downstream tooling to switch immediately.

---

## 5.2 Run identity

Each run should get a generated run id using a short timestamp, a random hex string (to prevent collisions during parallel generation), and the environment/approach:

```text
20260422-104112-a8f2-prod
20260422-104308-b1c3-staging
20260422-104455-d4e5-staging-approach-b2-v2
```

### Required run metadata
- `run_id`
- `started_at`
- `completed_at` (nullable if running or crashed)
- `status` (`running` / `success` / `failed` / `partial`)
- `env`
- `approach` (nullable)
- `run_tag` (nullable)
- `git_commit` (for reproducibility)
- `git_dirty` (boolean)
- `content_provider`
- `ranker_provider`
- `child_id`
- resolved config file paths
- produced artifact paths
- error summary (if failed)

*Note: The run directory and `manifest.json` should be initialized immediately upon starting with `status: "running"`. This makes it easy to identify and clean up runs that crashed mid-flight.*

---

## 5.3 Directory structure

### New root
```text
artifacts/
  runs/
    <run-id>/
      manifest.json
      links.json
      logs/
        stdout.txt
        stderr.txt
      debug/
        content-prompt.txt
        content-stdout.txt
        content-stderr.txt
        packet-prompt.txt
        packet-stdout.txt
        packet-stderr.txt
        ranker/
          weird_but_true/
            prompt.txt
            stdout-attempt0.txt
            stdout-attempt1.txt
          world_watch/
            ...
```

### Existing canonical outputs remain
Examples:
```text
artifacts/issues/sophie-2026-04-22.json
artifacts/staging/issues/sophie-2026-04-22.json
newsletters/staging/sophies-world-2026-04-22.html
```

The run bundle references these canonical outputs via `links.json` or `manifest.json`.

---

## 5.4 Manifest format

Example:

```json
{
  "run_id": "20260422-104308-b1c3-staging",
  "status": "success",
  "started_at": "2026-04-22T17:43:08Z",
  "completed_at": "2026-04-22T17:44:12Z",
  "git_commit": "a1b2c3d4e5f6...",
  "git_dirty": false,
  "env": "staging",
  "approach": null,
  "run_tag": null,
  "child_id": "sophie",
  "content_provider": "hosted_integrated_search",
  "ranker_provider": "heuristic_ranker",
  "resolved_config": {
    "child": "staging/config/children/sophie.yaml",
    "pipeline": "config/pipelines/default.yaml",
    "sections": {
      "world_watch": "config/sections/world_watch.yaml",
      "money_moves": "config/sections/money_moves.yaml"
    },
    "theme": "staging/config/themes/default.yaml"
  },
  "outputs": {
    "issue_artifact": "artifacts/staging/issues/sophie-2026-04-22.json",
    "research_artifact": null,
    "html": "newsletters/staging/sophies-world-2026-04-22.html"
  },
  "debug": {
    "stdout": "artifacts/runs/20260422-104308-staging/logs/stdout.txt",
    "stderr": "artifacts/runs/20260422-104308-staging/logs/stderr.txt"
  }
}
```

---

## 6. Logging policy

## 6.1 Replace flat `last-*` debug files with run-scoped debug

Current files like:
- `artifacts/debug/last-content-prompt.txt`
- `artifacts/debug/last-ranker-stdout-world_watch-attempt2.txt`

should stop being the primary durable debug surface.

### New rule
- write all durable debug output into `artifacts/runs/<run-id>/debug/...`
- maintain a **thin convenience pointer**, such as a `.latest_run` text file at the root.

Example:
```text
artifacts/runs/.latest_run
  -> text file containing the run_id of the most recent run
```

This preserves the operator convenience of “show me the latest” without sacrificing run traceability.

### Pointer scope
For now, `.latest_run` is a **global latest pointer** across all environments and approaches.
That is sufficient for Phase 1.

If operator usage later shows a need for environment-specific shortcuts, we can add:
- `.latest_prod_run`
- `.latest_staging_run`
- `.latest_<approach>_run`

Those are explicitly out of scope for the first implementation.

---

## 6.2 Separate stdout/stderr by stage

Within each run bundle, logs should be grouped by stage where useful:

```text
logs/
  generate-stdout.txt
  generate-stderr.txt
  content-stage-stdout.txt
  content-stage-stderr.txt
  packet-stage-stdout.txt
  packet-stage-stderr.txt
```

Minimum viable version:
- one `stdout.txt`
- one `stderr.txt`
- stage-specific debug files as needed

Better version later:
- stage-specific log files

---

## 6.3 Retention policy

### Durable forever (until manually cleaned)
- issue JSON
- research packets
- final HTML
- run manifests

### Keep recent N or time-windowed
- heavy debug payloads
- repeated provider stdout dumps
- transient test/debug files

Suggested default:
- keep run bundles for **30 days** in local workflow
- keep canonical outputs indefinitely
- implement a lightweight auto-prune in `generate.py` (e.g., delete runs older than 30 days automatically during startup) rather than relying on an optional cron job

### Auto-prune safety rules
- pruning must be **best-effort** only
- pruning must never fail or block issue generation
- pruning must only touch `artifacts/runs/`
- prune errors should be logged as warnings and generation should continue normally

---

## 7. Output conventions

## 7.1 Canonical outputs remain environment-centric

This avoids breaking the current repo mental model.

### Prod
- HTML: `newsletters/`
- issue artifact: `artifacts/issues/`
- research packet: `artifacts/research/`

### Prod test
- HTML: `newsletters/test/`
- issue artifact: still `artifacts/issues/`
- research packet: still `artifacts/research/`

### Staging
- HTML: `newsletters/staging/`
- issue artifact: `artifacts/staging/issues/`
- research packet: `artifacts/staging/research/`

### Staging approach
- HTML: `artifacts/approaches/<approach>/newsletters/`
- issue artifact: `artifacts/approaches/<approach>/issues/`
- research packet: `artifacts/approaches/<approach>/research/`

### New addition
Each of the above should also emit a run bundle under:
- `artifacts/runs/<run-id>/`

---

## 7.2 Tagged runs stay supported

The `--run-tag` parameter remains supported. Its primary purpose is to allow the operator to append a custom, human-readable label to the filenames of canonical outputs.

This is crucial for **side-by-side experiment comparisons**. When generating multiple variations of an issue in the same environment, the tag makes it easy to visually group, identify, and compare specific runs in the file explorer without needing to open up individual run manifests.

Example:
```text
artifacts/issues/sophie-2026-04-20-mode-b2-v2.json
newsletters/test/sophies-world-2026-04-20-mode-b2-v2.html
```

The run bundle should also record the tag in its manifest.

---

## 8. CLI and operator playbook

## 8.1 Generate commands

No breaking change to existing commands.

Examples:

```bash
python3 scripts/generate.py --test
python3 scripts/generate.py --env staging --test
python3 scripts/generate.py --env staging --approach approach-b1 --test
python3 scripts/generate.py --test --run-tag mode-b2-v2
```

### New behavior
Each command prints a final run summary such as:

```text
Run: 20260422-104308-b1c3-staging
Status: success
HTML: newsletters/staging/sophies-world-2026-04-22.html
Issue artifact: artifacts/staging/issues/sophie-2026-04-22.json
Run bundle: artifacts/runs/20260422-104308-b1c3-staging/
```

---

## 8.2 Useful operator questions this should answer easily

- What was the latest successful staging run?
- Which exact files were generated by approach-b2-v2 yesterday?
- What prompt produced this broken output?
- Which run wrote this HTML file?
- Did the failure happen in content generation, packet synthesis, or ranker parsing?

---

## 9. Recommended implementation scope

## Phase 1 — run bundle foundation

Implement now:
- generate `run_id` (collision resistant)
- create `artifacts/runs/<run-id>/`
- write `manifest.json` (initialize as `running`, update at end)
- *duplicate* stdout/stderr and stage debug into that directory (while keeping old behavior intact)
- keep canonical output behavior unchanged
- create a single global `.latest_run` pointer
- add lightweight auto-pruning for runs > 30 days old, following the non-fatal safety rules above

## Phase 2 — clean debug migration

Implement next:
- **stop** writing durable `artifacts/debug/last-*` files directly
- route provider prompts/stdout/stderr *exclusively* into run bundles

## Phase 3 — operator UX helpers

Implement later:
- `scripts/list-runs.py`
- `scripts/show-run.py <run-id>`
- optional retention cleanup script
- optional run index summary file

---

## 10. Non-goals

This spec does **not** introduce:
- a database
- a new admin console implementation
- multi-child productization
- a complete event sourcing system

This is a filesystem-and-playbook cleanup, not a platform rewrite.

---

## 11. Open questions

1. Should prod test runs get their own separate issue/research artifact roots, or keep using the current prod roots?
   - recommendation: keep current roots for now to avoid churn

2. Should run bundles use symlinks to canonical outputs or just store paths in the manifest?
   - recommendation: store paths in manifest first; symlinks optional later

3. Should approach runs continue writing canonical outputs under `artifacts/approaches/<approach>/`, or should they eventually move entirely under run bundles?
   - recommendation: keep approach-root canonical outputs for now; run bundle is additive

---

## 12. Recommendation summary

**Recommended approach:**
- keep current canonical output locations
- add a run-centric bundle layer under `artifacts/runs/`
- migrate debug output from flat `last-*` files to run-scoped debug folders
- use manifests to make experimentation traceable and legible

This gives us a cleaner experiment playbook without breaking the current app surface.

---

## 13. What success looks like

A month from now, with many issues per day across multiple approaches, we should be able to:

- trace any HTML file back to its exact run
- inspect the exact prompt/stdout/stderr for that run
- compare runs without guesswork
- avoid overwriting important debug context
- keep the repo understandable without a database
