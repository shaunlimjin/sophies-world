# Sophie's World Mode Comparison Scorecard

**Date:** 2026-04-20  
**Purpose:** Evaluate newsletter generation quality across Mode A, Mode B1, and Mode B2 using a lightweight, repeatable rubric.  
**Why this exists:** Preserve evaluation criteria in the repo so quality review does not disappear into chat history.

---

## Modes under review

- **Mode A**: `hosted_integrated_search`
- **Mode B1**: `hosted_packet_synthesis` + `heuristic_ranker`
- **Mode B2**: `hosted_packet_synthesis` + `hosted_model_ranker`

---

## Scoring scale

Use a 1 to 5 scale for each category:

- **5** = strong
- **4** = good
- **3** = acceptable, but noticeable weakness
- **2** = weak / problematic
- **1** = broken

Half-points are allowed if useful.

---

## Weighted categories

| Category | Weight | What it measures |
|---|---:|---|
| Novelty vs recent issues | 30% | Whether the issue feels meaningfully new relative to recent issues, rather than reusing the same stories or concepts with minor rewrites |
| Section quality and fit | 25% | Whether each section actually fulfills its purpose and feels distinct |
| Kid readability | 20% | Whether a smart 4th grader would understand and enjoy the writing |
| Source-to-story transformation | 15% | Whether the writing is genuine synthesis rather than light paraphrase of the source material |
| Mode-specific pipeline quality | 5% | Whether the pipeline choice produced meaningful quality differences, improvements, or regressions |
| Structural/render quality | 5% | Whether the issue is clean, balanced, and polished as a product artifact |

---

## Category definitions

### 1. Novelty vs recent issues (30%)
**Question:** Does this issue feel meaningfully new relative to the last few issues?

Check for:
- repeated stories or facts across recent issues
- the same underlying event/article resurfacing with only cosmetic wording changes
- section beats repeating too often in a tight window
- `sophies_challenge` being derived from already-reused `world_watch` content

**Special watch-out:** Track **story collision** explicitly:
- same URL reused
- same event reused from different URLs
- same concept reused with light rewriting

---

### 2. Section quality and fit (25%)
**Question:** Does each section actually do its job?

Check for:
- `world_watch` feels current and important
- `weird_but_true` feels genuinely surprising, not filler
- `singapore_spotlight` and `usa_corner` feel distinct rather than interchangeable trivia blobs
- interest section feels personal to Sophie
- `money_moves` teaches something concrete
- `sophies_challenge` feels naturally derived from the issue rather than stapled on

---

### 3. Kid readability (20%)
**Question:** Would a smart 4th grader actually enjoy and understand this?

Check for:
- clear explanations without flattening the idea
- good analogies and examples
- no stiff, adult, abstract, or finance-news style phrasing
- warm, energetic tone without sounding babyish

---

### 4. Source-to-story transformation (15%)
**Question:** Is the model synthesizing well, or mostly paraphrasing source framing?

Check for:
- excessive closeness to source language or structure
- multiple sections drawing from the same narrow source cluster
- whether the writing adds explanation and editorial shaping
- whether links and selected source material feel intentional rather than merely available

---

### 5. Mode-specific pipeline quality (5%)
**Question:** Did the pipeline meaningfully help or constrain output quality?

Check for:
- whether B1/B2 pick more diverse or cleaner candidates than Mode A
- whether deterministic retrieval narrows variety too much
- whether model reranking changes anything meaningfully versus heuristic ranking
- whether all modes collapse to nearly the same output anyway

---

### 6. Structural/render quality (5%)
**Question:** Is the issue clean as a product artifact?

Check for:
- strong `render_title` quality
- balanced section lengths
- no thin or awkward sections
- challenge formatting reads cleanly
- links and section composition feel polished

---

## Evaluation workflow

1. Review the final HTML output for each mode.
2. Inspect the issue artifact JSON for each mode.
3. Inspect the research packet for B1 and B2.
4. Compare against recent production/test issues to assess novelty.
5. Score each category for each mode.
6. Write a concise recommendation:
   - preferred default mode now
   - major quality risks
   - highest-leverage next fix

---

## Output template

```md
# First-pass mode comparison review

## Summary
- Recommended current default:
- Confidence:
- Main concern:

## Scorecard
| Category | Weight | Mode A | Mode B1 | Mode B2 | Notes |
|---|---:|---:|---:|---:|---|
| Novelty vs recent issues | 30% |  |  |  |  |
| Section quality and fit | 25% |  |  |  |  |
| Kid readability | 20% |  |  |  |  |
| Source-to-story transformation | 15% |  |  |  |  |
| Mode-specific pipeline quality | 5% |  |  |  |  |
| Structural/render quality | 5% |  |  |  |  |

## Story collision check
- Reused URLs:
- Reused events/themes:
- Suspected cosmetic rewrites:

## Findings
### Mode A
### Mode B1
### Mode B2

## Recommendation
```

---

## Current hypothesis before review

The biggest likely product risk is **repetition disguised as freshness**, not rendering quality.
That means novelty and story collision deserve more weight than surface polish.
