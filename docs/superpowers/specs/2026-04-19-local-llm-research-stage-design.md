# Design: Local-LLM Content Generation with Deterministic Brave Research Stage

**Date:** 2026-04-19  
**Status:** Draft

---

## Overview

Add a new generation mode for Sophie's World where:

1. the app performs deterministic research itself using the Brave Web Search API
2. the app builds a structured research packet per section
3. a local LLM running on the Mac mini synthesizes that packet into structured issue JSON
4. the existing local render stage turns the issue artifact into final HTML

This design is intentionally different from a full autonomous tool-calling agent.

The near-term goal is not to build a general-purpose local research agent. The goal is to make Sophie's World compatible with local models while preserving:

- predictable research quality
- debuggable behavior
- section-level control
- provider portability
- compatibility with the existing content/render split

In short:

```text
Brave search and retrieval in app code
+ local model for synthesis/writing
= simpler, cheaper, and easier-to-debug local generation path
```

---

## Problem Statement

Today, Sophie's World content generation depends on Claude CLI with integrated search/fetch behavior inside the model call.

That has worked well enough to prove the product, but it creates limitations if we want to move toward local generation on the Mac mini:

- most local models are worse at autonomous tool use than hosted frontier models
- local tool-calling loops are prompt-sensitive and harder to stabilize
- debugging “why did it search for that?” becomes much harder when search planning is implicit in model reasoning
- hosted-tool assumptions make local provider experiments more coupled than they need to be
- the app currently lacks an explicit research layer that can be inspected, scored, or replayed

If we naively replace Claude with a local tool-calling model, we risk trading one dependency for a much more fragile pipeline.

---

## Goals

### Immediate goals

- support a local-model content provider without requiring autonomous tool use from the model
- add a deterministic research stage using Brave Web Search API
- generate section-level candidate lists using rule-based ranking, not model judgment
- pass a compact structured research packet into the content stage
- preserve the current structured content artifact -> local render pipeline

### Near-term goals

- allow provider selection between hosted content generation and local synthesis
- make research behavior inspectable, replayable, and testable
- reduce cost and improve privacy by moving more generation work local
- support future experimentation with local tool-calling only after the deterministic path works

### Explicit non-goals for the first phase

- no fully autonomous local agent loop yet
- no requirement that the local model decide search queries on its own
- no requirement to replace Claude immediately
- no requirement to fetch and summarize the entire web corpus dynamically during generation
- no vector database or embedding retrieval layer yet

---

## Core Design Principle

Separate three responsibilities clearly:

1. **Research planning and retrieval** — deterministic app logic
2. **Selection and synthesis into newsletter content** — LLM responsibility
3. **Final HTML rendering** — deterministic local renderer

This means the local model is responsible for writing and judgment over a bounded packet, but not for orchestrating search itself.

---

## Why Deterministic Research First

Sophie's World is a structured recurring product, not an open-ended research assistant.

The app already knows:

- which sections are active
- what each section is trying to do
- which sources are preferred
- which topics are recurring
- which recent headlines should be avoided

That makes search planning highly template-able.

For example:

- `world_watch` always needs recent kid-appropriate current events
- `weird_but_true` always needs evergreen surprising facts
- `singapore_spotlight` always needs Singapore-relevant culture/place/history/current-interest items
- `sophies_challenge` can usually be derived from `world_watch` rather than searched independently

This structure makes deterministic search planning a better first system than full model-directed search.

---

## Proposed Pipeline

### Current pipeline

```text
config
-> content provider with embedded search behavior
-> structured issue artifact
-> local renderer
-> HTML
```

### Proposed local-research pipeline

```text
config + recent issue history
-> research planner
-> Brave Web Search queries
-> result scoring and candidate selection
-> research packet
-> content provider (local LLM)
-> structured issue artifact
-> local renderer
-> HTML
```

### Optional later hybrid pipeline

```text
config + recent issue history
-> research planner
-> Brave Web Search queries
-> candidate packet
-> local LLM synthesis
-> optional one-query refinement hook
-> structured issue artifact
-> local renderer
-> HTML
```

---

## Research Stage Responsibilities

The new research stage should:

- generate search queries per active section
- call Brave Web Search GET API directly
- normalize results into a local result schema
- score and rank results with deterministic heuristics
- deduplicate overlapping candidates
- optionally fetch top result pages for richer excerpts later
- output a bounded research packet for the content stage

The research stage should not:

- write final newsletter copy
- decide final section wording
- produce HTML
- rely on hidden model reasoning for ranking

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

1. We should keep queries short and template-driven.
2. We should use `count` conservatively, because we do not need huge result sets for each section.
3. We should use `freshness` only for sections that are supposed to be current.
4. We should explicitly request only relevant result types where practical.
5. We should default to `safesearch=strict` or `moderate` for a child-facing product, with a strong bias toward strict.
6. We should rely on section-specific source preferences rather than broad open search whenever possible.

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
- section-specific ranking profile

### Principle

The planner should be mostly deterministic and rule-based, not LLM-generated.

---

## Result Scoring and Candidate Selection

The app should score Brave results with heuristics rather than model judgment.

### Why

This makes the pipeline:
- cheaper
- easier to test
- easier to debug
- less dependent on local model tool discipline

### Proposed scoring signals

Per result, compute a score from:

