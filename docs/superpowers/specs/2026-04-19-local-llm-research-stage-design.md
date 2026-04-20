# Design: Deterministic Brave Research Stage with Pluggable Ranking and Content Providers

**Date:** 2026-04-19  
**Status:** Draft

---

## Overview

Add a new generation mode for Sophie's World where:

1. the app performs deterministic research itself using the Brave Web Search API
2. the app filters and normalizes raw retrieval results
3. a pluggable ranker selects the best candidate set per section
4. the app feeds the resulting research packet into a content provider, which may be either local or hosted
5. the existing local render stage turns the issue artifact into final HTML

This design intentionally separates:

- retrieval
- ranking/reranking
- synthesis
- rendering

The near-term goal is not to build a general-purpose agent. The goal is to make Sophie's World compatible with both local and hosted models while preserving:

- predictable retrieval behavior
- debuggable ranking behavior
- section-level control
- provider portability
- compatibility with the existing content/render split

In short:

```text
Brave search and retrieval in app code
+ pluggable ranker
+ hosted or local model for synthesis/writing
= simpler, cheaper, and easier-to-debug generation path
```

This means the deterministic research packet is not only a path to local models. It is also a useful intermediate mode for hosted providers such as Claude, where we want to compare:

- hosted provider with integrated search behavior
- hosted provider with deterministic retrieval + heuristic ranking
- hosted provider with deterministic retrieval + model-based reranking
- local provider with deterministic retrieval + reranking

That comparison path is a first-class goal of the design.

---

## Problem Statement

Today, Sophie's World content generation depends on Claude CLI with integrated search/fetch behavior inside the model call.

That has worked well enough to prove the product, but it creates limitations if we want to move toward a more modular system:

- local models are generally worse at autonomous tool use than hosted frontier models
- even hosted tool-calling hides too much behavior when debugging quality problems
- debugging “why did it search for that?” becomes much harder when search planning is implicit in model reasoning
- ranking and story selection are bundled into the writing pass, which makes provider comparisons muddy
- the app currently lacks explicit retrieval and ranking layers that can be inspected, tuned, replayed, or reused across providers

If we naively replace Claude with a local tool-calling model, we risk trading one dependency for a much more fragile pipeline.

If we keep hosted search and ranking implicit forever, we lose a valuable opportunity to evaluate writing providers on the same factual input packet.

If we lock ranking permanently to heuristics, we risk capping quality because a downstream model can only work with what survives the heuristic shortlist.

---

## Goals

### Immediate goals

- add a deterministic research stage using Brave Web Search API
- separate retrieval filtering from ranking
- support a pluggable ranker abstraction
- start with a heuristic ranker as the default implementation
- pass a compact structured research packet into the content stage
- support both local and hosted content providers consuming that same packet
- preserve the current structured content artifact -> local render pipeline

### Near-term goals

- support a local-model content provider without requiring autonomous tool use from the model
- support a hosted-model content provider using deterministic research packet input
- support a model-based reranker later without changing retrieval or synthesis contracts
- make retrieval and ranking behavior inspectable, replayable, and testable
- reduce cost and improve privacy by moving more generation work local where it makes sense

### Explicit non-goals for the first phase

- no fully autonomous local agent loop yet
- no requirement that the model decide search queries on its own
- no requirement to replace Claude immediately
- no vector database or embedding retrieval layer yet
- no requirement to fetch and summarize the entire web corpus dynamically during generation

---

## Core Design Principle

Separate four responsibilities clearly:

1. **Research planning and retrieval** — deterministic app logic
2. **Ranking/reranking** — pluggable selection layer over retrieved candidates
3. **Selection and synthesis into newsletter content** — content provider responsibility
4. **Final HTML rendering** — deterministic local renderer

This means the content provider, whether local or hosted, is responsible for writing and judgment over a bounded ranked packet, but not for orchestrating search itself.

This also means heuristic ranking is a starting point, not a permanent architectural ceiling.

---

## Why Deterministic Retrieval First

Sophie's World is a structured recurring product, not an open-ended research assistant.

The app already knows:

- which sections are active
- what each section is trying to do
- which sources are preferred
- which topics are recurring
- which recent headlines should be avoided

