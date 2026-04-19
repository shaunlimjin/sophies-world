# Sophie's World — Newsletter Project

## What this is
A weekly HTML email newsletter for Sophie (Shaun's daughter), generated with Claude and sent automatically each week.

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
- Footer: "Made with love by Dad & Claude 🤖❤️" + "Fremont, California ↔ Singapore"
- Title format: "Sophie's World · [Date] · Issue #N"

## Repo structure
```
sophies-world/
  CLAUDE.md                        # this file
  .env                             # credentials (gitignored)
  .env.example                     # template for credentials
  config/
    children/
      sophie.yaml                  # child profile: interests, active sections, theme, editorial defaults
    sections.yaml                  # section catalog: all reusable section definitions
    themes/
      default.yaml                 # theme metadata
  newsletters/
    sophies-world-YYYY-MM-DD.html  # one file per issue
  scripts/
    generate.py                    # orchestrates content stage + local render stage
    content_stage.py               # content provider orchestration (currently Claude)
    render_stage.py                # deterministic local HTML renderer
    issue_schema.py                # structured issue artifact helpers
    send.py                        # sends newsletter via Gmail SMTP
    run.sh                         # wrapper: runs generate + send, logs to logs/run.log
    template.html                  # HTML skeleton with placeholder comments
  tests/
    test_generate.py               # unit tests for generate.py
    test_send.py                   # unit tests for send.py
  logs/
    run.log                        # execution log (gitignored)
```

## Automation
- Cron job on Mac Mini: every Saturday at 6am Pacific
- `run.sh` sets PATH, runs `generate.py && send.py`, appends output to `logs/run.log`
- `generate.py` now orchestrates a two-stage flow: Claude returns structured newsletter content, then local Python renders final HTML
- structured issue artifacts are written under `artifacts/issues/`
- `send.py` reads `.env` for Gmail credentials and sends via `smtp.gmail.com:587`
- Both scripts are idempotent from the operator point of view: `generate.py` skips if today's live file exists; `send.py` always sends today's file
- The HTML template now uses a generic interest-feature slot rather than a hardcoded K-pop slot, so interest sections like Gymnastics Corner and K-pop Corner can swap without changing the template structure
- `generate.py` resolves the newsletter template from `config/themes/default.yaml` via `template_path`
- Prompt-wide editorial defaults like reading level, tone, emoji usage, and global preferred sources now come from `config/children/sophie.yaml` under `newsletter.editorial`

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
