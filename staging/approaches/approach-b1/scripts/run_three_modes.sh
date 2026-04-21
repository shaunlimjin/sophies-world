#!/bin/bash
set -u

cd /Users/hobbes/dev/sophies-world || exit 1
mkdir -p artifacts/debug newsletters/test
rm -f "newsletters/test/sophies-world-$(date +%F).html"

run_mode() {
  label="$1"
  shift
  logfile="artifacts/debug/${label}.run.log"
  echo "=== ${label} ===" | tee "$logfile"
  if python3 scripts/generate.py --test "$@" >> "$logfile" 2>&1; then
    echo "STATUS: SUCCESS" | tee -a "$logfile"
  else
    code=$?
    echo "STATUS: FAIL ($code)" | tee -a "$logfile"
  fi
}

run_mode mode-a --content-provider hosted_integrated_search
run_mode mode-b1 --content-provider hosted_packet_synthesis --ranker heuristic_ranker --refresh-research
run_mode mode-b2 --content-provider hosted_packet_synthesis --ranker hosted_model_ranker --refresh-research

echo
printf '%s\n' '--- SUMMARY ---'
for f in artifacts/debug/mode-a.run.log artifacts/debug/mode-b1.run.log artifacts/debug/mode-b2.run.log; do
  echo "FILE: $f"
  tail -n 25 "$f"
  echo
done

echo
printf '%s\n' '--- TEST OUTPUTS ---'
ls -l newsletters/test | tail -n 5

echo
printf '%s\n' '--- RESEARCH ARTIFACTS ---'
ls -l artifacts/research | tail -n 5 2>/dev/null || true
