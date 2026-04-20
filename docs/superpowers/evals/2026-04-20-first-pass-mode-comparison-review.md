# First-pass mode comparison review

**Date:** 2026-04-20  
**Evaluator:** Hobbes  
**Compared outputs:**
- `artifacts/issues/sophie-2026-04-20-mode-a.json`
- `artifacts/issues/sophie-2026-04-20-mode-b1.json`
- `artifacts/issues/sophie-2026-04-20-mode-b2.json`
- supporting research packets for B1/B2
- recent comparison issue: `artifacts/issues/sophie-2026-04-19.json`

## Summary
- **Recommended current default:** Mode B1
- **Confidence:** medium
- **Main concern:** repetition / story collision across nearby issues is real and currently under-defended

Mode B1 looks like the best current operating point. It preserves the benefits of deterministic retrieval, produces strong section-specific material, and feels slightly more grounded and coherent than Mode B2 without the extra complexity of model reranking. Mode A remains viable, but it showed the clearest direct collisions with the prior day's production issue.

## Scorecard

| Category | Weight | Mode A | Mode B1 | Mode B2 | Notes |
|---|---:|---:|---:|---:|---|
| Novelty vs recent issues | 30% | 2.0 | 4.0 | 3.5 | Mode A repeated multiple exact concepts from 2026-04-19. B1 had the freshest overall mix. B2 was mostly fresh, but still repeated hawker centers / national parks / Artemis cluster themes. |
| Section quality and fit | 25% | 3.5 | 4.5 | 4.0 | B1 had the strongest section-to-section fit overall. Mode A drifted into more evergreen/generic content. B2 was good, but sometimes slightly more generic than B1. |
| Kid readability | 20% | 4.5 | 4.5 | 4.5 | All three were readable and age-appropriate. No major separation here. |
| Source-to-story transformation | 15% | 3.0 | 4.0 | 3.5 | Mode A felt closest to rephrasing familiar material. B1 felt best editorially shaped. B2 was solid, but still closely tethered to selected source frames. |
| Mode-specific pipeline quality | 5% | 3.0 | 4.0 | 3.5 | B1 showed the clearest evidence that deterministic retrieval plus heuristic selection improved output distinctness. B2 did not yet show enough advantage to justify extra complexity. |
| Structural/render quality | 5% | 4.5 | 4.5 | 4.5 | All three rendered cleanly with no obvious structural issues. |

## Weighted read

Approximate weighted impression:
- **Mode A:** 3.1 / 5
- **Mode B1:** 4.3 / 5
- **Mode B2:** 3.9 / 5

These are directional, not mathematically precious. The ranking is more important than the exact decimal.

## Story collision check

### Reused URLs
Not fully audited URL-by-URL in this first pass, but candidate/title inspection strongly suggests thematic collisions rather than exact URL-only collisions.

### Reused events/themes
Clear collisions observed:
- **Octopus three hearts**
  - 2026-04-19 production issue
  - 2026-04-20 Mode A
- **Honey lasts / ancient honey still edible**
  - 2026-04-19 production issue
  - 2026-04-20 Mode A
- **Trade war / tariffs raising prices**
  - 2026-04-19 production issue
  - 2026-04-20 Mode A
- **Pay yourself first**
  - 2026-04-19 production issue
  - 2026-04-20 Mode A
- **Moziah Bridges bow tie business**
  - 2026-04-19 production issue
  - 2026-04-20 Mode A
- **Simone Biles profile-style gymnastics story**
  - 2026-04-19 production issue
  - 2026-04-20 Mode A
- **Singapore hawker centers**
  - 2026-04-19 production issue
  - 2026-04-20 Mode B2
- **Artemis / Moon mission**
  - appears in both B1 and B2, though with somewhat different framing
- **National parks free / national parks feature**
  - appears in both B1 and B2 with related framing

### Suspected cosmetic rewrites
Most obvious in Mode A, where multiple sections appear to be near-rewrites of the previous day's issue rather than genuinely new editorial choices.

## Findings

### Mode A
Mode A was surprisingly competent operationally, but weakest on novelty. It appears willing to reach for high-salience, stable, easy-to-explain stories and facts even when those were just used the prior day. That makes sense, because integrated search plus Claude synthesis can still converge on the same obvious answers in a tight time window.

Strengths:
- very readable
- polished phrasing
- coherent challenge derivation from tariff story

Weaknesses:
- strongest direct collisions with the previous issue
- several sections reused both concept and editorial angle from 2026-04-19
- feels least protected against repetition disguised as freshness

### Mode B1
Mode B1 is the strongest current mode. It produced the freshest-feeling mix and the best section fit overall.

Strengths:
- best novelty relative to the prior issue
- `world_watch` felt timely and substantial
- `singapore_spotlight`, `usa_corner`, and `gymnastics_corner` all felt more specifically grounded
- `sophies_challenge` was naturally tied to the Artemis story and felt more issue-specific than Mode A's recycled tariff math
- heuristic ranking appears to have nudged toward cleaner, more section-appropriate candidates

Weaknesses:
- still some broad collision risk around major current events like Artemis
- some research sources remain a bit mixed in quality and specificity

### Mode B2
Mode B2 was also strong, but it did not clearly beat B1.

Strengths:
- good readability
- fresh `world_watch` mix, especially with the Japan earthquake + Artemis pairing
- decent variety in weird facts and money section

Weaknesses:
- repeated some familiar theme clusters like hawker centers and national parks
- model reranking did not obviously produce a better issue than B1
- some selected stories felt slightly more generic or headline-driven than B1's choices

## Recommendation

### Current default
Use **Mode B1** as the current default for continued testing.

Why:
- best balance of freshness, coherence, and implementation simplicity
- deterministic retrieval gives better inspection/debugging surface
- heuristic ranking currently appears good enough, and may actually be helping preserve consistency without overfitting to headline salience

### Main product risk
The real product risk is **story collision across nearby issues**.
This is not just a rendering or phrasing problem. It is a selection problem.

### Highest-leverage next fix
Add stronger **novelty guards** across recent issues, specifically:
1. compare candidate headlines and source URLs against the last N issues
2. penalize semantic/event-level similarity more aggressively, not just title overlap
3. consider section-level cooldowns for recurring evergreen topics and factoids
4. explicitly block challenge derivation from a world story that is already too similar to a recent issue

### Practical interpretation
At this point, the question is no longer “do the pipelines work?” They do.
The next question is “how do we stop the system from confidently retelling yesterday's newsletter in a fresh shirt?”
That is where the next real quality gains are likely to come from.
