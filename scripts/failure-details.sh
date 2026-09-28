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
TIMINGS="$LOG_DIR/timings.tsv"

if [ -s "$TIMINGS" ]; then
  echo "Slowest builds${PLATFORM:+ on $PLATFORM} (seconds, dependencies included):"
  sort -t "$(printf '\t')" -k2,2nr "$TIMINGS" | awk -F'\t' 'NR <= 15 { printf "  %6d  %s\n", $2, $1 }'
  echo
fi

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
  # Real errors first: compiler and linker "error:" lines, CMake/configure
  # errors, missing files. Lines make marks "(ignored)" and warnings are noise.
  {
    echo "$CLEAN" | grep -E '(^|[^a-z])(error|Error|ERROR)(:| at )|fatal error|undefined (reference|symbol)|No such file|not found' \
      | grep -vE '\(ignored\)|WARNING|warning:' || true
    echo "$CLEAN" | grep -iE 'failed|cannot|unsupported' | grep -vE '\(ignored\)|WARNING|warning:' || true
  } | awk '!seen[$0]++' | awk 'NR <= 12' || true
  echo "--- end of log ---"
  echo "$CLEAN" | tail -n 12
done
