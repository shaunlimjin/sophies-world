# Plan: Split Newsletter Generation into Content Stage + Render Stage

**Date:** 2026-04-18  
**Status:** Approved
**Spec:** `docs/superpowers/specs/2026-04-18-content-render-split-design.md`

---

## Goal

Refactor Sophie's World from a single-step Claude-to-HTML pipeline into a two-stage architecture:

1. a **content stage** that researches and writes structured newsletter content
2. a **render stage** that turns structured content into deterministic HTML using local code

The implementation goal is to make experimentation with multiple content models easier while making HTML rendering more reliable and testable.

---

## Scope for This Plan

### In scope

- define and implement a structured intermediate newsletter artifact
- keep Claude as the initial content provider
- add a local Python HTML renderer as the render provider
- refactor `generate.py` into orchestration logic for the two-stage flow
- persist structured issue artifacts for debugging and future preview/edit flows
- add tests for intermediate content and renderer behavior
- update docs to match the new architecture

### Out of scope

- no admin UI yet
- no visual editor yet
- no database yet
- no new external content providers in the first pass
- no send pipeline redesign beyond consuming the new final HTML output

---

## Deliverables

### Code

- updated `scripts/generate.py` as orchestration entry point
- one or more helper modules for:
  - content-stage orchestration
  - intermediate issue schema handling
  - local HTML rendering
- new structured issue artifact output path
- deterministic local renderer for current section block types

### Artifacts / data

- structured issue JSON files, likely under a dedicated artifact directory

### Tests

- unit tests for structured artifact generation shape
- unit tests for renderer output by block type
- integration-style tests for content artifact -> final HTML path
- retained tests for existing send logic where still relevant

### Docs

- approved spec
- this implementation plan
- updated README and/or CLAUDE.md
- backlog updates if implementation reveals new next steps

---

## Implementation Strategy

Do this as a staged migration, not a rewrite-in-place.

The safest path is:

1. define the intermediate schema first
2. make the current generator produce structured content
3. add a local renderer that can consume it
4. keep output HTML compatible with the current send flow
5. only then consider provider experimentation later

This keeps the system working while the internal architecture improves.

---

## Phase Breakdown

### Phase 1: Define the structured intermediate issue format

#### Tasks

1. Define the Python-side schema/shape for a generated issue
2. Represent:
   - issue metadata
   - child metadata reference
   - theme reference
   - editorial defaults snapshot
   - ordered section list
   - section item content
   - links
   - footer content
3. Choose an artifact location, for example:
   - `artifacts/issues/`
4. Add helper functions for serializing/deserializing issue JSON

#### Notes

- The schema does not need to be perfect on day one, but it must be explicit and testable
- Use current block types as the starting contract:
  - `fact_list`
  - `story_list`
  - `spotlight`
  - `interest_feature`
  - `challenge`

#### Exit criteria

- There is a documented and code-usable intermediate issue shape
- A structured issue can be written to disk and loaded back reliably

---

### Phase 2: Refactor content generation to output structured content instead of HTML

#### Tasks

1. Replace the current final HTML prompt output requirement with a structured JSON output requirement
2. Update the content-stage prompt so Claude returns:
   - issue metadata
   - ordered sections
   - structured items per section
   - links as data
3. Add parsing and validation for the structured content response
4. Write the structured issue artifact to disk
5. Preserve current config-driven profile/section/theme flow

#### Notes

- Keep Claude as the content provider for this first pass
- Validation should fail clearly if the response is malformed or missing key fields
- The output should be treated as content data, not semi-rendered HTML fragments

#### Exit criteria

- The content stage writes a structured issue artifact successfully
- No final HTML is required from the content-stage model call

---

### Phase 3: Build the deterministic local renderer

#### Tasks

1. Create local render logic for each current block type:
   - `fact_list`
   - `story_list`
   - `spotlight`
   - `interest_feature`
   - `challenge`
2. Use the existing HTML template and adapt it to consume rendered section HTML fragments
3. Render all sections in configured order
4. Render footer from structured data
5. Produce final HTML compatible with the current email/send flow

#### Notes

- Keep rendering logic deterministic and explicit
- Avoid pushing HTML generation back into prompts
- Block-type-specific rendering can be implemented with simple Python string assembly first; no need to overengineer a full templating engine immediately

#### Exit criteria

- Structured issue JSON can be rendered into a full HTML newsletter locally
- Final HTML stays visually compatible with the current design

---

### Phase 4: Integrate the two-stage pipeline into `generate.py`

#### Tasks

1. Make `generate.py` orchestrate:
   - config loading
   - content generation
   - artifact persistence
   - local rendering
   - final HTML write
