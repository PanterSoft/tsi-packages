#!/usr/bin/env python3
"""Host platform id, and platform/dependency queries against a package JSON.

Kept in one file so the shell driver has exactly one python entry point.

    platform_id.py                      -> "macOS-aarch64"
    platform_id.py --supports PKG.json  -> exit 0 if buildable on this host
    platform_id.py --platforms PKG.json -> "linux" (declared platforms, joined)
    platform_id.py --deps PKG.json      -> deps + build_deps, space separated
"""
import json
import platform
import sys

OS = {"Linux": "Linux", "Darwin": "macOS", "Windows": "Windows"}
ARCH = {
    "x86_64": "x86_64", "amd64": "x86_64",
    "arm64": "aarch64", "aarch64": "aarch64",
    "armv7l": "armv7l", "i386": "i386", "i686": "i686",
}
# The `platforms` field uses TSI's own os names (src/platform/mod.rs), which
# differ from platform.system() -- notably "darwin", not "macOS".
TSI_OS = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}


def platform_id():
    s, m = platform.system(), platform.machine().lower()
    return f"{OS.get(s, s)}-{ARCH.get(m, m)}"


def first_version(path):
    """The version block a build uses: versions[0], or the file itself."""
    with open(path) as f:
        data = json.load(f)
    versions = data.get("versions")
    if isinstance(versions, list) and versions:
        return versions[0]
    return data


def declared_platforms(path):
    v = first_version(path)
    p = v.get("platforms", [])
    return [str(x) for x in p] if isinstance(p, list) else []


def supports(path):
    plats = declared_platforms(path)
    if not plats:
        return True
    host_os = TSI_OS.get(platform.system(), platform.system().lower())
    host_arch = ARCH.get(platform.machine().lower(), platform.machine().lower())
    return any(p == host_os or p == f"{host_os}-{host_arch}" for p in plats)


def main():
    args = sys.argv[1:]
    if not args:
        print(platform_id())
        return 0
    flag, path = args[0], args[1]
    if flag == "--supports":
        return 0 if supports(path) else 1
    if flag == "--platforms":
        print("/".join(declared_platforms(path)) or "unknown")
        return 0
    if flag == "--deps":
        v = first_version(path)
        deps = set()
        for key in ("dependencies", "build_dependencies"):
            val = v.get(key, [])
            if isinstance(val, list):
                deps.update(str(x) for x in val)
        print(" ".join(sorted(deps)))
        return 0
    print(f"unknown flag: {flag}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