That makes retrieval planning highly template-able.

For example:

- `world_watch` always needs recent kid-appropriate current events
- `weird_but_true` always needs evergreen surprising facts
- `singapore_spotlight` always needs Singapore-relevant culture/place/history/current-interest items
- `sophies_challenge` usually derives from selected `world_watch` content rather than being researched independently

This structure makes deterministic retrieval planning a better first system than full model-directed search.

It also creates a fairer evaluation setup: multiple ranking providers and writing providers can be compared on the same retrieved input set.

---

## Proposed Pipelines

### Current pipeline

```text
config
-> content provider with embedded search behavior
-> structured issue artifact
-> local renderer
-> HTML
```

### Proposed deterministic pipeline

```text
config + recent issue history
-> research planner
-> Brave Web Search queries
-> retrieval result normalization
-> ranker provider
-> research packet
-> content provider (hosted or local)
-> structured issue artifact
-> local renderer
-> HTML
```

### Supported provider combinations

#### Mode A: hosted provider with integrated search
Current path, retained for comparison and fallback.

#### Mode B: hosted provider with deterministic packet input
The app performs deterministic retrieval and ranking, then sends the bounded packet into Claude or another hosted model.

#### Mode C: local provider with deterministic packet input
The app performs deterministic retrieval and ranking, then sends the bounded packet into a local model.

#### Mode D: deterministic retrieval + heuristic ranker + hosted writer
Recommended early comparison mode.

#### Mode E: deterministic retrieval + model ranker + hosted or local writer
Recommended later experimental mode once the interfaces are stable.

---

## Research Stage Responsibilities

The new research stage should:

- generate search queries per active section
- call Brave Web Search GET API directly
- normalize results into a local result schema
- apply deterministic filtering and deduplication
- hand off filtered candidate pools to a ranker provider
- output a bounded research packet for the content stage
- persist retrieval and ranked artifacts for replay/debugging

The research stage should not:

- write final newsletter copy
- decide final section wording
- produce HTML
- rely on hidden model reasoning for retrieval planning

---

## Why Ranking Should Be Pluggable

Heuristic ranking is a good place to start, but it should not be treated as the permanent end state.

### Why heuristics are still useful

Heuristics are strong at:
- filtering junk
- enforcing source preferences
- enforcing safety constraints
- applying recency windows
- deduplicating obvious overlaps
- keeping cost and latency bounded

### Why heuristics can cap quality

Heuristics are weaker at:
- semantic story salience
- teaching value and explainability
- subtle novelty vs importance tradeoffs
- picking the more child-appropriate framing between similar candidates

If heuristics are the only ranker, the downstream model can only work with what survives the heuristic shortlist.

### Recommended design stance

Treat heuristics as the default **retrieval narrowing** layer, then allow ranking to be upgraded later through a ranker abstraction.

That means the architecture should support:

- `heuristic_ranker`
- `hosted_model_ranker`
- `local_model_ranker`
- potentially `none` for debugging

without changing the rest of the pipeline.

---

## Brave Web Search API Constraints to Design Around

This design should explicitly match the real Brave Web Search GET API behavior.

### Relevant request capabilities

From Brave Web Search GET `/v1/web/search`:

- `q` is required
- query max: 400 characters and 50 words
- `country` supported, default `US`
- `search_lang` supported, default `en`
- `ui_lang` supported, default `en-US`
- `count` max is 20 for web results
- `offset` is page-based, max 9
- `safesearch` supports `off`, `moderate`, `strict`
- `freshness` supports `pd`, `pw`, `pm`, `py`, and explicit date ranges
- `result_filter` can limit response types, including `web`, `news`, `query`, etc.
- `text_decorations` can be controlled
- `spellcheck` can be controlled
- `extra_snippets` can be requested
- `search operators` can be enabled/disabled
- `goggles` exist but are not required for v1

### Design implications

1. Keep queries short and template-driven.
2. Use `count` conservatively, because we do not need huge result sets for each section.
3. Use `freshness` only for sections that are supposed to be current.
4. Explicitly request only relevant result types where practical.
5. Default to `safesearch=strict` or `moderate` for a child-facing product, with a strong bias toward strict.
6. Rely on section-specific source preferences rather than broad open search whenever possible.
7. Do not depend too heavily on search-operator perfection, especially `site:` filtering, because support may be imperfect in practice.