2. Keep `--test` behavior working
3. Preserve current output file naming and general operator workflow
4. Ensure failures in either stage are surfaced clearly

#### Notes

- This phase is about orchestration, not new functionality
- The user-facing command should remain simple even though the internals become cleaner

#### Exit criteria

- `python3 scripts/generate.py`
  still behaves like the familiar entry point, while using the new internal architecture

---

### Phase 5: Tests and verification

#### Tasks

1. Add tests for structured issue parsing/validation
2. Add tests for block-type renderers
3. Add tests for final HTML containing expected rendered sections
4. Keep regression tests for config loading and section swapping
5. Run the full test suite
6. Run at least one manual `--test` generation smoke test if practical

#### Exit criteria

- The new pipeline is covered well enough to refactor safely later
- The final HTML path is verified, not assumed

---

### Phase 6: Docs cleanup

#### Tasks

1. Update README to explain the two-stage architecture
2. Update CLAUDE.md to reflect:
   - structured content artifact generation
   - local renderer role
   - current provider assumptions
3. Link the approved spec and this plan clearly
4. Update backlog if new obvious follow-ons appear during implementation

#### Exit criteria

- A future reader can understand the new pipeline without reading source first

---

## Proposed Code Direction

Exact filenames can vary, but the implementation should evolve toward something like:

```text
scripts/
  generate.py
  content_stage.py
  render_stage.py
  renderers/
    html_renderer.py
```

And issue artifacts may live under:

```text
artifacts/
  issues/
    sophie-2026-04-18.json
```

If this feels too fragmented, a smaller number of modules is fine, but the conceptual boundaries should stay clear.

---

## Suggested Intermediate Schema (First Pass)

### Top-level fields

```json
{
  "issue_date": "2026-04-18",
  "issue_number": 4,
  "child_id": "sophie",
  "theme_id": "default",
  "editorial": { ... },
  "sections": [ ... ],
  "footer": { ... }
}
```

### Section shape

```json
{
  "id": "world_watch",
  "title": "🌍 World Watch",
  "block_type": "story_list",
  "items": [ ... ]
}
```

### Example item shapes

#### `story_list`

```json
{
  "headline": "...",
  "body": ["paragraph 1", "paragraph 2"],
  "analogy": "...",
  "links": [
    { "label": "BBC Newsround", "url": "https://..." }
  ]
}
```

#### `fact_list`

```json
{
  "title": "...",
  "body": "..."
}
```

#### `interest_feature`

```json
{
  "headline": "...",
  "body": ["..."],
  "links": [
    { "label": "USA Gymnastics", "url": "https://..." }
  ]
}
```

The schema should remain explicit enough that the renderer does not need to guess.

---

## Risks and Mitigations

### Risk: model output is inconsistent JSON

**Mitigation:**
- validate aggressively
- keep schema simple at first
- fail with useful diagnostics
- optionally store raw output for debugging when parsing fails

### Risk: local renderer becomes a mini templating mess

**Mitigation:**
- keep block-type rendering functions small and explicit
- map one block type to one render function
- avoid premature abstraction

### Risk: migration breaks the current operator workflow

**Mitigation:**
- keep `generate.py` as the main entry point
- preserve `--test`
- preserve final HTML output file location

### Risk: structured schema is too loose

**Mitigation:**
- define required fields clearly
- add tests that lock in the shape
- keep data normalized enough for deterministic rendering

---

## Verification Checklist

Before calling this work done:

- [ ] structured issue artifact is generated successfully
- [ ] content stage outputs structured data, not HTML
- [ ] local renderer can render every current block type
- [ ] final HTML matches the configured section set
- [ ] `--test` still works
- [ ] current send flow still has a valid HTML file to consume
- [ ] tests pass
- [ ] docs reflect the new architecture

---

## Recommended Order of Execution

1. define intermediate schema helpers
2. refactor content prompt to produce structured JSON
3. parse and persist structured artifact
4. implement local renderer block by block
5. connect renderer into `generate.py`
6. update tests
7. run smoke test
8. update docs
9. commit in logical chunks if practical

---

## What We Are Deliberately Not Doing Yet

To keep this contained, this plan does **not** include:

- adding Gemini/OpenAI provider integrations yet
- building provider comparison tooling yet
- building a preview UI yet
- editing structured issue artifacts through a UI yet
- redesigning the send stage

Those become much easier after this foundation lands.

---

## Recommendation

Proceed with the two-stage migration using:

- Claude as the first content provider
- structured issue JSON as the intermediate representation
- local Python rendering as the final HTML render path

That gets the architecture into the right shape first. After that, model experimentation becomes much easier and much less messy.
