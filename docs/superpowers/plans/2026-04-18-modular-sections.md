# Plan: Modular Newsletter Sections + Config-Driven Profiles

**Date:** 2026-04-18  
**Status:** Draft
**Spec:** `docs/superpowers/specs/2026-04-18-modular-sections-design.md`

---

## Goal

Implement a phase-1 refactor that makes Sophie's World newsletter sections configurable via local config files rather than hardcoded logic in `scripts/generate.py`, while preserving the current generate → HTML output flow.

This work should allow section swaps such as replacing `kpop_corner` with `gymnastics_corner`, and should establish a clean foundation for future admin UI and multi-family productization.

---

## Scope for This Plan

### In scope

- Add config files for child profiles, section catalog, and theme metadata
- Refactor `scripts/generate.py` to build the Claude prompt from config
- Support profile-driven active section selection
- Add one interchangeable section example, specifically `gymnastics_corner`
- Preserve existing HTML output flow and newsletter archive behavior
- Add or update tests for the new config-driven logic
- Update docs so the repo is understandable after the refactor

### Out of scope

- No admin dashboard yet
- No visual editor yet
- No database
- No authentication or user accounts
- No full migration to structured JSON output from Claude
- No `send.py` refactor beyond any minimal compatibility changes needed

---

## Deliverables

### Code / config

- `config/children/sophie.yaml`
- `config/sections.yaml`
- `config/themes/default.yaml`
- refactored `scripts/generate.py`
- any helper module(s) if config loading/validation should be split out cleanly

### Tests

- updated `tests/test_generate.py`
- any new config or prompt-assembly tests needed

### Docs

- this plan
- approved spec
- updated `CLAUDE.md` or README-level documentation as needed so the new architecture is discoverable
- backlog update if new follow-on tasks are identified during implementation

---

## Implementation Strategy

Use a staged refactor, not a big-bang rewrite.

The safest path is:

1. Introduce config files first
2. Move Sophie-specific data out of Python
3. Move section rules out of Python
4. Keep the HTML template largely intact
5. Keep Claude returning final HTML
6. Only then add the first interchangeable section example

This keeps the working surface area small while steadily untangling hardcoded logic.

---

## Phase Breakdown

### Phase 1: Add config scaffolding

#### Tasks

1. Create `config/children/`, `config/themes/`, and a top-level `config/sections.yaml`
2. Add `config/children/sophie.yaml` containing:
   - profile metadata
   - active/inactive interests
   - active section list
   - selected theme
3. Add `config/sections.yaml` containing the current reusable section catalog, including:
   - `weird_but_true`
   - `world_watch`
   - `singapore_spotlight`
   - `usa_corner`
   - `kpop_corner`
   - `gymnastics_corner`
   - `money_moves`
   - `sophies_challenge`
4. Add `config/themes/default.yaml` containing lightweight theme metadata

#### Notes

- Keep config intentionally simple in v1.5
- Avoid over-designing the schema with product-only fields we do not need yet
- Use stable IDs from day one

#### Exit criteria

- Config files exist and are human-readable
- The current Sophie newsletter can be fully described using config

---

### Phase 2: Refactor prompt assembly in `generate.py`

#### Tasks

1. Add config loading logic in `generate.py` or a small helper module
2. Replace hardcoded Sophie profile prose with profile data loaded from `config/children/sophie.yaml`
3. Replace hardcoded section rules with dynamic assembly from `config/sections.yaml`
4. Replace fixed section assumptions with profile-driven `active_sections`
5. Add basic validation errors for:
   - missing child config
   - unknown section IDs
   - missing theme config
   - malformed config fields that are required for prompt assembly
6. Preserve existing date handling, output file naming, issue numbering, and headline-avoidance behavior

#### Notes

- Do not do a full template system rewrite here
- Aim for readable prompt generation, not abstraction gymnastics
- If helper functions improve clarity, use them, but do not explode the codebase into many files unnecessarily

#### Exit criteria

- `generate.py` can build a full prompt from config
- No core section logic remains hardcoded as fixed inline prose constants beyond generic orchestration helpers

---

### Phase 3: Support interchangeable interest sections

#### Tasks

1. Add a `gymnastics_corner` section definition to the section catalog
2. Configure Sophie’s active section list to use either `kpop_corner` or `gymnastics_corner`
3. Ensure the generated prompt reflects the chosen section and its rules
4. Verify that swapping the active section requires only config edits, not Python changes

#### Notes

- This is the proof point for the refactor
- The system should not care whether the interchangeable section is K-pop, gymnastics, skiing, animals, or something else later

#### Exit criteria

- A config-only swap changes the generated newsletter section set successfully

---

