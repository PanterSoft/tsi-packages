#!/usr/bin/env bash
# Self-check for check-linkage.sh: bash scripts/test_check_linkage.sh
#
# Builds a tiny library whose dependency cannot be resolved -- the shape of the
# icu bug, where postgres recorded a bare "libicui18n.74.dylib" -- and asserts
# the checker fails on it and passes once it is absolute.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKER="$HERE/check-linkage.sh"

command -v cc >/dev/null 2>&1 || { echo "no C compiler; skipping"; exit 0; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LIB="$TMP/install/demo-1.0/lib"
mkdir -p "$LIB"

case "$(uname -s)" in
  Darwin) EXT=dylib ;;
  Linux)  EXT=so ;;
  *) echo "unsupported platform; skipping"; exit 0 ;;
esac

echo 'int dep(void){return 1;}' > "$TMP/dep.c"
echo 'int dep(void); int use(void){return dep();}' > "$TMP/use.c"

if [ "$EXT" = dylib ]; then
  # A bare install_name is what makes dependents record an unloadable path.
  cc -dynamiclib -Wl,-headerpad_max_install_names -install_name "libdep.$EXT" -o "$LIB/libdep.$EXT" "$TMP/dep.c"
  # -headerpad_max_install_names so the later install_name_tool rewrite fits.
  cc -dynamiclib -Wl,-headerpad_max_install_names -install_name "$LIB/libuse.$EXT" -o "$LIB/libuse.$EXT" "$TMP/use.c" -L"$LIB" -ldep
else
  cc -shared -Wl,-soname,"libdep.$EXT" -fPIC -o "$LIB/libdep.$EXT" "$TMP/dep.c"
  cc -shared -fPIC -o "$LIB/libuse.$EXT" "$TMP/use.c" -L"$LIB" -ldep
fi

if [ "$EXT" = dylib ]; then
  if bash "$CHECKER" "$TMP" >"$TMP/out" 2>&1; then
    echo "FAIL: checker passed a library with an unresolvable dependency"
    cat "$TMP/out"
    exit 1
  fi
  grep -q 'libdep' "$TMP/out" || { echo "FAIL: did not name the bad dependency"; cat "$TMP/out"; exit 1; }

  # Now make it absolute, exactly as the icu fix does, and it must pass.
  install_name_tool -change "libdep.$EXT" "$LIB/libdep.$EXT" "$LIB/libuse.$EXT"
  install_name_tool -id "$LIB/libdep.$EXT" "$LIB/libdep.$EXT"
  bash "$CHECKER" "$TMP" >"$TMP/out2" 2>&1 || { echo "FAIL: rejected a correctly linked library"; cat "$TMP/out2"; exit 1; }
else
  # On Linux an soname that is not on the search path is what ldd reports as
  # "not found"; the library resolves when the path is provided.
  if LD_LIBRARY_PATH='' bash "$CHECKER" "$TMP" >"$TMP/out" 2>&1; then
    echo "NOTE: ldd resolved the dependency here; nothing to assert"
  else
    grep -q 'libdep' "$TMP/out" || { echo "FAIL: did not name the bad dependency"; cat "$TMP/out"; exit 1; }
  fi
fi

# A file with a relative install_name that nothing depends on is not a failure
# (coreutils ships libstdbuf.so that way).
if [ "$EXT" = dylib ]; then
  mkdir -p "$TMP/install/lone-1.0/lib"
  cc -dynamiclib -install_name "src/liblone.$EXT" -o "$TMP/install/lone-1.0/lib/liblone.$EXT" "$TMP/dep.c"
  bash "$CHECKER" "$TMP" lone >/dev/null 2>&1 \
    || { echo "FAIL: flagged a self-contained library for its own relative id"; exit 1; }
fi

# The gawk/readline shape: a library that resolves but is missing a symbol its
# dependents need. Linux only -- this is what `ldd -r` catches and plain ldd
# does not.
if [ "$EXT" = so ]; then
  T2="$TMP/sym"
  BIN2="$T2/install/demo-1.0/bin"
  LIB2="$T2/install/demo-1.0/lib"
  mkdir -p "$BIN2" "$LIB2"

  # libhalf.so calls missing(), which nothing defines -- the shape of readline
  # built without a termcap library. --allow-shlib-undefined lets it link.
  echo 'int missing(void); int half(void){return missing();}' > "$T2/half.c"
  echo 'int half(void); int main(void){return half();}' > "$T2/main.c"
  cc -shared -fPIC -Wl,-soname,libhalf.so -o "$LIB2/libhalf.so" "$T2/half.c"
  cc -o "$BIN2/prog" "$T2/main.c" -L"$LIB2" -lhalf -Wl,-rpath,"$LIB2" \
     -Wl,--allow-shlib-undefined

  if bash "$CHECKER" "$T2" >"$T2/out" 2>&1; then
    echo "FAIL: checker passed an executable with an undefined symbol"
    cat "$T2/out"
    exit 1
  fi
  grep -q 'undefined symbol' "$T2/out" \
    || { echo "FAIL: did not report the undefined symbol"; cat "$T2/out"; exit 1; }

  # The same undefined symbol in a shared library alone must NOT fail: a plugin
  # is meant to get symbols from whatever loads it.
  rm -f "$BIN2/prog"
  bash "$CHECKER" "$T2" >"$T2/out2" 2>&1 \
    || { echo "FAIL: flagged a shared library for an undefined symbol"; cat "$T2/out2"; exit 1; }
fi

echo "check-linkage self-check passed"
