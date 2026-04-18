# Design: Modular Newsletter Sections + Config-Driven Profiles

**Date:** 2026-04-18  
**Status:** Approved

---

## Overview

Refactor Sophie's World from a hardcoded single-child newsletter generator into a config-driven architecture where newsletter sections, child profiles, and visual theme choices are defined as data.

This change is intended to solve two immediate needs:

1. Allow sections to be swapped in and out as a child’s interests change, for example replacing `K-pop Corner` with `Gymnastics Corner`
2. Prepare the codebase for future evolution into:
   - a lightweight admin/config UI
   - a more visual newsletter assembly workflow
   - a multi-family product, not just a Sophie-specific script

The immediate implementation should remain simple and script-friendly. We are not building the full dashboard now. We are designing the data model and generation flow so that future UI and productization work are straightforward instead of requiring a rewrite.

---

## Problem Statement

Today, section definitions and newsletter behavior are embedded directly inside `scripts/generate.py` and tightly coupled to one static HTML template. This creates several problems:

- Section logic is hardcoded into prompt text
- Swapping sections requires code edits instead of config edits
- Sophie-specific assumptions are mixed directly into application logic
- The current architecture assumes one newsletter flavor, one child, and one fixed set of sections
- A future admin UI would have no clean data layer to edit
- Productizing for other families would require untangling Sophie-specific logic from the core app

In short, the current version is a good v1 script but a poor foundation for configurable newsletters.

---

## Goals

### Immediate goals

- Make section selection configurable without editing Python code
- Support swapping interest-based sections, for example `kpop_corner` ↔ `gymnastics_corner`
- Move child-specific data out of `generate.py`
- Preserve the existing generate → HTML output flow for now
- Keep the implementation low-complexity and local-file driven

### Near-term goals

- Make it easy to add a simple preview or admin UI later
- Make it easy to support multiple children/families later
- Make the template more configurable without rewriting prompt code
- Reduce hardcoded prompt logic in Python

### Explicit non-goals for this phase

- No full web dashboard yet
- No visual drag-and-drop editor yet
- No database yet
- No multi-user auth system yet
- No complete migration to model-generated structured JSON yet

---

## Product Direction

This refactor should treat the current app as a single-tenant instance of a future multi-tenant product.

That means the design should already think in terms of:

- child profiles
- section catalog entries
- theme/template configuration
- issue instances
- delivery settings

Even if only Sophie exists today, the file and schema shapes should generalize cleanly to additional children later.

---

## Proposed Architecture

### Core principle

Separate:

1. **Profile data** — who the newsletter is for
2. **Section definitions** — what modules can appear in a newsletter
3. **Theme/template configuration** — how content is visually arranged
4. **Generation orchestration** — how the prompt is assembled and Claude is called

### High-level flow

1. Load child profile config
2. Load section catalog config
3. Resolve the active section list for that child
4. Load template/theme metadata
5. Build a prompt dynamically from the selected sections and child context
6. Ask Claude to fill the existing HTML template
7. Write the resulting issue HTML to `newsletters/`

This preserves the current HTML-based output path while removing hardcoded content policy from Python.

---

## Proposed File Structure

```text
sophies-world/
  config/
    children/
      sophie.yaml
    sections.yaml
    themes/
      default.yaml
  docs/
    superpowers/
      specs/
      plans/
  newsletters/
  scripts/
    generate.py
    send.py
    template.html
```

### Notes

- `children/` allows future expansion to multiple children or families
- `sections.yaml` is the section catalog for reusable section definitions
- `themes/default.yaml` holds metadata for ordering and presentation decisions that may later be edited in an admin UI

---

## Configuration Model

### 1. Child profile

A child profile defines the audience and the active newsletter setup.

Example responsibilities:

- name
- reading level / age band
- location
- family/cultural context
- active interests
- inactive interests
- active newsletter sections
- optional recipient/delivery metadata later
- optional sensitivities or banned topics later

Example shape:

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

### 2. Section catalog

The section catalog defines all reusable newsletter modules.

Each section should include:

- stable `id`
- human-readable `title`
- `goal`
- section-specific content rules
- preferred source types
- visual/rendering block type
- link style token
- optional constraints and safety notes

Example shape:

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
      - kid-friendly sports coverage