- source/domain quality
- recency
- keyword match with section goal and query
- geography fit
- kid-safety / kid-friendliness
- novelty vs recent issue headlines
- duplicate penalty

### Example scoring components

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

### Example deterministic rules

#### Source/domain boost
- preferred domain match: strong positive boost
- known kid-safe source: positive boost
- unknown SEO or junk site: strong penalty

#### Recency
- current-events sections: strong weight
- evergreen sections: weak or zero weight

#### Novelty
- if title/snippet substantially overlaps recent issue headlines: penalize

#### Section fit
- `world_watch`: must be current, explanatory, and broadly relevant
- `weird_but_true`: prefer science/nature/animal novelty
- `spotlight`: prefer one or two vivid culturally/place-relevant items

### Deduplication

After scoring:
- cluster similar results by normalized title similarity and/or URL/topic overlap
- keep the highest-scoring representative(s)
- preserve diversity in the final shortlist

---

## Research Packet Schema

The research stage should emit structured intermediate data per section.

Example:

```json
{
  "issue_date": "2026-04-19",
  "sections": [
    {
      "section_id": "world_watch",
      "queries": [
        "site:bbc.co.uk/newsround world news kids",
        "site:timeforkids.com current events kids"
      ],
      "candidates": [
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
- `score` should be included for inspection and regression testing
- keep candidate count bounded to avoid bloating the model prompt

---

## Content Stage Changes

The content stage should support a new provider mode where the prompt includes:

- child summary
- editorial defaults
- section summaries
- research packet shortlist per section
- strict output schema

In this mode, the content model should not be asked to search the web directly.

Instead, it should:
- select from candidates
- combine and synthesize candidate material
- produce final structured issue JSON
- create lively `render_title` and `section_intro`
- preserve age-appropriate voice and reading level

---

## Local Model Requirements

The local model does not need to be a best-in-class autonomous tool user.

It does need to be good enough at:

- synthesizing structured inputs
- following output schema constraints
- producing valid JSON reliably
- writing clearly for roughly 4th-grade reading level
- generating section-level editorial polish

This lowers the bar for model selection compared with a full tool-calling agent design.

---

## Provider Abstraction

Extend the existing content provider abstraction so Sophie's World can choose between:

- hosted provider with integrated search behavior
- local provider with deterministic research packet input

Example conceptual config:

```yaml
generation:
  research_provider: brave_deterministic
  content_provider: local_ollama
  render_provider: local_renderer
```

Possible future values:
- `brave_deterministic`
- `none`
- `claude_remote`
- `local_ollama`
- `local_openai_compatible`

---

## Proposed Module Direction

```text
scripts/
  generate.py
  research_stage.py
  content_stage.py
  render_stage.py
  providers/
    brave_search.py
    local_llm_provider.py
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

## Suggested Phase Plan

### Phase 1: Deterministic research stage

- add Brave client wrapper
- add section-aware search planner
- add rule-based scoring and deduplication
- store research packet artifact
- keep existing Claude content path available

### Phase 2: Local synthesis provider

- add local provider interface
- feed research packet into local content prompt
- compare output quality against Claude path
- tune candidate packet size and prompt format

### Phase 3: Optional refinement loop

- allow local model to request one additional query for a section
- keep this bounded and observable

### Phase 4: Optional autonomous local tools

- only if needed, add full tool-calling local harness
- treat this as an experiment, not the default path

---

## Acceptance Criteria

This design is successful if:

1. the app can build section-level research packets using Brave without model-directed search
2. the research packet is inspectable and scored deterministically
3. a local model can generate valid issue JSON from the research packet
4. the local-render path remains unchanged and compatible
5. provider selection remains explicit and pluggable
6. the design respects real Brave API constraints rather than assuming unrestricted search behavior

---

## Risks and Mitigations

### Risk: deterministic search misses good stories
Mitigation:
- use multiple query templates per section
- support section-specific tuning
- later allow one bounded refinement query from the model

### Risk: heuristic ranking is too dumb
Mitigation:
- store scores and reasons for inspection
- tune weights using observed issue quality
- treat ranking as configuration and code, not magic

### Risk: local model still underperforms on synthesis
Mitigation:
- preserve hosted provider fallback
- keep provider abstraction clean
- compare local vs hosted outputs on the same research packet

### Risk: Brave snippets are insufficient for some stories
Mitigation:
- add optional fetch/excerpt enrichment for top candidates later
- keep v1 packet bounded and simple

### Risk: prompt becomes too large again
Mitigation:
- cap candidate count per section
- pass summaries, not full raw pages
- keep the local model focused on synthesis rather than retrieval

---

## Alternatives Considered

### 1. Full local tool-calling agent first
Rejected for v1 because it is more fragile, harder to debug, and more model-sensitive.

### 2. Replace Claude with a local model but keep search implicit in the model
Rejected for v1 because local models are less reliable at autonomous search orchestration.

### 3. Do no explicit research stage and rely on non-search local model memory
Rejected because the newsletter depends on timely and accurate external information.

---

## Recommendation

Proceed with a deterministic Brave-powered research stage before attempting full local tool-calling.

Short version:

- let the app plan and execute search
- rank and shortlist candidates with heuristics
- let the local model synthesize from a bounded research packet
- keep rendering deterministic and local
- add model-directed search only later if the deterministic path proves insufficient

This gives Sophie's World the best chance of shipping a practical local generation path without turning the product into an agent-debugging hobby project.
