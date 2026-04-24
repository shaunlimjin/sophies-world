#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd /Users/hobbes/dev/sophies-world

mkdir -p logs
echo "--- $(date) ---" >> logs/run.log

# Validate configuration before generating. Fail fast if any YAML under
# config/ violates its JSON schema — prevents broken generations.
if ! /usr/bin/python3 scripts/issue_schema.py >> logs/run.log 2>&1; then
    echo "Config validation failed — aborting run. See logs/run.log for details." >&2
    echo "Exit: config-validation-failed" >> logs/run.log
    exit 1
fi

/usr/bin/python3 scripts/generate.py >> logs/run.log 2>&1 && \
/usr/bin/python3 scripts/send.py >> logs/run.log 2>&1
echo "Exit: $?" >> logs/run.log
