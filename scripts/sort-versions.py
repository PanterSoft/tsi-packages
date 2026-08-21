#!/usr/bin/env python3
"""Deduplicate and order each package's `versions`, newest-first.

    python3 scripts/sort-versions.py --check   # report what would change
    python3 scripts/sort-versions.py           # rewrite the files

The dedupe is the part that matters. discover-versions.py appends without
checking, so packages accumulate repeated version numbers -- rocksdb carried 28
and msgpack 4. A repeat is unreachable: `name@version` resolves to one entry, so
every copy after the first is dead weight that still gets read and validated.

The ordering is tidiness, not semantics. TSI does *not* take `versions[0]`: the
registry sorts every package's versions with its own comparator and picks the
highest (src/core/registry.rs), so file order does not choose the default. A
file ordered the same way it will be resolved is simply easier to read and to
review a diff against.

Ordering rule: split on dots and dashes, compare numeric segments numerically
and everything else as text, and rank a prerelease (rc/alpha/beta/pre) below
the release it belongs to. Date-style versions ("2025-11-05") sort naturally
under the same rule.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PRERELEASE = re.compile(r"(rc|alpha|beta|pre)", re.I)


def version_key(version):
    """Sort key: (base version, is-release, prerelease tail).

    The prerelease flag has to outrank the tail, not trail it. Compared as one
    flat list, "1.76.0-pre1" beats "1.76.0" purely by being longer -- which is
    how grpc, icu and meson all defaulted to a release candidate.
    """
    chunks = []
    for token in re.split(r"[.\-_+]", str(version)):
        for chunk in re.findall(r"\d+|\D+", token):
            if chunk.isdigit():
                chunks.append((1, int(chunk), ""))
            else:
                chunks.append((0, 0, chunk.lower()))

    base, tail, seen_marker = [], [], False
    for kind, num, text in chunks:
        if not seen_marker and kind == 0 and PRERELEASE.fullmatch(text.strip()):
            seen_marker = True
        (tail if seen_marker else base).append((kind, num, text))

    return (base, 0 if seen_marker else 1, tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report, write nothing")
    ap.add_argument("--packages-dir", default=str(Path(__file__).resolve().parent.parent / "packages"))
    args = ap.parse_args()

    moved = 0
    for path in sorted(Path(args.packages_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        versions = data.get("versions")
        if not isinstance(versions, list) or len(versions) < 2:
            continue

        # Drop duplicate version numbers first: `name@version` resolves to the
        # first match, so a second entry with the same number is unreachable and
        # only there because discover-versions.py appended it again. Keeping the
        # first occurrence preserves what resolves today.
        deduped, seen = [], set()
        for v in versions:
            key = str(v.get("version"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(v)

        ordered = sorted(deduped, key=lambda v: version_key(v.get("version", "")), reverse=True)
        if ordered == versions:
            continue

        old_default = versions[0].get("version")
        new_default = ordered[0].get("version")
        moved += 1
        dropped = len(versions) - len(ordered)
        if dropped:
            print(f"{data.get('name', path.stem)}: dropped {dropped} duplicate version entr(ies)")
        if old_default != new_default:
            print(f"{data.get('name', path.stem)}: default {old_default} -> {new_default}")
        else:
            print(f"{data.get('name', path.stem)}: reordered (default stays {old_default})")

        if not args.check:
            data["versions"] = ordered
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(f"\n{moved} package file(s) {'would be' if args.check else ''} reordered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
