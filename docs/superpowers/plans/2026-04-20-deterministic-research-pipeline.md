# Plan: Deterministic Brave Research Pipeline with Heuristic and Model Ranking Experiments

**Date:** 2026-04-20  
**Status:** Draft  
**Spec:** `docs/superpowers/specs/2026-04-19-local-llm-research-stage-design.md`

---

## Goal

Implement a packet-driven generation pipeline for Sophie's World that separates:

1. deterministic Brave-based retrieval
2. pluggable ranking/reranking
3. content synthesis
4. deterministic local rendering

The first implementation goal is not to ship local models immediately.

The first implementation goal is to build a clean comparison harness across these modes:

1. **Mode A**: hosted provider with integrated search (current path)
2. **Mode B1**: deterministic retrieval + heuristic ranking + hosted packet synthesis
3. **Mode B2**: deterministic retrieval + heuristic prefilter + model-based ranking + hosted packet synthesis

That sequence gives us a sanity check before local-model work:

- does deterministic retrieval preserve or improve quality vs the current path?
- how much does heuristic-only ranking cap output quality?
- does model reranking recover meaningful quality on top of deterministic retrieval?

Only after those answers are clear should we move to local packet synthesis.

---

## Scope for This Plan

### In scope

- add deterministic Brave retrieval as a distinct stage
- add research artifact persistence and replay
- add deterministic prefiltering and heuristic ranking
- add ranker abstraction
- add hosted packet-synthesis mode using the same research packet
- add model-ranker mode for hosted reranking experiments
- add comparison-friendly orchestration in `generate.py`
- add tests and docs for the new pipeline

### Out of scope

- no local writer model implementation in this plan
- no full autonomous tool-calling loop
- no admin UI yet
- no dashboard for experiment comparison yet
- no send pipeline redesign beyond consuming final HTML output

---

## Success Criteria

This plan is successful if we can answer, with evidence:

1. whether Mode B1 produces acceptable newsletters compared with Mode A
2. whether Mode B2 improves on B1 enough to justify added complexity
3. whether retrieval, ranking, and synthesis are modular enough to support later local-provider work without major redesign

---

## Deliverables

### Code

- `scripts/research_stage.py`
- `scripts/ranking_stage.py`
- Brave API client wrapper
- heuristic ranker implementation
- hosted packet-synthesis content path
- hosted model-ranker path
- updates to `scripts/generate.py` for mode selection and replay

### Config

- generation mode configuration in `config/children/sophie.yaml`
- checked-in retrieval/ranking configuration, likely `config/research.yaml`

### Artifacts

- persisted research packets under `artifacts/research/`
- persisted issue artifacts under `artifacts/issues/`

### Tests

- retrieval normalization tests
- deterministic prefilter/ranking tests
- novelty comparison tests
- packet-driven content path tests
- integration-style tests across Mode A / B1 / B2 boundaries where practical

### Docs

- approved spec
- this implementation plan
- updated README / CLAUDE.md as implementation lands

---

## Recommended Execution Order

Implement this in the same order we want to evaluate it:

1. keep Mode A intact as baseline
2. build deterministic retrieval + heuristic ranking (B1)
3. compare A vs B1 on real sample issues
4. add model-ranker layer (B2)
5. compare B1 vs B2 on the same retrieval sets
6. only then decide whether local packet synthesis is worth prioritizing next

That prevents us from jumping to local-model debugging before we know whether the retrieval/ranking structure is sound.

---

## Phase Breakdown

### Phase 0: Lock the baseline and comparison harness

#### Tasks

1. Treat current path as explicit `Mode A`
2. Add config support for generation mode selection without changing default behavior
3. Define what outputs we will compare across modes:
   - final HTML
   - issue artifact JSON
   - section-level content quality
   - runtime and operational friction
4. Define a small evaluation set, for example 3-5 issue runs across different dates/topics if possible

#### Notes

- We do not need a fancy eval framework yet
- We do need repeatable inputs and saved outputs
- Mode A must remain runnable as the control

#### Exit criteria

