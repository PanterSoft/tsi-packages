#!/usr/bin/env bash
# Build all packages locally with TSI to verify they are buildable.
# Usage: build-all-packages.sh [--exclude-slow] [--packages-dir DIR]
#   --exclude-slow  Skip known slow packages (gcc, llvm, python, etc.)
#   --packages-dir  Path to packages directory (default: repo root packages/)
# Exit: 0 if all builds succeeded (Linux-only skips do not fail the run).
# Logs for failed builds are written to .build-logs/<package>.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGES_DIR="$REPO_ROOT/packages"
LOG_DIR="$REPO_ROOT/.build-logs"
PREFIX="${TSI_PREFIX:-$HOME/.tsi}"
EXCLUDE_SLOW=false
SLOW_PACKAGES='gcc|llvm|clang|rust|python|boost|mongodb|mysql|mariadb|postgresql|ros2|emacs'
# Kernel / syscall APIs not available on Darwin (or typical *BSD).
LINUX_ONLY_PACKAGES='libcap|libseccomp|liburing'
CURRENT_OS="$(uname -s)"

while [ $# -gt 0 ]; do
  case "$1" in
    --exclude-slow)  EXCLUDE_SLOW=true; shift ;;
    --packages-dir)   PACKAGES_DIR="$2"; shift 2 ;;
    --prefix)         PREFIX="$2"; shift 2 ;;
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

if ! PACKAGES=$(python3 "$SCRIPT_DIR/sort-packages.py" "$PACKAGES_DIR"); then
  echo "Error: Failed to sort packages. Ensure python3 is installed and valid." >&2
  exit 1
fi

# Save build order for verification
echo "$PACKAGES" > "$LOG_DIR/build-order.txt"
echo "Build order saved to: $LOG_DIR/build-order.txt"

if [ "$EXCLUDE_SLOW" = true ]; then
  PACKAGES=$(echo "$PACKAGES" | grep -vEx "$SLOW_PACKAGES" || true)
fi

echo "Using packages dir: $PACKAGES_DIR"
echo "Build logs: $LOG_DIR"
echo "Updating TSI package list (--local)... (skipped: already updated locally)"

SUCCEEDED=""
# FAILED_DEPS: any package that is unavailable for dependents (failed build, skipped linux-only, or skipped due to dep).
FAILED_DEPS=""
# LINUX_SKIPPED: subset of FAILED_DEPS that were skipped only because they are Linux-only on this OS.
LINUX_SKIPPED=""
# TSI_FAILED: packages where `tsi install` exited non-zero (real build failures).
TSI_FAILED=""
COUNT=0
STATUS_FILE="$REPO_ROOT/PACKAGES_STATUS.md"
echo "Status file: $STATUS_FILE"
TOTAL=$(echo "$PACKAGES" | grep -c . || echo 0)

for pkg in $PACKAGES; do
  COUNT=$((COUNT + 1))
  LOG_FILE="$LOG_DIR/${pkg}.log"
  echo "[$COUNT/$TOTAL] Building: $pkg"

  # Skip known Linux-only packages on non-Linux platforms.
  if [ "$CURRENT_OS" != "Linux" ] && echo "$pkg" | grep -Eq "^($LINUX_ONLY_PACKAGES)$"; then
    echo "  -> SKIPPED (Linux-only; not supported on $CURRENT_OS)"
    echo "Linux-only; not supported on ${CURRENT_OS}." > "$LOG_FILE"
    FAILED_DEPS="${FAILED_DEPS} ${pkg}"
    LINUX_SKIPPED="${LINUX_SKIPPED} ${pkg}"
    python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result unsupported --log "$LOG_FILE"
    continue
  fi

  # Skip packages whose dependencies have already failed in this run.
  PKG_FILE="$PACKAGES_DIR/${pkg}.json"
  if [ -n "$FAILED_DEPS" ] && [ -f "$PKG_FILE" ]; then
    DEPS=$(python3 - "$PKG_FILE" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

deps = set()
versions = data.get("versions")
if isinstance(versions, list) and versions:
    v = versions[0]
    for key in ("dependencies", "build_dependencies"):
        val = v.get(key, [])
        if isinstance(val, list):
            deps.update(str(x) for x in val)
else:
    for key in ("dependencies", "build_dependencies"):
        val = data.get(key, [])
        if isinstance(val, list):
            deps.update(str(x) for x in val)

print(" ".join(sorted(deps)))
PY
)

    if [ -n "$DEPS" ]; then
      SKIP=false
      FAILED_DEP=""
      for dep in $DEPS; do
        if [[ " $FAILED_DEPS " == *" $dep "* ]]; then
          SKIP=true
          FAILED_DEP="$dep"
          break
        fi
      done

      if [ "$SKIP" = true ]; then
        if [[ " $LINUX_SKIPPED " == *" $FAILED_DEP "* ]]; then
          echo "  -> SKIPPED (dependency is Linux-only: $FAILED_DEP)"
          echo "Skipped: dependency '${FAILED_DEP}' is Linux-only (not supported on this OS)." > "$LOG_FILE"
          FAILED_DEPS="${FAILED_DEPS} ${pkg}"
          LINUX_SKIPPED="${LINUX_SKIPPED} ${pkg}"
          python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result unsupported --log "$LOG_FILE"
        else
          echo "  -> SKIPPED (dependency previously failed: $FAILED_DEP)"
          echo "Skipped because dependency '$FAILED_DEP' failed earlier in this run." > "$LOG_FILE"
          FAILED_DEPS="${FAILED_DEPS} ${pkg}"
          python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result failure --log "$LOG_FILE"
        fi
        continue
      fi
    fi
  fi

  # Run build, save log to file and stdout.
  if tsi install --prefix "$PREFIX" --verbose "$pkg" 2>&1 | tee "$LOG_FILE"; then
    SUCCEEDED="${SUCCEEDED} ${pkg}"
    rm "$LOG_FILE"
    python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result success --log "$LOG_FILE"
  else
    echo "  -> FAILED (log: $LOG_FILE)" >&2
    FAILED_DEPS="${FAILED_DEPS} ${pkg}"
    TSI_FAILED="${TSI_FAILED} ${pkg}"
    python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result failure --log "$LOG_FILE"
  fi
done

if [ -n "$TSI_FAILED" ]; then
  exit 1
fi

echo "All $TOTAL packages built successfully (Linux-only / unsupported-on-this-OS packages were skipped)."
