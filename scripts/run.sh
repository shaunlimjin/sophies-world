#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd /Users/hobbes/dev/sophies-world

mkdir -p logs
RUN_LOG="logs/run.log"
ALERT_TARGET="${SOPHIES_WORLD_ALERT_TARGET:-channel:1495087675558989854}"
ALERT_CHANNEL="${SOPHIES_WORLD_ALERT_CHANNEL:-discord}"

run_started="$(date)"
echo "--- ${run_started} ---" >> "$RUN_LOG"

/usr/bin/python3 scripts/generate.py >> "$RUN_LOG" 2>&1
status=$?
if [ "$status" -eq 0 ]; then
  /usr/bin/python3 scripts/send.py >> "$RUN_LOG" 2>&1
  status=$?
fi

echo "Exit: $status" >> "$RUN_LOG"

if [ "$status" -ne 0 ]; then
  tail_text="$(tail -40 "$RUN_LOG")"
  alert="Sophie's World weekly send failed (exit ${status}) after run started ${run_started}.

Last log lines:
\`\`\`
${tail_text}
\`\`\`
"
  if command -v openclaw >/dev/null 2>&1; then
    openclaw message send --channel "$ALERT_CHANNEL" --target "$ALERT_TARGET" --message "$alert" >> "$RUN_LOG" 2>&1 || true
  fi
fi

exit "$status"
