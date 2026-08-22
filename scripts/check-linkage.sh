#!/usr/bin/env bash
# Report installed binaries whose dynamic dependencies cannot be resolved.
#
#   check-linkage.sh <prefix> [package ...]
#
# A package that compiles, links and installs can still produce libraries and
# executables that will not load. Both bugs that motivated this shipped green:
#
#   - icu recorded a bare install_name, so postgres died at startup with
#     "Library not loaded: libicui18n.74.dylib" while its install said ✅
#   - ncurses installed headers where nothing looked, so nano compiled against
#     Apple's curses and linked against TSI's
#
# Inspection only -- nothing here executes an installed binary, so it cannot
# hang on a program that ignores --version and waits for input.
#
# Exit: 0 when every dependency resolves, 1 otherwise.

set -uo pipefail

PREFIX="${1:?Usage: $0 <prefix> [package ...]}"
shift || true

INSTALL_DIR="$PREFIX/install"
if [ ! -d "$INSTALL_DIR" ]; then
  echo "No install directory at $INSTALL_DIR" >&2
  exit 1
fi

# Restrict to the named packages when given; otherwise everything installed.
if [ "$#" -gt 0 ]; then
  ROOTS=()
  for pkg in "$@"; do
    while IFS= read -r d; do ROOTS+=("$d"); done \
      < <(find "$INSTALL_DIR" -maxdepth 1 -type d -name "${pkg}-*" 2>/dev/null)
  done
  [ ${#ROOTS[@]} -gt 0 ] || { echo "None of the named packages are installed."; exit 0; }
else
  ROOTS=("$INSTALL_DIR")
fi

problems=0
checked=0

report() {
  printf '  ✗ %s\n      %s\n' "$1" "$2"
  problems=$((problems + 1))
}

check_linux() {
  local f="$1" out
  out="$(ldd "$f" 2>/dev/null)" || return 0   # not a dynamic executable
  while IFS= read -r line; do
    case "$line" in
      *"not found"*) report "$f" "$(echo "$line" | xargs)" ;;
    esac
  done <<< "$out"
}

check_macos() {
  local f="$1" out dep base
  out="$(otool -L "$f" 2>/dev/null)" || return 0
  base="$(basename "$f")"
  # Line 1 is the file being inspected. For a dylib, line 2 is its *own*
  # install_name (LC_ID_DYLIB), not a dependency -- coreutils ships
  # libstdbuf.so with a relative id, which nothing links against and which is
  # therefore not a load failure. Executables have no such line, so identify it
  # by basename rather than by position.
  while IFS= read -r dep; do
    [ -n "$dep" ] || continue
    [ "$(basename "$dep")" = "$base" ] && continue
    case "$dep" in
      /*|@*) continue ;;                       # absolute, or @rpath/@loader_path
      *) report "$f" "depends on \"$dep\", which is not an absolute path and will not load" ;;
    esac
  done < <(echo "$out" | awk 'NR>1 {print $1}')
}

case "$(uname -s)" in
  Linux)  CHECK=check_linux  ;;
  Darwin) CHECK=check_macos  ;;
  *) echo "Unsupported platform: $(uname -s); skipping linkage check."; exit 0 ;;
esac

for root in "${ROOTS[@]}"; do
  while IFS= read -r f; do
    checked=$((checked + 1))
    "$CHECK" "$f"
  done < <(find "$root" \( -path '*/bin/*' -o -name '*.so' -o -name '*.so.*' -o -name '*.dylib' \) -type f -perm -u+r 2>/dev/null)
done

if [ "$problems" -gt 0 ]; then
  echo "Checked $checked installed file(s)."
  echo "::error::$problems unresolved dynamic dependency/ies -- these packages install but will not load." >&2
  exit 1
fi

if [ "$checked" -eq 0 ]; then
  # Distinct from a pass: a package that installs only static archives and
  # headers (zlib, built without shared libraries) has nothing to inspect, and
  # saying "all dependencies resolve" would imply a check that never ran.
  echo "Nothing to check: no executables or shared libraries installed."
  exit 0
fi
echo "Checked $checked installed file(s); all dynamic dependencies resolve."
