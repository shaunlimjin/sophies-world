# Config Architecture Refactor Implementation Plan

**Date:** 2026-04-22  
**Status:** Implemented (merged in PR #3, merge commit `77681e6`)  
**Spec:** `docs/superpowers/specs/2026-04-22-config-architecture-refactor.md`  
**Goal:** Replace the current monolithic `sections.yaml` + `research.yaml` model with cohesive `config/sections/*.yaml` files, move infrastructure into `config/pipelines/*.yaml`, and update the loader/codepath in one clean cutover.

---

## 1. Scope

This plan covers:
- new config directory structure
- migration of existing config data
- loader/code updates
- verification via real generation invariants
- deletion of the old structure after verification

This plan does **not** cover:
- multi-child support
- admin UI changes
- new ranking logic
- prompt redesign

---

## 2. Desired end state

```text
config/
├── children/
│   └── sophie.yaml
├── sections/
│   ├── weird_but_true.yaml
│   ├── world_watch.yaml
│   ├── singapore_spotlight.yaml
│   ├── usa_corner.yaml
│   ├── gymnastics_corner.yaml
│   ├── kpop_corner.yaml
│   ├── money_moves.yaml
│   └── sophies_challenge.yaml
├── pipelines/
│   └── default.yaml
└── themes/
    └── default.yaml
```

Where:
- `children/` owns child identity + editorial defaults + active sections
- `sections/` owns display + editorial + research + section-local ranking intent
- `pipelines/` owns provider/model routing + global domains + global ranking defaults

---

## 3. Implementation strategy

### Strategy: one-shot cutover

We are still early enough to avoid a dual old/new compatibility layer.
So the implementation should be:
1. create the new files
2. migrate content into them
3. update loader + callers
4. verify against concrete invariants
5. delete old files

This keeps the system simpler than supporting both config shapes at once.

---

## 4. Workstreams

## Workstream A — Create new config structure

### A1. Add `config/sections/`
Create one file per section:
- `weird_but_true.yaml`
- `world_watch.yaml`
- `singapore_spotlight.yaml`
- `usa_corner.yaml`
- `gymnastics_corner.yaml`
- `kpop_corner.yaml`
- `money_moves.yaml`
- `sophies_challenge.yaml`

### A2. Add `config/pipelines/default.yaml`
Populate from current:
- `sophie.yaml` generation block
- `research.yaml` global domain lists
- `research.yaml` global ranking defaults

### A3. Update `config/children/sophie.yaml`
Keep:
- identity
- interests
- active sections
- theme
- child-specific editorial defaults

Remove:
- provider routing
- model selection
- ranker/content infra blocks

---

## Workstream B — Build migration script

### B1. Create a one-off migration helper
Suggested path:
- `scripts/migrate_config_architecture.py`

Responsibilities:
- read `config/sections.yaml`
- read `config/research.yaml`
- merge per-section keys into one section object per file
- write `config/sections/<section>.yaml`
- extract global pipeline values into `config/pipelines/default.yaml`
- optionally rewrite `config/children/sophie.yaml`

### B2. Script should be deterministic
Requirements:
- stable key ordering
- safe re-run behavior
- no partial destructive writes without explicit confirmation

### B3. Keep it one-off, not a permanent tool
This is migration tooling, not product surface.
It does not need a long maintenance tail.

---

## Workstream C — Update config loading code

### C1. Introduce new loader shape
Update config resolution logic so a run resolves:
1. child profile
2. pipeline config (default unless another pipeline is selected)
3. active section configs only
4. theme config

### C2. Resolved runtime config should still look ergonomic in code
Even if files are split, callers should receive one coherent resolved config object.

Suggested resolved structure:
```python
{
  "profile": {...},
  "pipeline": {...},
  "sections": {
    "world_watch": {...},
    ...
  },
  "theme": {...}
}
```

### C3. Keep environment overlay behavior intact
The new loader must still support:
- prod baseline
- staging override
- approach override

That means the resolver should work for paths like:
- `config/sections/world_watch.yaml`
- `staging/config/sections/world_watch.yaml`
- `staging/approaches/<name>/config/sections/world_watch.yaml`

### C4. Update all call sites
Likely areas:
- `generate.py`
- `research_stage.py`
- `ranking_stage.py`
- `content_stage.py`
- any helper that assumes monolithic `sections.yaml` or `research.yaml`

---

## Workstream D — Verification

### D1. Structural verification
Confirm:
- all active sections resolve successfully
- no missing section files
- pipeline loads correctly
- child profile still loads correctly
- staging/prod/approach overlays still resolve correctly

### D2. Behavioral verification
Run the same generation flow before and after the refactor and verify these invariants:
- same resolved child/profile semantics
- same active section set
- same provider/ranker selection
- same research plan structure
- same research packet schema
- same output path semantics
- same rendered issue shape
- acceptable content drift only where hosted generation is inherently nondeterministic

### D3. Minimum verification commands
At minimum:
```bash
python3 -m pytest -q
python3 scripts/generate.py --test
python3 scripts/generate.py --env staging --test
python3 scripts/generate.py --env staging --approach approach-b1 --test
```

### D4. Manual inspection
Inspect:
- generated issue artifact JSON
- research packet JSON
- final HTML output
- resolved config logging if available

---

## Workstream E — Cleanup

### E1. Remove old files
After verification:
- delete `config/sections.yaml`
- delete `config/research.yaml`

### E2. Update docs
Update at minimum:
- `README.md`
- any relevant plan/spec references
- config examples in docs

### E3. Keep the new structure legible
A new contributor should be able to understand:
- what belongs in `children/`
- what belongs in `sections/`
- what belongs in `pipelines/`

---

## 5. Recommended task order

1. Write migration script
2. Generate new `config/sections/*.yaml`
3. Create `config/pipelines/default.yaml`
4. Rewrite `config/children/sophie.yaml`
5. Update loader + callers
6. Run tests
7. Run prod/staging/approach smoke generations
8. Inspect outputs
9. Delete old files
10. Update docs

---

## 6. Risks and mitigations

### Risk 1 — Loader breakage across staging/prod/approach overlays
**Mitigation:** verify env resolution explicitly as part of the migration, not as an afterthought.

### Risk 2 — Hidden assumptions about `sections.yaml`
**Mitigation:** grep for direct references before code changes and update them systematically.

### Risk 3 — Behavioral drift in research/ranking
**Mitigation:** verify research plan shape and research packet schema, not just final HTML.

### Risk 4 — Documentation drift
**Mitigation:** update README in the same implementation sequence, not later.

---

## 7. Definition of done

The refactor is done when:
- config is split into `children/`, `sections/`, and `pipelines/`
- code loads only the new structure
- staging/prod/approach overlays still work
- smoke generations succeed
- tests pass
- old monolithic files are removed
- README is updated

---

## 8. Suggested first implementation slice

If we want to keep the first coding slice tight, do this first:

### Slice 1
- create `config/pipelines/default.yaml`
- migrate one or two section files manually (`world_watch`, `money_moves`)
- build the new loader shape
- prove it works end-to-end

Then finish the remaining section migrations once the shape is validated.

This is optional, but it can reduce the risk of doing the entire cutover blind.
