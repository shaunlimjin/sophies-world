# Sophie's World

A weekly HTML email newsletter generator for Sophie, with kid-friendly world news, fun facts, Singapore/USA cultural links, money lessons, and interest-based sections like Gymnastics Corner.

The app now supports two content-generation modes and three practical evaluation paths:

1. **Mode A, hosted integrated search**: Claude generates the issue JSON directly with search enabled
2. **Mode B1, deterministic packet + heuristic ranker**: Brave retrieval + deterministic prefiltering + heuristic ranking + hosted synthesis
3. **Mode B2, deterministic packet + hosted model ranker**: Brave retrieval + deterministic prefiltering + hosted model reranking + hosted synthesis

In all modes, the final HTML is rendered locally from a structured issue artifact, and the finished issue can optionally be sent via Gmail SMTP.

---

## Current status

This repo is now meaningfully config-driven and split into clean generation stages:

- child profile lives in `config/children/sophie.yaml`
- section catalog lives in `config/sections.yaml`
- theme metadata lives in `config/themes/default.yaml`
- research configuration lives in `config/research.yaml`
- the interest section is generic, so sections like Gymnastics Corner and K-pop Corner can swap without changing the HTML template structure
- deterministic retrieval planning and artifact management live in `scripts/research_stage.py`
- deterministic prefiltering and ranking live in `scripts/ranking_stage.py`
- external provider adapters live in `scripts/providers/`
- content generation and packet synthesis prompting live in `scripts/content_stage.py`
- issue artifact validation/persistence happens in `scripts/issue_schema.py`
- final HTML rendering happens in `scripts/render_stage.py`
- orchestration lives in `scripts/generate.py`

It is still a single-child implementation in practice, because `generate.py` currently loads `config/children/sophie.yaml` directly.

Current working recommendation after first-pass evaluation: **Mode B1 is the best default path right now.**
B2 is promising, but still slightly behind B1 on issue-level coherence and novelty, even after prompt upgrades.

---

## What the newsletter includes

Each issue currently includes:

- Weird But True
- World Watch
- Singapore Spotlight
- USA Corner
- an interest-driven section (currently Gymnastics Corner)
- Money Moves
- Sophie's Challenge

The target audience is roughly 4th-grade reading level, with a warm, curious tone.

---

## How it works

### High-level pipeline

```text
config + recent issue history
-> Mode A: content_stage.py -> issue artifact
or
-> Mode B: research_stage.py -> ranking_stage.py -> research packet -> content_stage.py -> issue artifact
-> issue_schema.py validation/persistence
-> render_stage.py
-> final HTML newsletter
-> send.py (optional)
```

### Generate

`python3 scripts/generate.py`

This command:

- loads child/profile config
- loads section catalog config
- loads theme config and resolves `template_path`
- loads research config if present
- gathers recent issue headlines to avoid repetition
- resolves `content_provider` and `ranker_provider`
- runs either:
  - **Mode A**: integrated hosted generation, or
  - **Mode B**: deterministic research, ranking, packet synthesis, and packet caching
- validates and writes the issue artifact to `artifacts/issues/`
- loads the HTML template
- renders final HTML locally in `scripts/render_stage.py`
- writes the final issue to `newsletters/sophies-world-YYYY-MM-DD.html`

### Generate a test issue

`python3 scripts/generate.py --test`

Writes to:

- `newsletters/test/`

This is the safest way to test changes to:

- section configuration
- prompt structure
- renderer behavior
- template/layout updates
- content quality tuning
- research/ranking behavior

Quick test workflow:

```bash
cd /Users/hobbes/dev/sophies-world
python3 scripts/generate.py --test
open newsletters/test/sophies-world-$(date +%F).html
```

If a test file for today already exists, `--test` will still regenerate it in the test folder.

### Tagged comparison runs

To compare multiple modes on the same day without overwriting outputs, use `--run-tag`.
This appends the same tag to:
- final HTML output
- issue artifact JSON
- research packet JSON (for Mode B runs)

Examples:

```bash
python3 scripts/generate.py --test --content-provider hosted_integrated_search --run-tag mode-a
python3 scripts/generate.py --test --content-provider hosted_packet_synthesis --ranker heuristic_ranker --refresh-research --run-tag mode-b1
python3 scripts/generate.py --test --content-provider hosted_packet_synthesis --ranker hosted_model_ranker --refresh-research --run-tag mode-b2
```

This produces separate comparable artifacts such as:
- `newsletters/test/sophies-world-YYYY-MM-DD-mode-a.html`
- `artifacts/issues/sophie-YYYY-MM-DD-mode-b1.json`
- `artifacts/research/sophie-YYYY-MM-DD-mode-b2.json`

### Provider selection

By default, generation behavior comes from `config/children/sophie.yaml` under:

- `newsletter.generation.content_provider`
- `newsletter.generation.ranker_provider`

CLI overrides are also available:

```bash
python3 scripts/generate.py --content-provider hosted_integrated_search
python3 scripts/generate.py --content-provider hosted_packet_synthesis --ranker heuristic_ranker
python3 scripts/generate.py --content-provider hosted_packet_synthesis --ranker hosted_model_ranker
```

