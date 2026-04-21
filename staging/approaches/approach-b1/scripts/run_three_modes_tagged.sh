#!/bin/bash
set -u

cd /Users/hobbes/dev/sophies-world || exit 1
mkdir -p artifacts/debug newsletters/test

today="$(date +%F)"

run_mode() {
  label="$1"
  shift
  logfile="artifacts/debug/${label}.run.log"
  echo "=== ${label} ===" | tee "$logfile"
  if python3 scripts/generate.py --test --run-tag "$label" "$@" >> "$logfile" 2>&1; then
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
  tail -n 30 "$f"
  echo
done

echo
printf '%s\n' '--- HTML OUTPUTS ---'
ls -l "newsletters/test/sophies-world-${today}-mode-"*.html 2>/dev/null || true

echo
printf '%s\n' '--- ISSUE ARTIFACTS ---'
ls -l "artifacts/issues/sophie-${today}-mode-"*.json 2>/dev/null || true

echo
printf '%s\n' '--- RESEARCH ARTIFACTS ---'
ls -l "artifacts/research/sophie-${today}-mode-"*.json 2>/dev/null || true