### Cost and quota note

Brave free-tier quota is finite and should be treated as an operational constraint.

At weekly cadence, a section-aware deterministic pipeline is still well within reason, but the app should:

- minimize redundant queries during debugging
- persist retrieval packets so synthesis can be rerun without re-querying Brave
- keep query budgets bounded per section

This makes idempotency and cacheability a product requirement, not a nice-to-have.

---

## Recommended Brave Usage by Section

### World Watch

Use Brave for recent current events.

Recommended defaults:
- `freshness`: `pw` or `pm`
- `safesearch`: `strict`
- `count`: 10-20 across a few queries
- `result_filter`: include `web` and optionally `news` if plan supports it

Example query shapes:
- `site:bbc.co.uk/newsround world news kids`
- `site:timeforkids.com current events kids`
- `site:newsforkids.net world news`
- `major world news for kids April 2026`

### Weird But True

Use Brave mainly for evergreen facts and kid-safe science/animal sources.

Recommended defaults:
- no strict freshness requirement
- `safesearch`: `strict`
- `count`: 5-10 per query

Example query shapes:
- `site:kids.nationalgeographic.com weird animal facts`
- `site:kids.britannica.com surprising science facts`

### Singapore Spotlight

Use Brave for evergreen or timely Singapore-relevant material.

Recommended defaults:
- no hard freshness requirement by default
- `freshness` optional when looking for timely local stories
- `safesearch`: `strict`

Example query shapes:
- `singapore culture for kids`
- `site:visitsingapore.com singapore interesting facts`
- `site:kids.britannica.com singapore`

### USA Corner

Use Brave for California or USA-relevant current-interest content.

Recommended defaults:
- `freshness`: `pw` or `pm` when seeking current stories
- geography-aware query terms like `California`, `Bay Area`, `Fremont`

### Gymnastics Corner

Use Brave for athlete stories, safe basics, and kid-friendly gymnastics content.

Recommended defaults:
- moderate freshness, often `pm`
- source-heavy queries against known domains

### Money Moves

Use Brave mostly for evergreen educational content and kid entrepreneur examples.

Recommended defaults:
- low freshness weighting
- strong source/domain preferences

### Sophie's Challenge

Do not search independently by default.

Instead:
- derive challenge material from selected `world_watch` or `money_moves` content
- only search independently later if the derivation path proves too weak

This section has an explicit downstream dependency and should not be treated as a peer section in independent research planning.

---

## Search Planner Design

The app should introduce a research planner that derives query templates from section config.

### Inputs

- child profile summary
- active sections
- section goals
- section source preferences
- section content rules
- recent headlines to avoid
- issue date
- optional local relevance context (Fremont, California, Singapore)

### Outputs

For each section:
- search queries
- expected freshness window
- domain preferences or boosts
- result-count budget
- ranking profile name
- dependency metadata where relevant

### Principle

The planner should be mostly deterministic and rule-based, not LLM-generated.

---

## Retrieval Filtering and Candidate Pooling

Before ranking, the app should apply a deterministic prefilter layer.

### Purpose

The prefilter layer exists to:
- discard obviously bad results cheaply
- apply source and safety constraints
- enforce freshness windows where required
- deduplicate obvious duplicates
- keep ranker cost bounded

### Important distinction

This stage is not the final semantic judge.
It is the gatekeeper that narrows a noisy web result set into a cleaner candidate pool.

That means:
- raw Brave results may be 20-40 items across several queries
- filtered candidate pool might be 5-10 items per section
- ranker chooses from that bounded pool

This reduces the risk that a model ranker has to reason over junk, while also reducing the risk that the final writer never sees strong candidates.

---

## Ranking and Candidate Selection

The app should support a ranker abstraction over the filtered candidate pool.

### Ranker provider role

The ranker decides which filtered candidates are most worth passing into the content stage.

This should be configurable and swappable.

### Initial default: heuristic ranker

The first implementation should be `heuristic_ranker`.

This keeps the system:
- cheaper
- easier to test
- easier to debug
- less dependent on early model-ranker quality

