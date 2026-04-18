# Sophie's World

A weekly HTML email newsletter generator for Sophie, with kid-friendly world news, fun facts, Singapore/USA cultural links, money lessons, and interest-based sections like Gymnastics Corner.

The app generates an issue with Claude + web search, writes the HTML to disk, and can send it via Gmail SMTP.

## Current status

This repo is now config-driven in the important places:
- child profile lives in `config/children/sophie.yaml`
- section catalog lives in `config/sections.yaml`
- theme metadata lives in `config/themes/default.yaml`
- the interest section is generic, so sections like Gymnastics Corner and K-pop Corner can swap without changing the HTML template structure

It is still a single-child implementation in practice, because `generate.py` currently loads `config/children/sophie.yaml` directly.

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

## How it works

### Generate
`python3 scripts/generate.py`

- loads child/profile config
- loads section catalog config
- loads theme config and resolves `template_path`
- builds a prompt for Claude
- asks Claude to fill the HTML template
- writes the issue to `newsletters/sophies-world-YYYY-MM-DD.html`

### Generate a test issue
`python3 scripts/generate.py --test`

Writes to:
- `newsletters/test/`

This is the safest way to test changes to sections, template structure, or prompt logic.

Quick test workflow:

```bash
cd /Users/hobbes/dev/sophies-world
python3 scripts/generate.py --test
open newsletters/test/sophies-world-$(date +%F).html
```

If a test file for today already exists, `--test` will still regenerate it in the test folder. Use this flow when changing active sections, editing the template, or tuning prompt/config behavior.

### Send
`python3 scripts/send.py`

- finds today's generated newsletter
- reads Gmail credentials from `.env`
- sends the HTML email via Gmail SMTP

### Weekly automation
`python3 scripts/generate.py && python3 scripts/send.py`

In practice, `scripts/run.sh` handles the weekly scheduled run and appends logs to `logs/run.log`.

## Setup

### Requirements
- Python 3
- Claude CLI installed and authenticated
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
GMAIL_USER=your.gmail@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=recipient@example.com
```

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
    sections.yaml
    themes/
      default.yaml
  newsletters/
    sophies-world-YYYY-MM-DD.html
    test/
  scripts/
    generate.py
    send.py
    run.sh
    template.html
  tests/
    test_generate.py
    test_send.py
  docs/
    ideas-backlog.md
    superpowers/
      specs/
      plans/
```

## Config-driven architecture

### Child profile
`config/children/sophie.yaml`

Controls:
- name / age band / location
- cultural context
- active interests
- active newsletter sections
- selected theme
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

This keeps prompt-wide editorial policy out of Python and makes it easier to tune without editing code.

## Switching sections

To swap the interest section, for example Gymnastics Corner ↔ K-pop Corner:

1. Open `config/children/sophie.yaml`
2. Edit `newsletter.active_sections`
3. Replace the relevant section ID
4. Regenerate with `python3 scripts/generate.py --test`

Important: section IDs in `active_sections` must exist in `config/sections.yaml`.

## Testing

Run the test suite:

```bash
python3 -m pytest -q tests
```

Current coverage includes:
- config loading
- missing/invalid config handling
- prompt assembly
- section swap behavior
- generic interest-slot template checks
- theme template path validation
- send script basics

## Known limitations

- `generate.py` still loads `config/children/sophie.yaml` directly, so multi-child support is not yet exposed through a flag like `--child`
- issue numbering is still derived from file counts, which is good enough for now but not fully robust
- Claude still returns final HTML directly, rather than structured section data rendered locally

## Docs worth reading

- `CLAUDE.md` — operator/developer notes for the repo
- `docs/ideas-backlog.md` — next improvements and product ideas
- `docs/superpowers/specs/2026-04-18-modular-sections-design.md` — approved modular-sections spec
- `docs/superpowers/plans/2026-04-18-modular-sections.md` — implementation plan

## Recommended next steps

If picking up the project fresh, the highest-leverage next steps are probably:
1. add a dry-run + preview workflow
2. add structured failure alerts / logging
3. replace file-count issue numbering with stable state
4. add explicit multi-child selection
5. move further toward structured content rendering instead of direct HTML generation