Valid content providers:

- `hosted_integrated_search`
- `hosted_packet_synthesis`

Valid rankers:

- `heuristic_ranker`
- `hosted_model_ranker`

### Research packet caching

Mode B writes cached research packets to:

- `artifacts/research/`

Cache behavior is now deterministic:

- cached packet + matching `config_hash` → reuse cached packet
- cached packet + mismatched `config_hash` → rerun research/ranking automatically and overwrite the artifact
- `--refresh-research` → always rerun research/ranking even if the hash matches

Useful command:

```bash
python3 scripts/generate.py --content-provider hosted_packet_synthesis --ranker heuristic_ranker --refresh-research
```

### Send

`python3 scripts/send.py`

This command:

- finds today's generated newsletter in `newsletters/`
- reads Gmail credentials from `.env`
- sends the HTML email via Gmail SMTP
- sets the sender display name to `Daddy`

### Weekly automation

A typical automation flow is:

```bash
python3 scripts/generate.py && python3 scripts/send.py
```

In practice, `scripts/run.sh` handles the weekly scheduled run and appends logs to `logs/run.log`.

---

## Key scripts

### `scripts/generate.py`
Main orchestration entry point.

Responsibilities:
- load config
- determine issue number
- collect recent headlines
- resolve content and ranker providers
- run Mode A or Mode B
- validate/persist artifact
- invoke render stage
- write final HTML

### `scripts/research_stage.py`
Deterministic retrieval planning and research packet persistence.

Responsibilities:
- build per-section research plans
- define derived-section behavior such as `sophies_challenge <- world_watch`
- execute Brave retrieval
- shape and persist research packets
- compute config fingerprints for safe cache reuse

### `scripts/ranking_stage.py`
Deterministic prefiltering and configurable candidate ranking.

Responsibilities:
- filter blocked domains and malformed items
- deduplicate by URL and near-duplicate title
- apply heuristic ranking with freshness, novelty, keyword, geography, kid-safe, and junk signals
- dispatch to heuristic or hosted-model rankers

### `scripts/providers/brave_search.py`
Brave Search adapter.

Responsibilities:
- call Brave Search API
- normalize result fields into candidate objects used by the research pipeline

### `scripts/providers/hosted_llm_provider.py`
Hosted model reranker.

Responsibilities:
- rerank filtered candidates for Mode B2
- use recent-issue headline context during reranking
- optimize for section fit, kid readability, novelty, and editorial distinctness
- fall back to filtered ordering if model ranking fails or returns empty

### `scripts/content_stage.py`
Structured content generation orchestration.

Responsibilities:
- summarize child/profile config for prompt use
- summarize active sections and block-type contracts
- build the integrated-search prompt for Mode A
- build the research-packet synthesis prompt for Mode B
- capture debug artifacts in `artifacts/debug/`
- parse the provider envelope safely into structured JSON

### `scripts/issue_schema.py`
Issue artifact helpers.

Responsibilities:
- define artifact paths
- write/read JSON issue artifacts
- validate required top-level and section-level structure

### `scripts/render_stage.py`
Deterministic local HTML renderer.

Responsibilities:
- map block types to renderer functions
- render structured section data into the HTML template
- render section variants like spotlight, interest, money, and challenge blocks
- build greeting/date/footer HTML locally

### `scripts/send.py`
SMTP delivery script.

Responsibilities:
- load Gmail config from `.env`
- find today's newsletter
- build the email subject and HTML message
- send via Gmail SMTP

---

## Setup

### Requirements

- Python 3
- Claude CLI installed and authenticated
- Brave Search API key for Mode B retrieval
- Gmail account with app password for sending

### Python dependencies

Install:

```bash
pip3 install -r requirements.txt
```

Current Python dependency:

- `PyYAML`

### Environment

Create `.env` from `.env.example` and fill in:

```env
BRAVE_API_KEY=your_brave_api_key
GMAIL_USER=your.gmail@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=recipient@example.com
```

---

## Repo structure

```text
sophies-world/
  README.md
  CLAUDE.md
  requirements.txt
  .env
  .env.example
  config/
    children/
      sophie.yaml
    research.yaml
    sections.yaml
    themes/
      default.yaml
  artifacts/
    issues/
    research/
    debug/
  newsletters/
    sophies-world-YYYY-MM-DD.html
    test/
  scripts/
    content_stage.py
    generate.py
    issue_schema.py
    providers/
      __init__.py
      brave_search.py
      hosted_llm_provider.py
    ranking_stage.py
    render_stage.py
    research_stage.py
    run.sh
    send.py
    template.html
  tests/
    test_generate.py
    test_pipeline_integration.py
    test_research_pipeline.py
    test_send.py
  docs/
    ideas-backlog.md
    superpowers/
      specs/
      plans/
```

Note:
- `artifacts/debug/` exists for local debugging but is gitignored.

---

## Config-driven architecture

### Child profile
`config/children/sophie.yaml`

