#!/usr/bin/env bash
# Build all packages locally with TSI to verify they are buildable.
# Usage: build-all-packages.sh [--exclude-slow] [--packages-dir DIR]
#   --exclude-slow  Skip known slow packages (gcc, llvm, python, etc.)
#   --packages-dir  Path to packages directory (default: repo root packages/)
# Exit: 0 if all builds succeeded, 1 if any failed.
# Logs for failed builds are written to .build-logs/<package>.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGES_DIR="$REPO_ROOT/packages"
LOG_DIR="$REPO_ROOT/.build-logs"
PREFIX="${TSI_PREFIX:-$HOME/.tsi}"
EXCLUDE_SLOW=false
SLOW_PACKAGES='gcc|llvm|clang|rust|python|boost|mongodb|mysql|mariadb|postgresql|ros2|emacs'
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
FAILED=""
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
    echo "  -> SKIPPED (unsupported on this platform: $CURRENT_OS)"
    echo "Unsupported on platform '$CURRENT_OS': linux-only package." > "$LOG_FILE"
    FAILED="${FAILED} ${pkg}"
    python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result failure --log "$LOG_FILE"
    continue
  fi

  # Skip packages whose dependencies have already failed in this run.
  PKG_FILE="$PACKAGES_DIR/${pkg}.json"
  if [ -n "$FAILED" ] && [ -f "$PKG_FILE" ]; then
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
        if [[ " $FAILED " == *" $dep "* ]]; then
          SKIP=true
          FAILED_DEP="$dep"
          break
        fi
      done

      if [ "$SKIP" = true ]; then
        echo "  -> SKIPPED (dependency previously failed: $FAILED_DEP)"
        echo "Skipped because dependency '$FAILED_DEP' failed earlier in this run." > "$LOG_FILE"
        FAILED="${FAILED} ${pkg}"
        python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result failure --log "$LOG_FILE"
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
    FAILED="${FAILED} ${pkg}"
    python3 "$SCRIPT_DIR/update-status.py" --status-file "$STATUS_FILE" --package "$pkg" --result failure --log "$LOG_FILE"
  fi
done

if [ -n "$FAILED" ]; then
  exit 1
fi

echo "All $TOTAL packages built successfully."
