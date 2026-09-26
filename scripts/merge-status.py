#!/usr/bin/env python3
"""Build PACKAGES_STATUS.md from one results.tsv per platform.

    merge-status.py [--packages-dir DIR] PACKAGES_STATUS.md \
        Linux-x86_64=a.tsv macOS-aarch64=b.tsv

Each results.tsv (written by build-all-packages.sh) holds
"<package>\t<ok|fail|skipped|unsupported>\t<note>" rows. The file is rebuilt
from scratch every time: no in-place markdown parsing, so parallel CI legs can
each report independently and only the merge step writes the file.

Every platform TSI knows about gets a column, whether or not CI builds on it
yet, so the table shows the whole support matrix rather than only the legs
that happened to run. On a platform with no results, a package whose
`platforms` field excludes it still renders "—"; everything else is blank.

A package absent from a leg's TSV renders blank -- "not tested there", which is
honestly different from "failed there".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from platform_id import declared_platforms  # noqa: E402

MARK = {"ok": "✅", "fail": "❌", "skipped": "⏭️", "unsupported": "—"}

# Every platform column, in display order: (column id, TSI os, TSI arch).
# Column ids are what platform_id.py prints on that host (and what CI passes
# as <platform>=...); os/arch are the spellings the `platforms` field uses
# (see VALID_OS / VALID_ARCH in validate-packages.py).
PLATFORMS = [
    ("Linux-x86_64", "linux", "x86_64"),
    ("Linux-aarch64", "linux", "aarch64"),
    ("Linux-i686", "linux", "x86"),
    ("Linux-armv7l", "linux", "arm"),
    ("macOS-x86_64", "darwin", "x86_64"),
    ("macOS-aarch64", "darwin", "aarch64"),
    ("Windows-x86_64", "windows", "x86_64"),
    ("Windows-aarch64", "windows", "aarch64"),
    ("FreeBSD-x86_64", "freebsd", "x86_64"),
    ("FreeBSD-aarch64", "freebsd", "aarch64"),
    ("OpenBSD-x86_64", "openbsd", "x86_64"),
    ("NetBSD-x86_64", "netbsd", "x86_64"),
]

LEGEND = """\
| Marker | Meaning |
| ------ | ------- |
| ✅ | built and installed on that platform |
| ❌ | failed to build there |
| — | declares it does not support that platform (`platforms`) |
| ⏭️ | skipped: a dependency was unavailable in that run |
| *(blank)* | not tested on that platform |"""


def read_results(path):
    rows = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        pkg, status = parts[0], parts[1]
        note = parts[2] if len(parts) > 2 else ""
        rows[pkg] = (status, note)
    return rows


def supports(plats, os_name, arch):
    return not plats or any(p == os_name or p == f"{os_name}-{arch}" for p in plats)


def render_table(columns, rows):
    widths = {c: max([len(c)] + [len(r.get(c, "")) for r in rows]) for c in columns}
    lines = [
        "| " + " | ".join(f"{c:<{widths[c]}}" for c in columns) + " |",
        "| " + " | ".join("-" * widths[c] for c in columns) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(f"{r.get(c, ''):<{widths[c]}}" for c in columns) + " |")
    return "\n".join(lines)


def main(argv):
    args = argv[1:]
    packages_dir = Path(__file__).resolve().parent.parent / "packages"
    if len(args) >= 2 and args[0] == "--packages-dir":
        packages_dir = Path(args[1])
        args = args[2:]
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(args[0])
    legs = {}
    for spec in args[1:]:
        if "=" not in spec:
            print(f"Expected <platform>=<results.tsv>, got: {spec}", file=sys.stderr)
            return 2
        name, path = spec.split("=", 1)
        if not Path(path).exists():
            print(f"warning: no results for {name} ({path}); treated as untested", file=sys.stderr)
            continue
        legs[name] = read_results(path)

    if not legs:
        print("No results files found; refusing to write an empty table.", file=sys.stderr)
        return 1

    known = {pid for pid, _, _ in PLATFORMS}
    platforms = PLATFORMS + [(name, None, None) for name in legs if name not in known]

    pkg_files = {p.stem: p for p in packages_dir.glob("*.json")} if packages_dir.is_dir() else {}
    packages = sorted({p for rows in legs.values() for p in rows} | set(pkg_files))

    table = []
    counts = {pid: {} for pid, _, _ in platforms}
    for pkg in packages:
        plats = declared_platforms(pkg_files[pkg]) if pkg in pkg_files else []
        cells = {"Package": pkg}
        notes = []
        for pid, os_name, arch in platforms:
            if pid in legs:
                status, note = legs[pid].get(pkg, ("", ""))
                if note and note not in notes:
                    notes.append(note)
            elif os_name and not supports(plats, os_name, arch):
                status = "unsupported"
            else:
                status = ""
            cells[pid] = MARK.get(status, "")
            key = status if status in MARK else "untested"
            counts[pid][key] = counts[pid].get(key, 0) + 1
        if plats and not any(n.endswith("-only") for n in notes):
            notes.append("/".join(plats) + "-only")
        cells["Notes"] = "; ".join(notes)
        table.append(cells)

    summary = []
    for pid, _, _ in platforms:
        c = counts[pid]
        summary.append({
            "Platform": pid,
            "Validated in CI": "yes" if pid in legs else "not yet",
            "✅": str(c.get("ok", 0)),
            "❌": str(c.get("fail", 0)),
            "⏭️": str(c.get("skipped", 0)),
            "—": str(c.get("unsupported", 0)),
            "Untested": str(c.get("untested", 0)),
        })

    doc = [
        "# Package Status",
        "",
        "<!-- Generated by scripts/merge-status.py from the Validate All Packages"
        " workflow. Do not edit by hand. -->",
        "",
        "Build results for every package on every platform TSI supports. Platforms"
        " marked *not yet* in the summary have no CI runner; their columns only show"
        " packages that declare they do not support them.",
        "",
        LEGEND,
        "",
        "## Summary",
        "",
        render_table(list(summary[0]), summary),
        "",
        "## Packages",
        "",
        render_table(["Package"] + [pid for pid, _, _ in platforms] + ["Notes"], table),
        "",
    ]
    out.write_text("\n".join(doc), encoding="utf-8")
    print(f"Wrote {out} ({len(packages)} packages x {len(platforms)} platforms, {len(legs)} tested)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
