#!/usr/bin/env python3
"""Self-check for platform_id.py: python3 scripts/test_platform_id.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from platform_id import parse_platform_id, platform_id, supports_platform  # noqa: E402


def main():
    # Known systems use TSI's `platforms` spellings, whatever Python calls them.
    cases = {
        ("Linux", "x86_64"): "Linux-x86_64",
        ("Linux", "armv7l"): "Linux-arm",
        ("Linux", "i686"): "Linux-x86",
        ("Linux", "riscv64"): "Linux-riscv64",
        ("Linux", "ppc64le"): "Linux-ppc64le",
        ("Darwin", "arm64"): "macOS-aarch64",
        ("Windows", "AMD64"): "Windows-x86_64",
        ("FreeBSD", "amd64"): "FreeBSD-x86_64",
        ("SunOS", "i86pc"): "illumos-x86",
        ("CYGWIN_NT-10.0-19045", "x86_64"): "Cygwin-x86_64",
        # Unknown systems and CPUs are named, never folded into "unknown".
        ("Haiku", "x86_64"): "haiku-x86_64",
        ("MyOS", "loongarch64"): "myos-loongarch64",
        ("", ""): "unknown-unknown",
    }
    for (system, machine), want in cases.items():
        got = platform_id(system, machine)
        assert got == want, (system, machine, got)
        # Round trip: an id parses back to the os/arch it was made from.
        assert platform_id(*parse_platform_id(got)) == got, got

    assert parse_platform_id("macOS-aarch64") == ("darwin", "aarch64")
    assert parse_platform_id("myos-riscv64") == ("myos", "riscv64")

    assert supports_platform([], "myos", "riscv64")
    assert supports_platform(["linux"], "linux", "riscv64")
    assert supports_platform(["linux-x86_64"], "linux", "x86_64")
    assert not supports_platform(["linux-x86_64"], "linux", "aarch64")
    assert not supports_platform(["linux"], "myos", "x86_64")
    assert supports_platform(["myos"], "myos", "x86_64")

    print("platform_id self-check passed")


if __name__ == "__main__":
    main()