```

### 3. Theme/template config

The theme config should initially stay lightweight.

Initial responsibilities:

- selected HTML template file
- default section ordering rules
- optional section overrides for labels or card style tokens
- future compatibility with visual theme editing

Example shape:

```yaml
theme_id: default
template_path: scripts/template.html
section_order_mode: profile_driven
```

---

## Rendering Model

### Phase-1 rendering approach

Keep the current HTML-generation model:

- Claude still returns final HTML
- Python still writes the `.html` output file
- The template remains largely unchanged

However, section instructions should no longer be hand-authored directly in `generate.py`. Instead, `generate.py` should assemble section instructions from config.

### Reusable block types

To reduce future rewrite cost, section definitions should reference a reusable visual/content block type rather than implying a totally custom one-off section.

Initial block types:

- `fact_list`
- `story_list`
- `spotlight`
- `interest_feature`
- `challenge`

This allows multiple sections to share layout patterns.

For example:

- `kpop_corner` and `gymnastics_corner` can both use `interest_feature`
- `weird_but_true` can use `fact_list`
- `world_watch` can use `story_list`

---

## Prompt Assembly Changes

`generate.py` should stop embedding the full newsletter spec inline as hardcoded prose and instead build prompt sections from config.

Prompt inputs should include:

- child profile summary
- active section list
- section-by-section rules from the catalog
- theme/template metadata
- previous issue headlines to avoid repetition
- date / issue number context

The prompt should still instruct Claude to output final HTML directly in this phase.

---

## Future Admin UI Implications

This design should make an eventual admin/config UI straightforward.

Potential future UI capabilities supported by this data model:

- toggle sections on/off
- reorder sections visually
- switch child interests
- swap themes
- preview a generated issue
- edit section labels or descriptions
- create new child profiles

Without this config layer, a UI would have to edit prompt text and code, which is brittle and ugly.

---

## Future Productization Implications

This design also supports future productization for other families.

### What should become reusable product entities later

- family/account
- child profile
- newsletter issue
- section catalog entry
- theme/template
- delivery settings

### Why that matters now

Even if we are storing everything in local YAML files for now, those same entities could later map to database tables or API resources with minimal conceptual changes.

That means this phase should avoid Sophie-specific naming or assumptions in core logic wherever practical.

---

## Migration Strategy

### Phase 1, this work

- Add config files for children, sections, and theme
- Refactor `generate.py` to read from config
- Introduce one concrete interchangeable section example:
  - `kpop_corner`
  - `gymnastics_corner`
- Preserve the existing newsletter template and output approach

### Phase 2, later

- Move Claude output from raw HTML toward structured section data
- Render HTML locally from structured content
- Add validation and preview tooling

### Phase 3, later

- Add lightweight admin UI / config panel
- Add multi-child and multi-family support in a more formal product shell

---

## Acceptance Criteria

This design is successful if:

1. A non-code config change can replace `kpop_corner` with `gymnastics_corner`
2. `generate.py` no longer hardcodes the newsletter’s full section logic inline
3. Sophie-specific profile details live outside Python code
4. The generated issue flow still works end-to-end with the existing scripts
5. The file and schema layout could reasonably support future UI and multi-family expansion

---

## Tradeoffs

### Benefits

- Faster section swaps
- Cleaner separation of concerns
- Better product foundation
- Easier future preview/admin tooling
- Less brittle than hardcoded prompt prose

### Costs

- More config files to manage
- Slightly more complex generation path
- Some prompt complexity moves from code constants into config assembly
- Still not as clean long-term as structured content generation

---

## Alternatives Considered

### 1. Keep everything hardcoded and just add a few flags

Rejected because it solves today’s swap problem but does not support UI/product evolution well.

### 2. Fully migrate to structured JSON output now

Deferred because it is the better long-term architecture, but likely too large a refactor for the immediate need.

### 3. Add a dashboard first

Rejected because a UI without a clean underlying config/data model would just be a prettier way to edit technical debt.

---

## Recommendation

Proceed with a config-driven Phase-1 refactor now.

Specifically:

- use local YAML config files
- define children, sections, and themes as separate config domains
- keep Claude returning HTML for now
- design the data model so future structured-output rendering and admin UI work are natural follow-ons

This gives us the quickest path to modular sections today without building ourselves into a corner tomorrow.
