# Design: Weekly Cron Job

**Date:** 2026-04-17  
**Status:** Approved

---

## Overview

A wrapper shell script (`scripts/run.sh`) called by a crontab entry on the Mac Mini. Runs every Saturday at 6am Pacific, generates the newsletter with `generate.py`, then sends it with `send.py`. All output is appended to `logs/run.log`.

---

## Architecture

### `scripts/run.sh`

```bash
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd /Users/hobbes/dev/sophies-world

mkdir -p logs
echo "--- $(date) ---" >> logs/run.log
/usr/bin/python3 scripts/generate.py >> logs/run.log 2>&1 && \
/usr/bin/python3 scripts/send.py >> logs/run.log 2>&1
echo "Exit: $?" >> logs/run.log
```

- Sets PATH explicitly so `claude` (at `/opt/homebrew/bin/claude`) is found by `generate.py`'s subprocess call
- `&&` ensures `send.py` only runs if `generate.py` succeeds
- Both stdout and stderr are appended to `logs/run.log` with a timestamp header
- `logs/run.log` is gitignored

### Crontab entry

```
0 6 * * 6 /Users/hobbes/dev/sophies-world/scripts/run.sh
```

- `0 6 * * 6` — 6:00am every Saturday
- Uses the Mac Mini's system timezone (must be set to America/Los_Angeles)
- Added via `crontab -e` on the Mac Mini

---

## Files

| File | Purpose |
|---|---|
| `scripts/run.sh` | Wrapper script (committed) |
| `logs/run.log` | Append-only execution log (gitignored) |
| `.gitignore` | Updated to include `logs/` |

---

## Error Handling

| Condition | Behaviour |
|---|---|
| `generate.py` fails | Non-zero exit logged; `send.py` skipped |
| `send.py` fails | Non-zero exit logged |
| `claude` not in PATH | `generate.py` exits non-zero; logged |
| Mac Mini offline | Cron job missed silently; runs next Saturday |

---

## macOS Permissions Note

macOS may require **Full Disk Access** for `cron` to write to the repo directory. If `run.sh` silently fails, go to System Settings → Privacy & Security → Full Disk Access and add `/usr/sbin/cron`.

---

## Explicitly Out of Scope

- Failure notifications / alerting
- Automatic retries
- Running on missed schedules (launchd catch-up behaviour)