### Future ranker providers

Planned compatible options:
- `heuristic_ranker`
- `hosted_model_ranker`
- `local_model_ranker`
- `none` for debugging/raw inspection

### Heuristic ranker configuration requirement

The implementation should not hardcode opaque magic numbers directly into ranking logic.

Instead, heuristic rank composition should be:
- explicitly named
- normalized to a documented scale
- configurable via checked-in defaults
- overrideable per section

Recommended config location:

```text
config/research.yaml
```

### Example heuristic scoring components

```text
score =
  source_weight
+ recency_weight
+ keyword_match_weight
+ geography_weight
+ section_fit_weight
- duplicate_penalty
- unsafe_or_low_quality_penalty
```

### Recommended approach to heuristic weights

The spec does not need to freeze exact permanent numeric values, but the implementation must define:

- named weight keys
- default values in config
- per-section override capability
- an explicit rule for how penalties and bonuses combine

Example categories:
- source/domain boost
- freshness boost
- preferred-keyword boost
- kid-safe source boost
- recency penalty for stale results in current sections
- novelty penalty for repeated themes
- junk/unsafe penalty

### Model ranker requirements

A future model ranker should:
- consume only the filtered candidate pool, not raw Brave results
- return structured ranked selections, not prose commentary
- be bounded in candidate count and cost
- preserve source/safety constraints enforced by the deterministic prefilter

This keeps model ranking as an intelligence layer on top of deterministic guardrails, not a replacement for them.

### Novelty comparison requirement

Novelty must be deterministic and explicitly defined at least in the heuristic path.

Minimum design:
- compare against the last `N` issues, where `N` is configured
- source history from prior issue artifacts or final HTML-derived headline index
- normalize titles/snippets before comparison
- compute similarity using a documented string/token heuristic such as normalized token overlap or Jaccard similarity
- penalize results above a configured similarity threshold

This avoids vague “recent headlines to avoid” behavior.

---

## Research Packet Schema

The research stage should emit structured intermediate data per section.

Example:

```json
{
  "issue_date": "2026-04-19",
  "history_window": {
    "issues_considered": 3,
    "similarity_method": "token_jaccard"
  },
  "sections": [
    {
      "section_id": "world_watch",
      "queries": [
        "site:bbc.co.uk/newsround world news kids",
        "site:timeforkids.com current events kids"
      ],
      "ranking_profile": "world_watch_default",
      "filtered_candidates": [
        {
          "title": "Earth Day events ramp up globally",
          "url": "https://...",
          "source": "BBC Newsround",
          "domain": "bbc.co.uk",
          "snippet": "...",
          "published_at": "2026-04-18"
        }
      ],
      "ranked_candidates": [
        {
          "title": "Earth Day events ramp up globally",
          "url": "https://...",
          "source": "BBC Newsround",
          "domain": "bbc.co.uk",
          "snippet": "...",
          "published_at": "2026-04-18",
          "score": 83,
          "reasons": [
            "preferred source",
            "fresh within 7 days",
            "high world_watch keyword match",
            "not similar to recent headlines"
          ]
        }
      ]
    }
  ]
}
```

### Notes

- `reasons` should be machine-generated explanations for debug visibility
- `score` should be included for inspection and regression testing when using heuristic ranking
- packet format should be reusable across both hosted and local providers
- if a model ranker is used later, keep enough traceability to understand what it selected and why

---

## Research Artifact Idempotency and Replay

The research packet should be persisted to:

```text
artifacts/research/
```

This is required so that:
- synthesis can be rerun without repeating Brave API calls
- local model iteration is cheap and fast
- hosted vs local provider comparisons can use the exact same packet
- ranker experiments can be rerun on the same retrieval set
- debugging ranking behavior does not require re-querying the network every time

### Default behavior

Recommended default behavior:
- if today’s research artifact exists, reuse it unless `--refresh-research` or equivalent is requested
- allow synthesis reruns against the cached artifact without repeating research
- allow reranking against the same filtered candidate pool without repeating research
- allow regeneration of only the synthesis stage when experimenting with providers

This should be treated as a first-class product workflow, not a temporary debug hack.

---

## Content Stage Changes

