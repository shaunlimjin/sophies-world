# Staging/Production Env + Approaches Design

**Date:** 2026-04-20
**Status:** Spec draft
**Owner:** Shaun
**Related:** sections.yaml phase-zone restructure, admin console

---

## What this is

A spec for making Sophie's World safe to iterate on by separating **staging** and **production** as isolated runtime environments, with **approaches** as the unit of experimentation inside staging.

---

## Problem statement

Currently the app has one runtime — prod — with test artifacts in `newsletters/test/`. Iterating on config or scripts risks prod stability. When we do the major sections.yaml restructure or try new generation approaches, we have no clean way to run them safely before committing to prod.

We also want to compare multiple generation approaches simultaneously in staging before promoting any of them.

---

## Core model

**Root = prod baseline.** The existing `scripts/` and `config/` directories are prod. Staging is a lightweight overlay — it only contains files that differ from prod. Approaches are fully self-contained snapshots (config + scripts + templates) used for full-stack experiments inside staging.

Staging usually runs the same scripts as prod. When a staging-specific script change is needed, the full file is copied into `staging/scripts/` and modified there — no partial function-level patching.

---

## Directory structure

```
sophies-world/
├── scripts/                        # prod scripts (root = prod baseline)
│   ├── generate.py                 # entry point — accepts --env, --approach
│   ├── content_stage.py
│   ├── research_stage.py
│   ├── ranking_stage.py
│   ├── render_stage.py
│   ├── issue_schema.py
│   ├── send.py
│   ├── promote.py                  # promotes approach → staging or staging → prod
│   └── providers/
│       ├── brave_search.py
│       └── hosted_llm_provider.py
├── config/                         # prod config (root = prod baseline)
│   ├── children/sophie.yaml
│   ├── sections.yaml
│   └── research.yaml
├── staging/
│   ├── scripts/                    # optional overrides — only files that differ from prod
│   ├── config/                     # optional overrides — only files that differ from prod
│   └── approaches/
│       └── approach-b2-v2/         # fully self-contained snapshot
│           ├── scripts/
│           ├── config/
│           └── templates/          # optional — only if overriding template.html
├── artifacts/
│   ├── research/                   # prod research packets
│   ├── issues/                     # prod issue artifacts
│   ├── staging/
│   │   ├── research/
│   │   └── issues/
│   └── approaches/
│       └── approach-b2-v2/
│           ├── research/
│           ├── issues/
│           └── newsletters/
├── newsletters/                    # prod HTML outputs
└── newsletters/staging/            # staging HTML outputs
```

---

## CLI flags

`generate.py` gains two new flags:

```
--env [prod|staging]        # defaults to prod
--approach <name>           # only valid with --env staging; raises an error with --env prod
```

Examples:

```bash
# Prod (default — unchanged behavior)
python3 scripts/generate.py --test

# Staging
python3 scripts/generate.py --env staging --test

# Staging with a specific approach
python3 scripts/generate.py --env staging --approach approach-b2-v2 --test
```

---

## Overlay resolution

`generate.py` resolves script and config file paths at startup using a small helper. Resolved paths are logged for debuggability.

**Prod:**
1. `scripts/<file>` — always root, no overlay

**Staging (no approach):**
1. `staging/scripts/<file>` if it exists
2. `scripts/<file>` — prod baseline fallback

**Staging with approach:**
1. `staging/approaches/<name>/scripts/<file>` if it exists
2. `staging/scripts/<file>` if it exists
3. `scripts/<file>` — prod baseline fallback

Same resolution logic applies to config files.

---

## Output routing

Determined by flags — no separate config needed:

| Invocation | HTML output | Artifacts |
|---|---|---|
| `--env prod` | `newsletters/` | `artifacts/` |
| `--env staging` | `newsletters/staging/` | `artifacts/staging/` |
| `--env staging --approach <name>` | `artifacts/approaches/<name>/newsletters/` | `artifacts/approaches/<name>/` |

---

## Promotion

Approaches must be promoted to staging before they can be promoted to prod. Direct approach → prod is rejected.

```bash
# Promote approach to staging default
python3 scripts/promote.py --from approach-b2-v2 --to staging

# Promote staging to prod
python3 scripts/promote.py --from staging --to prod
```

`promote.py` behavior:
1. Validates source and destination (rejects `--from approach-* --to prod` with a clear error)
2. Shows a diff summary of what will change (files added/modified/removed)
3. Asks for confirmation before overwriting
4. Copies files
5. Auto-commits with a message derived from the flags: e.g. `chore: promote approach-b2-v2 to staging`

Future: the admin console will expose promotion via UI by calling the same underlying logic.

---

## Migration path

**Phase 1 — Structural split**
1. Create `staging/scripts/`, `staging/config/`, `staging/approaches/` directories
2. Populate `staging/config/` as a copy of `config/` (starting point for staging overrides)
3. Add `--env` and `--approach` flags + overlay resolver to `generate.py`
4. Add output routing logic
5. Add `promote.py`
6. Verify: `python3 scripts/generate.py --env staging --test` produces output in `newsletters/staging/`

**Phase 2 — First approach**
1. Copy current prod baseline (`scripts/`, `config/`) into `staging/approaches/approach-b1/` as the first named experiment
2. Verify: `python3 scripts/generate.py --env staging --approach approach-b1 --test` produces output in `artifacts/approaches/approach-b1/`

**Phase 3 — sections.yaml restructure** *(separate workstream)*
Once Phase 1 is stable, the restructure lands in `staging/config/` first, then promotes to prod when validated.

---

## What this enables

- Safe iteration in staging without touching production
- Multiple approaches runnable simultaneously for side-by-side comparison
- Full-stack experiments (config + scripts + templates together)
- Clear enforced promotion path: approach → staging default → prod
- Admin console becomes the approach management and comparison hub

---

## What this doesn't solve

- The sections.yaml phase-zone restructure (Phase 3 above)
- The research.yaml merge into sections.yaml
- Novelty guards (separate workstream)
- Approach creation via admin console UI (future)