### Phase 4: Test coverage and verification

#### Tasks

1. Update `tests/test_generate.py` to cover config-driven behavior
2. Add tests for:
   - loading profile config
   - resolving active sections
   - handling unknown section IDs
   - prompt assembly containing the chosen interest section
   - failure when required config is missing
3. Keep existing tests for issue numbering, output path, idempotency, and Claude output parsing
4. Run the full test suite
5. Optionally run one manual generation smoke test in `--test` mode if practical

#### Exit criteria

- Tests cover the main refactor path
- The generator still works end-to-end

---

### Phase 5: Docs cleanup

#### Tasks

1. Update `CLAUDE.md` so the repo structure and generation model match reality
2. Add a short operator note describing how to switch active sections
3. Update the ideas backlog if implementation uncovers obvious next-step improvements
4. Ensure the spec and plan remain linked and current

#### Exit criteria

- A future reader can understand how the modular section system works without reverse-engineering the code

---

## Proposed File-Level Changes

### New files

- `config/children/sophie.yaml`
- `config/sections.yaml`
- `config/themes/default.yaml`

### Modified files

- `scripts/generate.py`
- `tests/test_generate.py`
- `CLAUDE.md` possibly
- `docs/ideas-backlog.md` possibly

### Likely unchanged files

- `scripts/send.py`
- `scripts/run.sh`
- `tests/test_send.py`

---

## Suggested Config Schema (Phase 1)

### `config/children/sophie.yaml`

```yaml
id: sophie
name: Sophie
age_band: 4th-grade
location: Fremont, California
cultural_context:
  - Singaporean family in the USA
interests:
  active:
    - gymnastics
    - skiing
    - fun facts
    - saving money
  inactive:
    - k-pop
newsletter:
  active_sections:
    - weird_but_true
    - world_watch
    - singapore_spotlight
    - usa_corner
    - gymnastics_corner
    - money_moves
    - sophies_challenge
  theme: default
```

### `config/sections.yaml`

```yaml
sections:
  gymnastics_corner:
    title: "🤸 Gymnastics Corner"
    goal: "Share interesting gymnastics news, athlete stories, fun facts, or beginner-safe tips for kids."
    block_type: interest_feature
    link_style: link-rose
    content_rules:
      - Keep it age-appropriate and encouraging.
      - Prefer athlete stories, fun facts, competition highlights, or safe basic technique explanations.
      - Avoid risky coaching advice or unsafe training suggestions.
    source_preferences:
      - Olympics
      - USA Gymnastics
      - Britannica Kids
```

### `config/themes/default.yaml`

```yaml
theme_id: default
template_path: scripts/template.html
section_order_mode: profile_driven
```

---

## Risks and Mitigations

### Risk: YAML parsing introduces new dependency or fragility

**Mitigation:**
- Prefer a minimal, well-supported parser if needed
- Keep schema simple
- Add validation errors with useful messages

### Risk: Prompt quality regresses during refactor

**Mitigation:**
- Preserve current instruction richness where it matters
- Compare old and new prompt content structurally
- Run at least one smoke test generation after refactor

### Risk: Template assumptions remain too hardcoded

**Mitigation:**
- Accept this in phase 1
- Keep theme metadata light now
- Defer full componentized rendering to a later spec

### Risk: Overbuilding for future productization

**Mitigation:**
- Only implement what supports today’s section modularity
- Use future-friendly shapes without prematurely building dashboard infrastructure

---

## Verification Checklist

Before calling this work done:

- [ ] Sophie profile data is loaded from config
- [ ] Active sections are loaded from config
- [ ] Section rules are loaded from config
- [ ] `gymnastics_corner` exists and is selectable
- [ ] Swapping `kpop_corner` and `gymnastics_corner` only requires config changes
- [ ] `generate.py` still writes the expected output file
- [ ] existing behavior for issue numbering and duplicate avoidance still works
- [ ] tests pass
- [ ] docs reflect the new structure

---

## Recommended Order of Execution

1. Create config files
2. Add loader + validator logic
3. Refactor profile prompt assembly
4. Refactor section prompt assembly
5. Add gymnastics section and config swap support
6. Update tests
7. Run smoke test
8. Update docs
9. Commit in logical chunks if possible

---

## What We Are Deliberately Not Doing Yet

To avoid scope creep, this plan does **not** include:

- switching Claude output to structured JSON
- building an admin panel
- designing a database schema
- adding account/family auth
- building a full theme editor
- changing send/delivery architecture

Those can come later, once the config-driven foundation is in place.

---

## Recommendation

Proceed with this plan as the next implementation step.

It gives us the immediate win, section modularity, while creating a clean bridge to preview tooling, visual config, and future productization.
