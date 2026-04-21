#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd /Users/hobbes/dev/sophies-world

mkdir -p logs
echo "--- $(date) ---" >> logs/run.log
/usr/bin/python3 scripts/generate.py >> logs/run.log 2>&1 && \
/usr/bin/python3 scripts/send.py >> logs/run.log 2>&1
echo "Exit: $?" >> logs/run.log