The content stage should support a packet-driven provider mode where the prompt includes:

- child summary
- editorial defaults
- section summaries
- ranked research packet shortlist per section
- strict output schema

In this mode, the content provider should not be asked to search the web directly.

Instead, it should:
- select from ranked candidates
- combine and synthesize candidate material
- produce final structured issue JSON
- create lively `render_title` and `section_intro`
- preserve age-appropriate voice and reading level

### Reliability contract

The content stage boundary must include:

- schema validation of returned issue JSON
- bounded retry behavior on invalid output
- failure artifact capture for debugging
- explicit fallback behavior when a provider repeatedly fails

Recommended first-pass policy:
- validate against issue schema immediately after parse
- allow 1-2 retries for invalid JSON or schema-invalid output
- if retries fail, either surface a hard error or fall back to a configured provider

This must be part of the design, because valid JSON generation is a known weak point for many local models.

---

## Provider Abstraction

The app should support four conceptual provider surfaces:

1. **Research provider**
2. **Ranker provider**
3. **Content provider**
4. **Render provider**

### Research provider interface

Conceptual contract:

```text
plan_research(issue_context, config) -> ResearchPlan
run_research(plan) -> RetrievedCandidatePool
```

### Ranker provider interface

Conceptual contract:

```text
rank_candidates(retrieved_pool, issue_context, config) -> ResearchPacket
```

### Content provider interface

Conceptual contract:

```text
generate_issue(content_input) -> IssueArtifact
```

Where `content_input` may be either:
- direct app context with integrated provider-side search, or
- deterministic ranked research packet input

### Render provider interface

Conceptual contract:

```text
render_issue(issue_artifact, template_context) -> html
```

### Supported content modes

- `hosted_integrated_search`
- `hosted_packet_synthesis`
- `local_packet_synthesis`

### Supported ranker modes

- `heuristic_ranker`
- `hosted_model_ranker`
- `local_model_ranker`
- `none`

This makes ranking a first-class design surface rather than an implementation detail.

---

## Generation Config Placement

A generation config block is needed.

Recommended home:
- `config/children/sophie.yaml` under `newsletter.generation`

Example:

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

This keeps generation mode tied to the child/newsletter profile rather than introducing a disconnected global file too early.

---

## Local Model Requirements

A local writer model does not need to be a best-in-class autonomous tool user.

It does need to be good enough at:

- synthesizing structured inputs
- following output schema constraints
- producing valid JSON reliably enough for bounded retry to be practical
- writing clearly for roughly 4th-grade reading level
- generating section-level editorial polish

A local ranker model, if used later, needs a different capability set:

- semantic comparison across bounded candidate sets
- structured ranking output
- stable adherence to ranking schema
- lower cost than using the full writer model for ranking if possible

This reinforces that ranking and writing may eventually use different models.

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
    local_llm_provider.py
    hosted_llm_provider.py
```

Potential artifacts:

```text
artifacts/
  research/
    sophie-2026-04-19.json
  issues/
    sophie-2026-04-19.json
