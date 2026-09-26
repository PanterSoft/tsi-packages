#!/usr/bin/env bash
# Print why each failed package failed, from a build-all-packages.sh log dir.
#
# Usage: failure-details.sh LOG_DIR [PLATFORM]
#
# A full catalogue run writes tens of thousands of log lines; the reasons for
# its failures are a few lines each, buried among them. This prints just
# those: the first error-looking lines and the tail of each failed package's
# log, without the Rust backtrace tsi appends to every error.

set -euo pipefail

LOG_DIR="${1:?usage: failure-details.sh LOG_DIR [PLATFORM]}"
PLATFORM="${2:-}"
RESULTS="$LOG_DIR/results.tsv"

if [ ! -f "$RESULTS" ]; then
  echo "No $RESULTS: the build never got far enough to record results."
  exit 0
fi

FAILED=$(awk -F'\t' '$2 == "fail" { print $1 }' "$RESULTS")
if [ -z "$FAILED" ]; then
  echo "No failed packages${PLATFORM:+ on $PLATFORM}."
  exit 0
fi

for pkg in $FAILED; do
  echo "===== $pkg${PLATFORM:+ ($PLATFORM)} ====="
  LOG="$LOG_DIR/$pkg.log"
  if [ ! -f "$LOG" ]; then
    echo "(no log)"
    continue
  fi
  # Backtrace frames look like "  12: tsi::..." or "      at ./src/...".
  CLEAN=$(grep -vE '^[[:space:]]+([0-9]+: |at )' "$LOG" || true)
  echo "--- first errors ---"
  echo "$CLEAN" | grep -iE 'error|fatal|undefined (reference|symbol)|not found|No such file|cannot|unsupported|failed' | head -n 12 || true
  echo "--- end of log ---"
  echo "$CLEAN" | tail -n 12
done
