# Design: Split Newsletter Generation into Content Stage + Render Stage

**Date:** 2026-04-18  
**Status:** Draft

---

## Overview

Refactor Sophie's World from a single-step "model writes final HTML" workflow into a two-stage generation pipeline:

1. **Content stage** — research, select stories, and write structured newsletter content
2. **Render stage** — transform structured content into final HTML using either a second model or a deterministic local renderer

The goal is to make the app easier to evolve in three directions:

- test models other than Claude
- use different models for content generation vs rendering
- reduce dependence on LLMs for deterministic presentation logic over time

This design intentionally separates **content intelligence** from **presentation mechanics**.

---

## Problem Statement

Today, `generate.py` does all of the following through one Claude invocation:

- researches current events and section content
- writes the newsletter copy
- chooses link placement
- fills the HTML template directly
- returns final HTML as the only output artifact

That coupling creates several issues:

- difficult to swap models for only one part of the pipeline
- difficult to compare content quality independently from rendering quality
- brittle HTML output path because template filling is still LLM-driven
- no structured intermediate representation to validate, inspect, or edit
- future preview/dashboard/editor work has no clean data layer to operate on

In short, the current pipeline fuses creative work and mechanical rendering into one opaque step.

---

## Goals

### Immediate goals

- define a clean two-stage generation architecture
- introduce a structured intermediate representation for newsletter content
- make content generation provider-pluggable
- make render stage provider-pluggable
- support a future deterministic local HTML renderer

### Near-term goals

- allow one model for research/writing and another for rendering
- make side-by-side provider experiments easier
- make preview, validation, and editing workflows possible
- improve rendering reliability by shrinking LLM responsibility for final markup

### Non-goals for the first implementation phase

- no full admin dashboard yet
- no visual editor yet
- no database yet
- no complete multi-user product shell yet
- no requirement to remove Claude immediately

---

## Core Design Principle

Separate these concerns explicitly:

1. **Research + writing** — creative, probabilistic, content-heavy
2. **Rendering** — structured, repeatable, mechanical

LLMs are useful for the first category.
Code is usually better for the second.

---

## Proposed Pipeline

### Current pipeline

```text
config + template -> Claude -> final HTML
```

### Target pipeline

```text
config + template metadata
        -> content provider
        -> structured newsletter content
        -> render provider
        -> final HTML
```

### Recommended end-state pipeline

```text
config + template metadata
        -> content provider (LLM)
        -> structured newsletter content (JSON)
        -> local renderer (Python)
        -> final HTML
```

---

## Stage 1: Content Generation

### Responsibility

The content stage should:

- research current stories and facts
- choose section content based on active section config
- write age-appropriate copy
- suggest links and source attributions
- return structured content for each section

### Output format

The content stage should output structured JSON, not HTML.

Example shape:

```json
{
  "issue_date": "2026-04-18",
  "issue_number": 4,
  "child_id": "sophie",
  "theme_id": "default",
  "editorial": {
    "reading_level": "4th grade",
    "tone": ["warm", "fun", "curious"],
    "use_emojis": true
  },
  "sections": [
    {
      "id": "world_watch",
      "title": "🌍 World Watch",
      "block_type": "story_list",
      "items": [
        {
          "headline": "...",
          "body": ["...", "..."],
          "analogy": "...",
          "links": [
            { "label": "BBC Newsround", "url": "https://..." }
          ]
        }
      ]
    },
    {
      "id": "gymnastics_corner",
      "title": "🤸 Gymnastics Corner",
      "block_type": "interest_feature",
      "items": [
        {
          "headline": "...",
          "body": ["..."],
          "links": [
            { "label": "USA Gymnastics", "url": "https://..." }
          ]
        }
      ]
    }
  ],
  "footer": {
    "tagline": "Made with love by Dad & Claude 🤖❤️",
    "location_line": "Fremont, California ↔ Singapore"
  }
}
```

### Notes

- exact schema can evolve, but it must be structured and explicit
- every section should include its `id` and `block_type`
- links should be data, not pre-rendered HTML
- body copy should be broken into explicit fields rather than one giant blob where useful

---

## Stage 2: Rendering

### Responsibility

The render stage should:

- accept structured content
- validate required fields per section/block type
- map structured content into HTML
- preserve template/theme consistency
- output deterministic final HTML

### Provider options

#### Option A: second model renderer

A model receives structured content and produces HTML.

**Pros**
- fast to prototype
- low engineering cost initially

**Cons**
- still probabilistic
- can drift from template rules
- weaker guarantee of valid markup

