# Design: `scripts/generate.py`

**Date:** 2026-04-16  
**Status:** Approved

---

## Overview

A single CLI script that generates a new Sophie's World HTML newsletter issue by invoking the `claude` CLI subprocess with web search enabled, using the user's existing Claude Pro subscription (no separate API billing).

---

## Architecture

### Flow

1. Read `scripts/template.html` — clean HTML skeleton (CSS + structure, all section content replaced with `<!-- CONTENT -->` placeholders)
2. Count files in `newsletters/` to determine the next issue number
3. Build a detailed prompt encoding Sophie's profile, all 7 section rules, current date, and the full template HTML
4. Shell out to the `claude` CLI with web search tools
5. Parse the JSON response and extract the completed HTML
6. Write output to `newsletters/sophies-world-YYYY-MM-DD.html`

### CLI invocation

```bash
claude -p "<prompt>" \
  --tools "WebSearch,WebFetch" \
  --allowedTools "WebSearch" "WebFetch" \
  --output-format json \
  --max-turns 10
```

- `--tools` restricts Claude to only web tools (no file editing, no bash)
- `--allowedTools` auto-approves those tool calls without interactive prompts
- `--output-format json` gives a structured envelope; the completed HTML is in the `result` field (verify exact field name at implementation time)
- `--max-turns 10` caps the research loop

---

## Prompt Design

The prompt instructs Claude to:

1. Search for current real-world content for each section (World Watch, Singapore Spotlight, USA Corner, K-pop Corner)
2. Fill all 7 sections per the newsletter spec (4th-grade reading level, warm tone, pill-style Learn More links, Sophie's Challenge tied to World Watch)
3. Return **only** the completed HTML — no preamble, no commentary

Sophie's full profile (age, location, interests) and the complete section spec from CLAUDE.md are embedded in the prompt so Claude has full context.

---

## Files

| File | Purpose |
|---|---|
| `scripts/generate.py` | The generation script |
| `scripts/template.html` | Clean HTML skeleton extracted from Issue #1 |
| `newsletters/sophies-world-YYYY-MM-DD.html` | Generated output (one file per issue) |

---

## Error Handling

| Condition | Behaviour |
|---|---|
| Non-zero exit code from `claude` | Print stderr, exit with error |
| Empty or non-HTML result | Print warning, exit with error |
| Output file already exists for today | Print message and skip (idempotent) |

---

## Explicitly Out of Scope

- Sending the email (`send.py` is a separate script)
- Scheduling / cron setup (separate task)
- Automatic retries on failure
