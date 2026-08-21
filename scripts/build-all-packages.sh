#!/usr/bin/env bash
# Build every package with TSI to verify it is buildable on THIS host.
#
# Usage: build-all-packages.sh [--exclude-slow] [--packages-dir DIR] [--prefix PREFIX]
#   --exclude-slow  Skip known slow packages (gcc, llvm, python, ...)
#   --packages-dir  Path to packages directory (default: repo root packages/)
#   --prefix        TSI prefix to install into (default: $TSI_PREFIX or ~/.tsi)
#
# Emits .build-logs/results.tsv -- "<package>\t<ok|fail|unsupported>\t<note>" --
# which merge-status.py turns into the multi-platform PACKAGES_STATUS.md table.
# One results.tsv per platform; the merge is what makes cross-arch reporting work.
#
# Exit: 0 if every package either built or was legitimately unsupported here.
#       Packages skipped because a *dependency* failed do not fail the run on
#       their own -- the dependency's own `fail` row already does.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGES_DIR="$REPO_ROOT/packages"
LOG_DIR="$REPO_ROOT/.build-logs"
PREFIX="${TSI_PREFIX:-$HOME/.tsi}"
EXCLUDE_SLOW=false
SLOW_PACKAGES='gcc|llvm|clang|rust|python|boost|mongodb|mysql|mariadb|postgresql|ros2|emacs'

while [ $# -gt 0 ]; do
  case "$1" in
    --exclude-slow)  EXCLUDE_SLOW=true; shift ;;
    --packages-dir)  PACKAGES_DIR="$2"; shift 2 ;;
    --prefix)        PREFIX="$2"; shift 2 ;;
    *) echo "Usage: $0 [--exclude-slow] [--packages-dir DIR] [--prefix PREFIX]" >&2; exit 1 ;;
  esac
done

if [ ! -d "$PACKAGES_DIR" ]; then
  echo "Error: packages directory not found: $PACKAGES_DIR" >&2
  exit 1
fi

if ! command -v tsi >/dev/null 2>&1; then
  echo "Error: tsi not found on PATH. Install TSI and ensure it is in PATH." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
RESULTS="$LOG_DIR/results.tsv"
: > "$RESULTS"

PLATFORM="$(python3 "$SCRIPT_DIR/platform_id.py")"
echo "Platform: $PLATFORM"

if ! PACKAGES=$(python3 "$SCRIPT_DIR/sort-packages.py" "$PACKAGES_DIR"); then
  echo "Error: Failed to sort packages. Ensure python3 is installed and valid." >&2
  exit 1
fi

echo "$PACKAGES" > "$LOG_DIR/build-order.txt"

if [ "$EXCLUDE_SLOW" = true ]; then
  PACKAGES=$(echo "$PACKAGES" | grep -vEx "$SLOW_PACKAGES" || true)
fi

echo "Using packages dir: $PACKAGES_DIR"
echo "Build logs: $LOG_DIR"

record() { printf '%s\t%s\t%s\n' "$1" "$2" "${3:-}" >> "$RESULTS"; }

# UNAVAILABLE: every package a dependent cannot build against (failed, or
# unsupported here). BLAMED_UNSUPPORTED: the subset that is merely unsupported,
# so dependents get "unsupported" rather than a spurious "fail".
UNAVAILABLE=""
BLAMED_UNSUPPORTED=""
ANY_FAILED=false
COUNT=0
TOTAL=$(echo "$PACKAGES" | grep -c . || echo 0)

for pkg in $PACKAGES; do
  COUNT=$((COUNT + 1))
  LOG_FILE="$LOG_DIR/${pkg}.log"
  PKG_FILE="$PACKAGES_DIR/${pkg}.json"
  echo "[$COUNT/$TOTAL] Building: $pkg"

  # Declared platform support (schema `platforms` field) decides this, not a
  # hardcoded package-name list.
  if [ -f "$PKG_FILE" ] && ! python3 "$SCRIPT_DIR/platform_id.py" --supports "$PKG_FILE"; then
    echo "  -> SKIPPED (not supported on $PLATFORM)"
    UNAVAILABLE="${UNAVAILABLE} ${pkg}"
    BLAMED_UNSUPPORTED="${BLAMED_UNSUPPORTED} ${pkg}"
    record "$pkg" unsupported "$(python3 "$SCRIPT_DIR/platform_id.py" --platforms "$PKG_FILE")-only"
    continue
  fi

  # Skip packages whose dependencies are already unavailable in this run.
  if [ -n "$UNAVAILABLE" ] && [ -f "$PKG_FILE" ]; then
    BLAME=""
    for dep in $(python3 "$SCRIPT_DIR/platform_id.py" --deps "$PKG_FILE"); do
      case " $UNAVAILABLE " in *" $dep "*) BLAME="$dep"; break ;; esac
    done
    if [ -n "$BLAME" ]; then
      UNAVAILABLE="${UNAVAILABLE} ${pkg}"
      case " $BLAMED_UNSUPPORTED " in
        *" $BLAME "*)
          echo "  -> SKIPPED (dependency unsupported here: $BLAME)"
          BLAMED_UNSUPPORTED="${BLAMED_UNSUPPORTED} ${pkg}"
          record "$pkg" unsupported "needs $BLAME"
          ;;
        *)
          echo "  -> SKIPPED (dependency failed earlier: $BLAME)"
          record "$pkg" skipped "needs $BLAME"
          ;;
      esac
      continue
    fi
  fi

  # Not --verbose: a full-catalogue run with verbose output writes tens of
  # gigabytes of compiler chatter (it filled a 926G disk once). Compact mode
  # still streams every step, and tsi dumps the failing command's full output
  # on failure, which is the part anyone actually reads.
  if tsi install --prefix "$PREFIX" "$pkg" 2>&1 | tee "$LOG_FILE"; then
    rm -f "$LOG_FILE"
    record "$pkg" ok
  else
    echo "  -> FAILED (log: $LOG_FILE)" >&2
    UNAVAILABLE="${UNAVAILABLE} ${pkg}"
    ANY_FAILED=true
    record "$pkg" fail
  fi
done

echo "Results: $RESULTS"
if [ "$ANY_FAILED" = true ]; then
  echo "Some packages failed to build on $PLATFORM." >&2
  exit 1
fi
echo "All $TOTAL packages built on $PLATFORM (unsupported packages skipped)."
