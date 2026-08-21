#!/usr/bin/env python3
"""Validate the package catalogue.

    python3 scripts/validate-packages.py                  # whole packages/ dir
    python3 scripts/validate-packages.py packages/git.json # one file
    python3 scripts/validate-packages.py path/to/packages  # another dir

Per package file: valid JSON, a `name`, and a well-formed version block for
every version (source, build system, array/object field types, `platforms`
values). Across the catalogue: no duplicate package names, and every
dependency naming a package that exists.

Both file shapes are checked. In a single-version file the version fields sit
at the top level; in a multi-version file they live in `versions[]`. Checking
only one shape is how half the catalogue used to go unvalidated.

Exit 0 if everything is valid, 1 otherwise.
"""
import json
import sys
from collections import Counter
from pathlib import Path

VALID_SOURCE_TYPES = ["git", "tarball", "zip", "local"]
VALID_BUILD_SYSTEMS = ["autotools", "cmake", "meson", "make", "custom"]
ARRAY_FIELDS = [
    "dependencies", "build_dependencies", "configure_args",
    "cmake_args", "make_args", "patches", "platforms",
]
# `platforms` entries are TSI's own os names (src/platform/mod.rs), optionally
# with an arch suffix. A typo ("macos" for "darwin") would make the package
# unbuildable everywhere while looking perfectly valid, so values are checked.
VALID_OS = ["linux", "darwin", "windows", "freebsd", "openbsd", "netbsd"]
VALID_ARCH = ["x86_64", "aarch64", "x86", "arm"]


def iter_versions(data):
    """Every version block in a package file, whichever shape it uses."""
    versions = data.get("versions")
    if isinstance(versions, list) and versions:
        return versions
    return [data]


def validate_version(version, index, path):
    """Report problems with one version block. Returns True if it is valid."""
    label = f"{path} version {index + 1}"
    ok = True

    if "version" not in version:
        print(f"❌ {label}: missing 'version'")
        ok = False

    source = version.get("source")
    if not isinstance(source, dict) or "type" not in source:
        print(f"❌ {label}: missing or malformed 'source' object")
        return False

    source_type = source.get("type")
    if source_type not in VALID_SOURCE_TYPES:
        print(f"❌ {label}: invalid source type {source_type!r} (valid: {VALID_SOURCE_TYPES})")
        ok = False
    elif source_type == "local":
        if "path" not in source:
            print(f"❌ {label}: source type 'local' needs 'path'")
            ok = False
    elif "url" not in source:
        print(f"❌ {label}: source type {source_type!r} needs 'url'")
        ok = False

    build_system = version.get("build_system", "")
    if build_system and build_system not in VALID_BUILD_SYSTEMS:
        print(f"❌ {label}: invalid build_system {build_system!r} (valid: {VALID_BUILD_SYSTEMS})")
        ok = False

    for field in ARRAY_FIELDS:
        if field in version and not isinstance(version[field], list):
            print(f"❌ {label}: field {field!r} must be an array")
            ok = False

    if "env" in version and not isinstance(version["env"], dict):
        print(f"❌ {label}: field 'env' must be an object")
        ok = False

    platforms = version.get("platforms", [])
    if isinstance(platforms, list):
        for entry in platforms:
            os_part, _, arch_part = str(entry).partition("-")
            if os_part not in VALID_OS or (arch_part and arch_part not in VALID_ARCH):
                print(
                    f"❌ {label}: invalid platform {entry!r} "
                    f"(expected <os> or <os>-<arch>; os one of {VALID_OS})"
                )
                ok = False

    return ok


def main(argv):
    targets = [Path(a) for a in argv[1:]] or [Path(__file__).resolve().parent.parent / "packages"]
    files = []
    for target in targets:
        if target.is_dir():
            files.extend(sorted(target.glob("*.json")))
        elif target.exists():
            files.append(target)
        else:
            print(f"❌ No such file or directory: {target}")
            return 1

    if not files:
        print(f"❌ No package files found in {', '.join(str(t) for t in targets)}")
        return 1

    failed = False
    loaded = {}

    for path in files:
        try:
            loaded[path] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {path}: {e}")
            failed = True

    for path, data in loaded.items():
        if "name" not in data:
            print(f"❌ {path}: missing required field 'name'")
            failed = True
        for i, version in enumerate(iter_versions(data)):
            if not validate_version(version, i, path):
                failed = True

    names = [(data["name"], path) for path, data in loaded.items() if data.get("name")]
    for name, count in Counter(n for n, _ in names).items():
        if count > 1:
            where = ", ".join(str(p) for n, p in names if n == name)
            print(f"❌ Duplicate package name {name!r} in: {where}")
            failed = True

    # Only meaningful over a whole catalogue; validating a single file has no
    # view of what else exists, so unknown deps there are not an error.
    if len(files) > 1:
        known = {n for n, _ in names}
        for path, data in loaded.items():
            pkg_name = data.get("name", path.stem)
            for version in iter_versions(data):
                for key in ("dependencies", "build_dependencies"):
                    for dep in version.get(key) or []:
                        if str(dep).split("@")[0] not in known:
                            print(f"❌ {pkg_name}: {key} {dep!r} names no package in the catalogue")
                            failed = True

    if failed:
        print("::error::Package catalogue validation failed")
        return 1
    print(f"✓ {len(files)} package file(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
