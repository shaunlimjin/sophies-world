# Sophie's World

A weekly HTML email newsletter generator for Sophie, with kid-friendly world news, fun facts, Singapore/USA cultural links, money lessons, and interest-based sections like Gymnastics Corner.

The app currently uses a two-stage pipeline:

1. generate structured newsletter content as a JSON issue artifact
2. render final HTML locally from that artifact
3. optionally send the finished issue via Gmail SMTP

---

## Current status

This repo is now meaningfully config-driven and split into clean generation stages:

- child profile lives in `config/children/sophie.yaml`
- section catalog lives in `config/sections.yaml`
- theme metadata lives in `config/themes/default.yaml`
- the interest section is generic, so sections like Gymnastics Corner and K-pop Corner can swap without changing the HTML template structure
- content generation happens in `scripts/content_stage.py`
- issue artifact validation/persistence happens in `scripts/issue_schema.py`
- final HTML rendering happens in `scripts/render_stage.py`
- orchestration lives in `scripts/generate.py`

It is still a single-child implementation in practice, because `generate.py` currently loads `config/children/sophie.yaml` directly.

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
-> content_stage.py
-> structured issue artifact (JSON)
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
- gathers recent issue headlines to avoid repetition
- builds a structured content prompt in `scripts/content_stage.py`
- calls the content provider and parses the returned JSON issue artifact
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

Quick test workflow:

```bash
cd /Users/hobbes/dev/sophies-world
python3 scripts/generate.py --test
open newsletters/test/sophies-world-$(date +%F).html
```

If a test file for today already exists, `--test` will still regenerate it in the test folder.

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
- invoke content stage
- validate/persist artifact
- invoke render stage
- write final HTML

### `scripts/content_stage.py`
Structured content generation orchestration.

Responsibilities:
- summarize child/profile config for prompt use
- summarize active sections and block-type contracts
- build the content prompt
- call the content provider (currently Claude CLI)
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
    sections.yaml
    themes/
      default.yaml
  artifacts/
    issues/
    debug/
  newsletters/
    sophies-world-YYYY-MM-DD.html
    test/
  scripts/
    content_stage.py
    generate.py
    issue_schema.py
    render_stage.py
    run.sh
    send.py
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

This keeps editorial policy out of Python and makes it easier to tune without editing code.

---

## Output artifacts

### Structured issue artifact
Each successful generation writes a JSON issue artifact to:

- `artifacts/issues/`

This artifact is the contract between content generation and local rendering.

### Final HTML newsletter
Production issues are written to:

- `newsletters/`

Test issues are written to:

- `newsletters/test/`

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
python3 -m pytest -q tests
```

Current coverage includes:

- config loading
- missing/invalid config handling
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
- content generation still depends on Claude CLI in the current provider path
- debug artifacts are local-only and not part of the durable product surface
- the planned deterministic Brave research stage and local-LLM synthesis path are designed but not implemented yet

---

## Docs worth reading

- `CLAUDE.md` — operator/developer notes for the repo
- `docs/ideas-backlog.md` — next improvements and product ideas
- `docs/superpowers/specs/2026-04-18-modular-sections-design.md` — approved modular-sections spec
- `docs/superpowers/specs/2026-04-18-content-render-split-design.md` — approved content/render split spec
- `docs/superpowers/specs/2026-04-19-local-llm-research-stage-design.md` — draft local-LLM + deterministic Brave research design

---

## Recommended next steps

If picking up the project fresh, the highest-leverage next steps are probably:

1. add a deterministic Brave-powered research stage
2. add a local-model content provider behind the existing content-stage abstraction
3. replace file-count issue numbering with stable state
4. add explicit multi-child selection
5. keep README + specs + plans aligned as the local-provider path lands