#### Option B: local Python renderer (recommended)

Python code renders final HTML from structured content.

**Pros**
- deterministic
- testable
- easier to validate
- safer and cheaper in the long run

**Cons**
- more implementation work up front
- requires explicit render logic per block type

### Recommendation

Use Option A only as an intermediate step if needed.
Design toward Option B as the intended destination.

---

## Provider Abstraction

Introduce explicit generation providers.

Example config shape:

```yaml
generation:
  content_provider: claude
  render_provider: local_renderer
```

Possible future values:

- `claude`
- `openai`
- `gemini`
- `local_renderer`
- `mock`

### Why this matters

This makes experimentation a config decision, not a code fork.

Examples:

```yaml
generation:
  content_provider: claude
  render_provider: claude
```

```yaml
generation:
  content_provider: gemini
  render_provider: local_renderer
```

```yaml
generation:
  content_provider: openai
  render_provider: local_renderer
```

---

## Proposed File / Module Direction

This spec does not force the final exact filenames, but the codebase should evolve toward something like:

```text
scripts/
  generate.py              # orchestration entry point
  content_stage.py         # content provider orchestration
  render_stage.py          # render provider orchestration
  renderers/
    html_renderer.py       # deterministic local HTML renderer
  providers/
    claude_provider.py
    gemini_provider.py
    openai_provider.py
```

And intermediate data may live temporarily in:

```text
artifacts/
  issues/
    sophie-2026-04-18.json
```

for inspection/debugging.

---

## Structured Intermediate Representation

This is the key enabling layer.

Without structured content, model A and model B are still loosely coupled through prose, which means the system is not truly modular.

The intermediate representation should support:

- inspection by humans
- validation by code
- preview before render/send
- later UI editing
- regression tests on content shape

This intermediate artifact is the bridge to future productization.

---

## Validation Requirements

The system should eventually validate:

- all required sections exist
- each section matches its expected block shape
- links are present where required
- challenge section references World Watch when required
- footer fields are present
- output content is structurally renderable before final send

This becomes much easier once content is structured.

---

## Product / Admin UI Implications

This split strongly supports future UI work.

Once structured content exists, an admin UI can:

- preview the generated issue before send
- edit section copy without touching HTML
- reorder sections
- swap themes/templates
- compare outputs from different content providers
- re-render the same content through different templates

That is much harder when HTML is the only artifact.

---

## Experimentation Benefits

This architecture will allow experiments like:

- Claude for content, Python renderer for HTML
- Gemini for content, Python renderer for HTML
- Claude for content, Claude for rendering
- OpenAI for content, Claude for rendering
- local model for content drafting, stronger hosted model for refinement

It also allows A/B testing on:

- content quality
- factuality
- reading-level fit
- rendering stability
- cost and latency

---

## Migration Strategy

### Phase 1

- define the structured intermediate schema
- keep Claude as the content provider
- optionally keep Claude as the render provider at first
- persist structured issue artifacts for debugging

### Phase 2

- add deterministic local renderer for existing block types
- switch render provider from model-based to local code

### Phase 3

- introduce additional content providers
- add provider selection via config
- support provider comparison workflows

### Phase 4

- build preview/editor/admin tools on top of structured issue artifacts

---

## Acceptance Criteria

This design is successful if:

1. content generation and rendering become separate stages
2. the handoff between stages is structured data, not raw prose or raw HTML
3. the system can eventually swap content providers without rewriting render logic
4. the system can eventually swap render providers without rewriting content logic
5. the architecture clearly supports a deterministic local HTML renderer

---

## Tradeoffs

### Benefits

- cleaner separation of concerns
- easier model experimentation
- more reliable rendering path
- better future support for preview/edit tooling
- stronger product foundation

### Costs

- more moving pieces
- more explicit schema work
- some short-term complexity while migrating
- need for render logic per block type

---

## Alternatives Considered

### 1. Keep current single-model HTML generation and just add provider flags

Rejected because it preserves the fused architecture and makes experimentation shallow.

### 2. Add multiple content providers before introducing structured output

Rejected because provider-swapping without structured handoff would still be brittle and messy.

### 3. Jump straight to full UI/editor product work

Rejected because the structured content layer should exist first.

---

## Recommendation

Proceed with the two-stage architecture.

Short version:

- use an LLM for content generation
- use structured intermediate content as the handoff
- design toward a deterministic local renderer for final HTML
- make providers configurable so model experiments become easy later

That gives Sophie's World a cleaner technical core and sets up the next generation of the product properly.