Controls:
- name / age band / location
- cultural context
- active interests
- active newsletter sections
- selected theme
- generation provider defaults
- editorial defaults like reading level, tone, emoji usage, and global source preferences

### Section catalog
`config/sections.yaml`

Defines reusable newsletter modules, including:
- title
- goal
- block type
- link style
- content rules
- preferred sources

### Research config
`config/research.yaml`

Controls deterministic research behavior, including:
- per-section query templates
- per-section freshness windows and result counts
- ranking defaults and section overrides
- novelty comparison settings
- kid-safe and blocked domain lists

### Theme metadata
`config/themes/default.yaml`

Currently controls:
- template path
- section ordering mode

Right now this is intentionally light, but it gives us a clean place to grow toward visual theming later.

### Editorial defaults
Child-specific editorial defaults now live in `config/children/sophie.yaml` under `newsletter.editorial`.

That currently includes:
- reading level
- tone
- emoji usage
- global source preferences

This keeps editorial policy out of Python and makes it easier to tune without editing code.

---

## Output artifacts

### Structured issue artifact
Each successful generation writes a JSON issue artifact to:

- `artifacts/issues/`

This artifact is the contract between content generation and local rendering.

When `--run-tag` is used, the issue artifact filename is tagged as well.

### Research packet artifact
Each successful Mode B research run writes a JSON research packet to:

- `artifacts/research/`

This packet is the contract between retrieval/ranking and packet-driven synthesis.

When `--run-tag` is used, the research packet filename is tagged as well.

### Final HTML newsletter
Production issues are written to:

- `newsletters/`

Test issues are written to:

- `newsletters/test/`

When `--run-tag` is used, the final HTML filename is tagged as well.

---

## Switching sections

To swap the interest section, for example Gymnastics Corner ↔ K-pop Corner:

1. Open `config/children/sophie.yaml`
2. Edit `newsletter.active_sections`
3. Replace the relevant section ID
4. Regenerate with `python3 scripts/generate.py --test`

Important:
- section IDs in `active_sections` must exist in `config/sections.yaml`

---

## Testing

Run the full test suite:

```bash
python3 -m pytest -q
```

Current coverage includes:

- config loading
- missing/invalid config handling
- Mode A / Mode B provider wiring
- tagged output/artifact path handling via `--run-tag`
- deterministic research plan and packet persistence
- prefiltering, dedupe, freshness scoring, novelty handling, and junk penalties
- derived-section packet structure for `sophies_challenge`
- hosted-model ranker fallback behavior
- hosted-model ranker prompt guidance for recent-headline novelty and editorial distinctness
- cache reuse vs rerun behavior for research packets
- structured content prompt assembly
- parser robustness against fenced/trailing content
- issue artifact validation and persistence
- local renderer basics
- spotlight / challenge / money / interest block behavior
- generic interest-slot template checks
- theme template path validation
- send script basics

---

## Known limitations

- `generate.py` still loads `config/children/sophie.yaml` directly, so multi-child support is not yet exposed through a flag like `--child`
- issue numbering is still derived from file counts, which is good enough for now but not fully robust
- final content generation still depends on Claude CLI in both Mode A and Mode B synthesis paths
- research caching is keyed to config shape, but not yet to broader external retrieval conditions beyond those configured inputs
- debug artifacts are local-only and not part of the durable product surface

---

## Evaluation status so far

A first comparison pass has been completed across Mode A, Mode B1, and Mode B2 using tagged runs and saved artifacts.

Current conclusion:
- **Mode B1** is the best current default
- **Mode B2** improved after prompt upgrades, but still does not clearly beat B1
- the biggest quality risk is **repetition / story collision across nearby issues**

Evaluation docs:
- `docs/superpowers/evals/2026-04-20-mode-comparison-scorecard.md`
- `docs/superpowers/evals/2026-04-20-first-pass-mode-comparison-review.md`

---

## Docs worth reading

- `CLAUDE.md` — operator/developer notes for the repo
- `docs/ideas-backlog.md` — next improvements and product ideas
- `docs/superpowers/specs/2026-04-18-modular-sections-design.md` — approved modular-sections spec
- `docs/superpowers/specs/2026-04-18-content-render-split-design.md` — approved content/render split spec
- `docs/superpowers/specs/2026-04-19-local-llm-research-stage-design.md` — local-LLM + deterministic research design
- `docs/superpowers/plans/2026-04-20-deterministic-research-pipeline.md` — deterministic research pipeline implementation plan
- `docs/superpowers/evals/2026-04-20-mode-comparison-scorecard.md` — evaluation rubric for mode comparison
- `docs/superpowers/evals/2026-04-20-first-pass-mode-comparison-review.md` — first-pass mode comparison findings

---

## Recommended next steps

If picking up the project fresh, the highest-leverage next steps are probably:

1. harden novelty guards against repeated stories, repeated events, and recurring evergreen factoids across recent issues
2. continue refining B2 as an experimental path, especially with stronger section-specific anti-repeat guidance
3. tighten cache identity further if real-world retrieval drift becomes a problem
4. replace file-count issue numbering with stable state
5. add explicit multi-child selection
