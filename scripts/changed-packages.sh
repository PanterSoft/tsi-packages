#!/usr/bin/env bash
# Outputs package names (one per line) for packages/*.json files changed since BASE_REF.
# Usage: changed-packages.sh <base_ref> [path_filter]
#   base_ref: e.g. origin/main or HEAD^
#   path_filter: default "packages/" (only paths under this are considered)
# Exit: 0 if changed list computed (may be empty), 1 on usage/error.

set -euo pipefail

BASE_REF="${1:?Usage: $0 <base_ref> [path_filter]}"
PATH_FILTER="${2:-packages/}"

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  echo "Error: invalid base ref: $BASE_REF" >&2
  exit 1
fi

git diff --name-only "$BASE_REF" -- "$PATH_FILTER" \
  | sed -n 's|.*/||; s|\.json$||p' \
  | sort -u