```

---

## Phase Plan

### Phase 1: Deterministic retrieval + heuristic ranking

- add Brave client wrapper
- add section-aware search planner
- add deterministic filtering and deduplication
- add heuristic ranker with config-backed weights
- add novelty comparison over recent issue history
- store research packet artifact
- add retry/backoff behavior for Brave API failures
- keep existing hosted-integrated-search path available

### Phase 2: Packet-driven hosted synthesis

- add hosted packet-synthesis mode
- feed ranked research packet into Claude or another hosted provider
- compare quality against hosted integrated-search path
- tune packet format and ranking profiles

### Phase 3: Local packet synthesis

- add local content provider interface
- feed the same ranked research packet into local content prompt
- compare output quality against hosted packet-synthesis
- tune candidate packet size and prompt format
- enforce schema validation + retry + fallback behavior

### Phase 4: Model-based reranking

- add hosted or local model ranker behind the ranker abstraction
- compare model reranking against heuristic ranker on the same retrieved pools
- keep deterministic prefilter guardrails in front of the model ranker
- persist reranked packet traces for debugging

### Phase 5: Optional bounded refinement loop

- allow provider to request one additional query for a section
- define a structured request field, not freeform chatter
- enforce one and only one refinement query at the harness level
- persist both original and refined packets for debugging

### Phase 6: Optional autonomous local tools

- only if needed, add full tool-calling local harness
- treat this as an experiment, not the default path

---

## Bounded Refinement Interface

If the refinement phase is pursued, the refinement loop must be explicitly constrained.

Recommended interface:
- provider returns either a final issue artifact or a structured refinement request
- refinement request includes exactly one query and one target section
- harness validates shape and allows at most one refinement round
- second refinement request is rejected and surfaced as an error

This prevents a quiet slide into unbounded agent loops.

---

## Acceptance Criteria

This design is successful if:

1. the app can build section-level candidate pools using Brave without model-directed search
2. retrieval filtering, ranking, and synthesis are separate stages
3. heuristic ranking is replaceable through a ranker abstraction
4. the same retrieved candidate pool can be fed into multiple rankers and multiple content providers
5. the same ranked research packet can be fed into both hosted and local content providers
6. content-stage schema validation and bounded retry behavior are defined
7. `sophies_challenge` dependency behavior is explicit rather than implicit
8. the local-render path remains unchanged and compatible
9. provider selection remains explicit and pluggable
10. the design respects real Brave API constraints rather than assuming unrestricted search behavior

---

## Risks and Mitigations

### Risk: deterministic retrieval misses good stories
Mitigation:
- use multiple query templates per section
- support section-specific tuning
- later allow one bounded refinement query from the provider

### Risk: heuristic ranking is too dumb
Mitigation:
- keep ranking pluggable
- store scores and reasons for inspection
- tune weights via checked-in config
- add model reranking later over the filtered pool if needed

### Risk: model ranker becomes expensive or unstable
Mitigation:
- keep deterministic prefilter guardrails
- only rank bounded candidate pools
- preserve heuristic ranker as default fallback

### Risk: novelty checks are inconsistent
Mitigation:
- define history window, normalization, and similarity metric explicitly
- source history from persisted artifacts

### Risk: local or hosted packet-synthesis provider returns invalid JSON
Mitigation:
- validate at the content-stage boundary
- retry in bounded fashion
- keep configured fallback path
- persist failure artifacts for debugging

### Risk: Brave snippets are insufficient for some stories
Mitigation:
- add optional fetch/excerpt enrichment for top candidates later
- keep v1 packet bounded and simple

### Risk: Brave API failures or quota exhaustion interrupt generation
Mitigation:
- add retry/backoff on transient failures
- cache research artifacts
- support rerun against cached packets
- retain hosted integrated-search fallback if needed

### Risk: prompt becomes too large again
Mitigation:
- cap candidate count per section
- pass summaries, not full raw pages
- keep ranking and writing focused on bounded packets rather than raw retrieval

---

## Alternatives Considered

### 1. Full local tool-calling agent first
Rejected for v1 because it is more fragile, harder to debug, and more model-sensitive.

### 2. Replace Claude with a local model but keep search implicit in the model
Rejected for v1 because local models are less reliable at autonomous search orchestration.

### 3. Do no explicit retrieval stage and rely on non-search model memory
Rejected because the newsletter depends on timely and accurate external information.

### 4. Use deterministic retrieval and ranking only for local models
Rejected because hosted packet-synthesis and reranker comparisons are too valuable for apples-to-apples debugging and evaluation.

### 5. Let model ranking replace deterministic filtering entirely
Rejected because deterministic filtering is still valuable for source quality, safety, deduplication, and cost control.

---

## Recommendation

Proceed with a deterministic Brave-powered retrieval stage before attempting full tool-calling.

Short version:

- let the app plan and execute search
- filter and dedupe candidates deterministically
- start with a heuristic ranker, but make ranking pluggable from day one
- cache research artifacts for replay
- allow both hosted and local providers to synthesize from the same ranked packet
- validate and retry content output at the schema boundary
- keep rendering deterministic and local
- add model-based reranking later if heuristic ranking proves to be the bottleneck
- add bounded refinement only after the packet-driven path is working well

This gives Sophie's World the best chance of shipping a practical, inspectable generation path without turning the product into an agent-debugging hobby project.
