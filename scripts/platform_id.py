#!/usr/bin/env python3
"""Host platform id, and platform/dependency queries against a package JSON.

Kept in one file so the shell driver has exactly one python entry point.

    platform_id.py                      -> "macOS-aarch64"
    platform_id.py --supports PKG.json  -> exit 0 if buildable on this host
    platform_id.py --platforms PKG.json -> "linux" (declared platforms, joined)
    platform_id.py --deps PKG.json      -> deps + build_deps, space separated

Nothing here is limited to a known list of systems. Any OS or CPU Python can
name gets an id: the well-known ones are spelled the way TSI's `platforms`
field spells them (src/platform/mod.rs), everything else is passed through
lower-cased, so a custom Unix, a new BSD or a new architecture is reported
under its own name instead of being folded into "unknown".
"""
import json
import platform
import re
import sys

# platform.system() -> the os name `platforms` uses. Unlisted systems fall
# through to their own lower-cased name ("Haiku" -> "haiku").
TSI_OS = {
    "linux": "linux",
    "darwin": "darwin", "macos": "darwin",
    "windows": "windows",
    "freebsd": "freebsd", "openbsd": "openbsd", "netbsd": "netbsd",
    "dragonfly": "dragonfly",
    "sunos": "illumos", "illumos": "illumos", "solaris": "illumos",
}
# Prefixes platform.system() reports with a version attached.
TSI_OS_PREFIX = {"cygwin": "cygwin", "msys": "windows", "mingw": "windows"}

# How the os is written in a platform id (and a PACKAGES_STATUS.md column).
# Anything unlisted is shown as its tsi name.
OS_DISPLAY = {
    "linux": "Linux", "darwin": "macOS", "windows": "Windows",
    "freebsd": "FreeBSD", "openbsd": "OpenBSD", "netbsd": "NetBSD",
    "dragonfly": "DragonFly", "illumos": "illumos", "cygwin": "Cygwin",
}


def tsi_os(system):
    s = re.sub(r"[^a-z0-9_]", "", system.lower()) or "unknown"
    if s in TSI_OS:
        return TSI_OS[s]
    for prefix, name in TSI_OS_PREFIX.items():
        if s.startswith(prefix):
            return name
    return s


def tsi_arch(machine):
    """platform.machine() -> the arch name `platforms` uses (x86_64, aarch64,
    x86, arm); anything else (riscv64, ppc64le, s390x, loongarch64, ...) is
    kept as-is."""
    m = re.sub(r"[^a-z0-9_]", "", machine.lower()) or "unknown"
    if m in ("x86_64", "amd64", "x64", "em64t"):
        return "x86_64"
    if m in ("aarch64", "arm64") or m.startswith("armv8") or m.startswith("aarch64"):
        return "aarch64"
    if re.fullmatch(r"i[3-6]86|x86|i86pc", m):
        return "x86"
    if m.startswith("arm"):
        return "arm"
    return m


def platform_id(system=None, machine=None):
    os_name = tsi_os(platform.system() if system is None else system)
    arch = tsi_arch(platform.machine() if machine is None else machine)
    return f"{OS_DISPLAY.get(os_name, os_name)}-{arch}"


def parse_platform_id(pid):
    """"macOS-aarch64" -> ("darwin", "aarch64"). The inverse of platform_id()
    for any id it produces, including ones for systems it has never heard of."""
    display, _, arch = pid.rpartition("-")
    if not display:
        display, arch = pid, ""
    return tsi_os(display), tsi_arch(arch) if arch else ""


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


def supports_platform(plats, os_name, arch):
    """Same rule as TSI's own check: no `platforms` means everywhere."""
    return not plats or any(p == os_name or p == f"{os_name}-{arch}" for p in plats)


def supports(path):
    return supports_platform(
        declared_platforms(path), tsi_os(platform.system()), tsi_arch(platform.machine())
    )


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
