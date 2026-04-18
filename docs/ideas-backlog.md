# Sophie’s World Ideas Backlog

A working backlog for improving the newsletter generator and delivery flow.

## Reliability

- Add failure alerts for cron runs so silent breakage does not go unnoticed.
- Add a preflight check that validates required env vars, Claude CLI availability, and writable output/log directories before the Saturday run.
- Make issue numbering more robust. Right now it is derived from counting HTML files, which can drift if files are deleted, regenerated, or test files are mixed in.
- Add a delivery log or sent-state file so we can prove whether a specific issue was generated and sent.
- Add clearer structured logging for generate/send/run steps so debugging does not require reading raw mixed stdout.
- Add a dry-run mode for the full pipeline that generates and renders without sending email.
- Add retry/backoff for transient SMTP or Claude CLI failures.
- Add HTML validation or a lightweight sanity check before send, so broken markup does not get emailed.

## Content Quality

- Move the newsletter content spec into a dedicated config or prompt file so it is easier to tune without editing Python code.
- Add a lightweight editorial checklist, for example age-appropriateness, factual clarity, no repeated stories, and link quality.
- Improve duplicate avoidance beyond the previous issue, so topics do not repeat too often across multiple weeks.
- Add guardrails for source quality, preferring kid-friendly and trustworthy sources consistently.
- Add optional personalization hooks based on Sophie’s recent interests, school events, travel, or family context.
- Add a way to preview the generated issue in browser before sending.
- Add a revision pass that checks reading level, tone, and section balance before final output.

## Features

- Add a simple archive index page so past issues are easy to browse.
- Add support for multiple recipients, for example Dad, Mom, or a family alias.
- Add themed or seasonal modes for holidays, birthdays, trips, or special events.
- Add a parent note section that can optionally append a custom message for a given week.
- Add image support carefully, either hosted images or a safer illustrated mode, if we want the newsletter to feel richer visually.
- Add a small admin CLI for common tasks like generate test issue, resend latest, preview latest, or list archive.
- Add a local web UI later if the workflow grows beyond a few scripts.

## Product / UX

- Decide what the core product is: a newsletter factory, a family publishing tool, or a child-friendly current events product. That choice will shape the next features.
- Define success criteria for a good issue, not just successful generation and send.
- Create a lightweight README for fast re-entry, since the repo currently leans on `CLAUDE.md` and internal design docs.
- Add an example issue walkthrough in docs that explains how the template, prompt, and send flow fit together.
- Separate operator-facing docs from app behavior docs so future edits stay tidy.

## Ops / Automation

- Consider moving from cron to launchd if we want better macOS-native scheduling and missed-run behavior.
- Add a scheduled test generation on a non-send cadence, so breakage is caught before the live Saturday run.
- Add a healthcheck command that reports whether the app is ready for the next scheduled send.
- Add backup or export of generated issues to cloud storage or git history conventions if the archive becomes important.

## Nice-to-Have Experiments

- Generate 2 candidate issues and choose the better one.
- Add a “big question of the week” section to encourage conversation after reading.
- Add a Singapore ↔ California comparison mini-section when there is a natural tie-in.
- Add a kid entrepreneurship tracker or recurring savings challenge over multiple weeks.
- Add a feedback loop where Shaun can mark sections as hits or misses, and future prompts adapt.

## Recommended Next Few

If we want the highest leverage next steps, I’d start here:

1. Add a dry-run + preview workflow.
2. Add failure alerts and better structured logs.
3. Move the content spec into its own editable file.
4. Add a stable issue metadata/state file instead of deriving everything from file counts.
