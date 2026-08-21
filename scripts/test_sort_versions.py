#!/usr/bin/env python3
"""Self-check for sort-versions.py: python3 scripts/test_sort_versions.py"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "sort_versions", Path(__file__).resolve().parent / "sort-versions.py"
)
sv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv)


def newest_first(versions):
    return sorted(versions, key=sv.version_key, reverse=True)


def main():
    cases = [
        # Plain numeric ordering, including the "1.10 > 1.9" trap.
        (["1.1.10", "1.2.0", "1.1.9"], "1.2.0"),
        (["1.9", "1.10"], "1.10"),
        # A release always outranks its own prereleases.
        (["1.76.0-pre1", "1.76.0"], "1.76.0"),
        (["78.1rc", "78.1"], "78.1"),
        (["1.10.0rc2", "1.10.0"], "1.10.0"),
        (["1.8.2-rc1", "1.8.2"], "1.8.2"),
        # ...but a prerelease of a *newer* version still beats the older release.
        (["1.8.2", "1.9.0-rc1"], "1.9.0-rc1"),
        # Letter suffixes are later releases, not prereleases (tmux 3.6a).
        (["3.6", "3.6a"], "3.6a"),
        # Date-style versions.
        (["2024-07-02", "2025-11-05"], "2025-11-05"),
        # Real regressions this script exists to prevent.
        (["1.4.6", "2.1.12", "1.3e"], "2.1.12"),
        (["1.8.5", "1.9.2", "1.9.1"], "1.9.2"),
    ]
    for versions, expected in cases:
        got = newest_first(versions)[0]
        assert got == expected, f"{versions}: expected {expected}, got {got} ({newest_first(versions)})"

    # Sorting is stable and idempotent.
    v = ["1.0", "2.0", "1.5"]
    assert newest_first(newest_first(v)) == newest_first(v)

    print("sort-versions self-check passed")


if __name__ == "__main__":
    main()