- Mode A is preserved and explicitly named in code/docs
- We have a clear experiment sequence for A vs B1 vs B2

---

### Phase 1: Add research-stage scaffolding and artifact persistence

#### Tasks

1. Create `scripts/research_stage.py`
2. Define the research packet schema in code
3. Create helper functions to:
   - build research artifact paths
   - write/read research packets
   - distinguish retrieval output from ranked output if needed
4. Add default artifact location:
   - `artifacts/research/`
5. Add idempotent behavior:
   - reuse existing research packet unless refresh is requested

#### Notes

- This phase is mostly plumbing
- The point is to make packet-driven iteration cheap before Brave logic arrives

#### Exit criteria

- research packets can be written and read reliably
- generation flow can reuse an existing research artifact

---

### Phase 2: Implement deterministic Brave retrieval

#### Tasks

1. Add Brave Web Search client wrapper
2. Support the required request fields:
   - `q`
   - `count`
   - `freshness`
   - `safesearch`
   - `result_filter`
   - optional locale fields
3. Normalize Brave results into a local retrieval schema
4. Add retry/backoff handling for transient API failures
5. Add section-aware query planning from config
6. Respect section budgets so query counts stay bounded

#### Notes

- Keep queries template-driven and short
- Do not overengineer query generation yet
- Normalize enough result metadata for ranking later:
   - title
   - url
   - domain
   - snippet
   - published date when available
   - query source

#### Exit criteria

- a research stage can produce deterministic retrieved candidate pools per section
- Brave failures are surfaced clearly and retried sanely

---

### Phase 3: Add deterministic prefiltering and heuristic ranking (Mode B1 foundation)

#### Tasks

1. Create `scripts/ranking_stage.py`
2. Add deterministic prefilter logic for:
   - source quality allow/deny
   - safety filtering
   - freshness window enforcement
   - cheap deduplication
3. Add heuristic ranker implementation
4. Add config-backed ranking weights in `config/research.yaml`
5. Add novelty comparison over recent issue history
6. Emit ranked candidate lists with scores and reasons

#### Notes

- This phase should produce the first usable Mode B1 packet
- Prefiltering and ranking should be separate in code, even if housed in one file initially

#### Exit criteria

- the app can build a ranked research packet without any model involvement
- ranking weights live in checked-in config rather than hardcoded magic constants

---

### Phase 4: Add hosted packet-synthesis mode (Mode B1)

#### Tasks

1. Extend `content_stage.py` to accept a ranked research packet as input
2. Add hosted packet-synthesis provider mode, likely reusing Claude CLI first
3. Ensure packet-driven prompt shape is explicit and bounded
4. Validate packet-synthesis output against issue schema
5. Add bounded retry behavior for invalid JSON/schema failures
6. Preserve current local render stage unchanged

#### Notes

- This is the first real comparison point against Mode A
- The provider here is still hosted, which isolates the retrieval/ranking change from local-model variables

#### Exit criteria

- Mode B1 can run end-to-end:
  - deterministic retrieval
  - heuristic ranking
  - hosted packet synthesis
  - local render

---

### Phase 5: Compare Mode A vs Mode B1

#### Tasks

1. Run a small comparison set between:
   - Mode A
   - Mode B1
2. Save outputs for review
3. Compare on practical dimensions:
   - factual adequacy
   - story selection quality
   - Sophie fit / kid-friendliness
   - section variety / novelty
   - operational reliability
   - latency / cost roughness
4. Note whether deterministic retrieval appears obviously harmful, neutral, or helpful

#### Notes

- This phase is deliberately qualitative first
- We want signal, not fake precision

#### Exit criteria

- we can answer whether deterministic retrieval + heuristic ranking is a viable foundation

---

### Phase 6: Add model-ranker abstraction and hosted model reranking (Mode B2)

#### Tasks

1. Formalize ranker provider abstraction in code
2. Keep `heuristic_ranker` as the default implementation
3. Add `hosted_model_ranker` provider
4. Feed only filtered candidate pools into the model ranker, not raw Brave results
5. Require structured ranking output from the model ranker
6. Persist reranked packet traces for debugging and replay

