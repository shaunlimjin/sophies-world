# Design: `scripts/send.py`

**Date:** 2026-04-17  
**Status:** Approved

---

## Overview

A single CLI script that finds today's generated newsletter HTML and sends it to Sophie's email via Gmail SMTP using an App Password. No external dependencies — stdlib only.

---

## Architecture

### Flow

1. Parse `.env` for `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `RECIPIENT_EMAIL`
2. Find `newsletters/sophies-world-YYYY-MM-DD.html` for today's date
3. If no file exists, print error and exit with non-zero code
4. Count `.html` files in `newsletters/` to derive the issue number
5. Build a `MIMEMultipart("alternative")` email with the HTML body
6. Connect to `smtp.gmail.com:587`, STARTTLS, login, send, close

### Subject line

```
Sophie's World · April 17, 2026 · Issue #2
```

Issue number derived by counting all `sophies-world-*.html` files in `newsletters/` (same logic as `generate.py`).

---

## Configuration

### `.env` (gitignored)

```
GMAIL_USER=shaunthegreat@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=sophie.lim.xin.en@gmail.com
```

### `.env.example` (committed)

```
GMAIL_USER=your.gmail@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=recipient@example.com
```

---

## Files

| File | Purpose |
|---|---|
| `scripts/send.py` | The send script |
| `.env` | Credentials (gitignored) |
| `.env.example` | Template for credentials (committed) |

---

## Error Handling

| Condition | Behaviour |
|---|---|
| `.env` missing or unreadable | Print which variables are missing, exit with error |
| No newsletter for today | Print "No newsletter found for YYYY-MM-DD", exit with error |
| SMTP auth failure | Print error from exception, exit with error |
| SMTP send failure | Print error from exception, exit with error |

---

## Explicitly Out of Scope

- Retries on SMTP failure
- CC/BCC recipients
- Attachments
- Scheduling / cron setup (separate task)
- Sending past issues (always sends today's file)
