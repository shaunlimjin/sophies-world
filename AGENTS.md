# Sophie's World — Newsletter Project

## What this is
A weekly HTML email newsletter for Sophie (Shaun's daughter), generated with Codex and sent automatically each week.

## Setup
- Install Python dependencies with `pip3 install -r requirements.txt`
- Current dependency list is intentionally tiny; right now the main extra dependency is `PyYAML` for config loading

## Sophie's profile
- **Age:** 4th grade (~9–10 years old)
- **Lives:** Fremont, California
- **Family:** Singaporean, living in the USA

**Interests:**
- Gymnastics (active participant) and skiing
- K-pop: especially Katseye and BLACKPINK
- Non-fiction and fun facts ("Weird But True" style)
- Business fairs; learning about saving money

## Newsletter goals
- Develop curiosity about the world
- Age-appropriate current events, including serious topics (wars, economy, tariffs) explained simply with analogies
- Build affinity for both the USA (Fremont/California) and Singapore
- Singapore–USA cultural connection each week

## Newsletter sections (every issue)
| Section | Content |
|---|---|
| **Weird But True** | 2–3 wild fun facts (animals, science, nature) |
| **World Watch** | 2 real, material current events explained for a 4th grader — include serious topics (conflicts, economics) with kid-friendly analogies |
| **Singapore Spotlight** | A fun fact about Singapore — cultural, historical, economic, nature, food, or quirky. Timeless facts are great; does not need to be current news. |
| **USA Corner** | California/Fremont angle, or US sports/science/culture |
| **Gymnastics Corner** | Gymnastics news, athlete stories, fun facts, beginner-safe tips |
| **Money Moves** | One saving/entrepreneurship concept + a real kid entrepreneur story |
| **Sophie's Challenge** | A maths or reasoning puzzle tied to that week's World Watch content |

## Format rules
- Language: 4th-grade reading level, warm and fun tone
- Each section gets 1–2 "Learn More" links (pill-style buttons in HTML)
- Links should prefer kid-friendly sources: Time for Kids, NewsForKids.net, Britannica, BBC Newsround, Nat Geo Kids
- Challenge should tie back to World Watch content (percentages, fractions, basic reasoning)
- Footer: "Made with love by Dad & Codex 🤖❤️" + "Fremont, California ↔ Singapore"
- Title format: "Sophie's World · [Date] · Issue #N"

## Repo structure
```
sophies-world/
  AGENTS.md                        # this file
  .env                             # credentials (gitignored)
  .env.example                     # template for credentials
  config/
    children/
      sophie.yaml                  # child profile: interests, active sections, theme, editorial defaults, generation mode
    sections.yaml                  # section catalog: all reusable section definitions
    themes/
      default.yaml                 # theme metadata
    research.yaml                  # query templates, ranking weights, domain lists, novelty window
  newsletters/
    sophies-world-YYYY-MM-DD.html  # one file per issue
  scripts/
    generate.py                    # orchestrates pipeline: mode selection, research, ranking, content, render
    content_stage.py               # Mode A (integrated search) and Mode B (packet synthesis) content providers
    research_stage.py              # deterministic Brave retrieval stage + artifact persistence
    ranking_stage.py               # deterministic prefilter + pluggable ranker dispatch
    render_stage.py                # deterministic local HTML renderer (unchanged)
    issue_schema.py                # structured issue artifact helpers
    send.py                        # sends newsletter via Gmail SMTP
    run.sh                         # wrapper: runs generate + send, logs to logs/run.log
    template.html                  # HTML skeleton with placeholder comments
    providers/
      brave_search.py              # Brave Web Search API client with retry/backoff
      heuristic_ranker.py          # (unused directly; heuristic ranking lives in ranking_stage.py)
      hosted_llm_provider.py       # hosted model-ranker for Mode B2
  artifacts/
    research/
      sophie-YYYY-MM-DD.json       # persisted research packets (reusable without re-querying Brave)
    issues/
      sophie-YYYY-MM-DD.json       # persisted structured issue artifacts
    debug/                         # debug artifacts from content provider calls
  tests/
    test_generate.py               # unit tests for generate.py
    test_send.py                   # unit tests for send.py
    test_research_pipeline.py      # tests for research/ranking pipeline
  logs/
    run.log                        # execution log (gitignored)
```

## Automation
- Cron job on Mac Mini: every Saturday at 6am Pacific
- `run.sh` sets PATH, runs `generate.py && send.py`, appends output to `logs/run.log`
- `generate.py` orchestrates a four-stage pipeline: research → ranking → content synthesis → local render
- Structured issue artifacts are written under `artifacts/issues/`
- Research packets are persisted under `artifacts/research/` — synthesis can be re-run without re-querying Brave
- `send.py` reads `.env` for Gmail credentials and sends via `smtp.gmail.com:587`
- Both scripts are idempotent: `generate.py` skips if today's live file exists; `send.py` always sends today's file
- `generate.py` resolves the newsletter template from `config/themes/default.yaml` via `template_path`
- Prompt-wide editorial defaults (reading level, tone, emoji usage, global sources) come from `config/children/sophie.yaml` under `newsletter.editorial`

## Generation modes

`generate.py` supports three modes, controlled by `newsletter.generation.content_provider` in `config/children/sophie.yaml` or via `--mode`:

| Mode | `content_provider` value | Description |
|---|---|---|
| **Mode A** | `hosted_integrated_search` | Current baseline: Codex with integrated web search |
| **Mode B1** | `hosted_packet_synthesis` | Deterministic Brave retrieval + heuristic ranking + Codex synthesis |
| **Mode B2** | `hosted_model_ranker` | Deterministic Brave retrieval + model reranking + Codex synthesis |

### Running a specific mode

`content_provider` and `ranker_provider` are separate controls:

```sh
# Mode A (baseline — default):
python3 scripts/generate.py --test

# Mode B1 (deterministic retrieval + heuristic ranking):
python3 scripts/generate.py --test --content-provider hosted_packet_synthesis

# Mode B2 (deterministic retrieval + model reranking):
python3 scripts/generate.py --test --content-provider hosted_packet_synthesis --ranker hosted_model_ranker

# Mode B1 with forced refresh of the research packet:
python3 scripts/generate.py --test --content-provider hosted_packet_synthesis --refresh-research
```

### Replaying synthesis from a cached research packet

If `artifacts/research/sophie-YYYY-MM-DD.json` already exists, Mode B will reuse it.
This lets you iterate on synthesis or ranking without spending Brave API quota.

### Ranking config

Heuristic ranking weights, domain lists, novelty window, and per-section query overrides
are all in `config/research.yaml`. Edit that file to tune ranking without touching code.

### Required credentials

- `BRAVE_API_KEY` — in `.env` — needed for Modes B1 and B2
- Gmail credentials — in `.env` — needed for `send.py`

## Switching sections

To swap newsletter sections (e.g. replace Gymnastics Corner with K-pop Corner):

1. Edit `config/children/sophie.yaml` → `newsletter.active_sections`
2. Add or remove section IDs (must match keys in `config/sections.yaml`)
3. To add a new section type, add its definition to `config/sections.yaml` first

Active sections for Sophie are currently: weird_but_true, world_watch, singapore_spotlight, usa_corner, gymnastics_corner, money_moves, sophies_challenge

## Current limitation
- The architecture is shaped for multiple child profiles, but the current implementation still loads `config/children/sophie.yaml` directly.
- A future enhancement should add explicit child selection, for example a `--child` flag.

## Gmail CSS notes
- Use `display: block` + `margin-bottom` for vertically stacked items — Gmail ignores `flex-direction: column`
- `display: flex; flex-wrap: wrap` is fine for horizontal pill-link rows