#### Notes

- The model ranker is an intelligence layer, not a replacement for deterministic filtering
- Keep it bounded in candidate count and token use

#### Exit criteria

- Mode B2 can run end-to-end:
  - deterministic retrieval
  - deterministic prefilter
  - model reranking
  - hosted packet synthesis
  - local render

---

### Phase 7: Compare Mode B1 vs Mode B2

#### Tasks

1. Run B1 and B2 on the same retrieved candidate pools
2. Compare whether model reranking materially improves:
   - story selection
   - section delight/teachability
   - novelty balance
   - source choice quality
3. Judge whether gains justify the extra complexity and cost

#### Notes

- This is the crucial ranking decision point
- If B2 barely helps, heuristics may be enough for v1 local-provider work
- If B2 helps a lot, ranking abstraction was the right call

#### Exit criteria

- we can answer whether model reranking deserves to be part of the medium-term architecture

---

### Phase 8: Docs and operational cleanup

#### Tasks

1. Update README with retrieval/ranking/content mode support once implemented
2. Document generation/ranker config placement
3. Document research artifact replay workflow
4. Record experiment outcomes in backlog or follow-up doc

#### Exit criteria

- a future reader can understand the new pipeline and experiment modes without reading all implementation diffs

---

## Proposed Config Direction

### In `config/children/sophie.yaml`

Add generation settings under:

```yaml
newsletter:
  generation:
    research_provider: brave_deterministic
    ranker_provider: heuristic_ranker
    content_provider: hosted_packet_synthesis
    content_model: claude_cli
    render_provider: local_renderer
    fallback_content_provider: hosted_integrated_search
```

### New `config/research.yaml`

Use for:
- query budgets per section
- ranking weight defaults
- per-section ranking profiles
- novelty window settings
- domain boosts / penalties

---

## Proposed Module Direction

```text
scripts/
  generate.py
  research_stage.py
  ranking_stage.py
  content_stage.py
  render_stage.py
  providers/
    brave_search.py
    heuristic_ranker.py
    hosted_llm_provider.py
```

This can stay compact at first, but the conceptual boundaries should remain clear.

---

## Verification Checklist

Before calling this plan complete:

- [ ] Mode A remains runnable and documented as baseline
- [ ] research packets can be persisted and replayed
- [ ] deterministic Brave retrieval works with retries and bounded budgets
- [ ] heuristic ranking works from config-backed weights
- [ ] Mode B1 runs end-to-end successfully
- [ ] A vs B1 comparison outputs are captured and reviewed
- [ ] model-ranker abstraction exists
- [ ] Mode B2 runs end-to-end successfully
- [ ] B1 vs B2 comparison outputs are captured and reviewed
- [ ] docs reflect the new modes and workflow

---

## Risks and Mitigations

### Risk: A vs B1 comparisons are noisy because the writing provider is still stochastic
Mitigation:
- compare multiple runs where practical
- save raw packets and outputs
- focus on obvious directional signal, not fake precision

### Risk: heuristic ranking looks worse simply because retrieval packet shape is bad
Mitigation:
- inspect filtered pools before blaming ranking
- keep retrieval, filtering, and ranking outputs visible separately

### Risk: model ranker grows into a mini-agent
Mitigation:
- require structured rank output only
- do not allow search from the ranker in this plan
- keep ranker bounded to filtered pools

### Risk: local-provider work starts before B1/B2 are understood
Mitigation:
- explicitly gate local packet synthesis after the A/B1/B2 sanity sequence

---

## Recommendation

Proceed in this order:

1. **Mode A baseline**
2. **Mode B1: deterministic retrieval + heuristic ranking + hosted synthesis**
3. **Mode B2: deterministic retrieval + model ranking + hosted synthesis**
4. only then decide how aggressively to pursue local packet synthesis

That sequence is the cleanest way to learn whether deterministic retrieval makes sense, whether heuristic ranking is good enough, and whether model reranking meaningfully improves the system before adding local-model complexity on top.
