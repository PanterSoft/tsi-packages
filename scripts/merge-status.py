#!/usr/bin/env python3
"""Build PACKAGES_STATUS.md from one results.tsv per platform.

    merge-status.py [--packages-dir DIR] [--results-dir DIR] [--notes NOTES.tsv] \
        PACKAGES_STATUS.md [Linux-x86_64=a.tsv macOS-aarch64=b.tsv ...]

Each results.tsv (written by build-all-packages.sh) holds
"<package>\t<ok|fail|skipped|unsupported>\t<note>" rows. Lines starting with
"#" are comments, except "# source: <text>", which labels where the results
came from in the summary (default: "contributed"). The file is rebuilt from
scratch every time: no in-place markdown parsing, so parallel CI legs can each
report independently and only the merge step writes the file.

Results come from two places:
  * <platform>=<file> arguments -- the CI legs;
  * --results-dir (default: status-results/), one <platform-id>.tsv per
    platform. The weekly workflow commits its CI results there, and anyone who
    runs build-all-packages.sh on a machine CI does not have commits theirs
    alongside. This is how any OS or architecture gets a column, and why the
    table can be regenerated from the repository alone.
A <platform>=<file> argument wins over a committed file of the same name.

The platform set is open: every baseline platform, every platform with
results, and every <os>-<arch> a package's `platforms` field names each get a
column. A platform with no results still shows "—" for a package whose
`platforms` field excludes it; everything else there is blank.

A package absent from a leg's TSV renders blank -- "not tested there", which is
honestly different from "failed there".

--notes names a hand-written "<package>\t<platform or *>\t<reason>" file saying
*why* a package does not build somewhere. A reason is shown only while that
package is not green on that platform, so a fixed package sheds its stale note
without anyone having to remember to delete it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from platform_id import (  # noqa: E402
    declared_platforms, parse_platform_id, platform_id, supports_platform,
)

REPO = Path(__file__).resolve().parent.parent
MARK = {"ok": "✅", "fail": "❌", "skipped": "⏭️", "unsupported": "—"}

# Always shown, tested or not, so the table keeps the common targets in view
# even before anything runs there. It is a floor, not the list of supported
# platforms: anything else appears as soon as it has results. Ids are what
# platform_id.py prints on that host.
BASELINE = [
    "Linux-x86_64", "Linux-aarch64", "Linux-x86", "Linux-arm",
    "Linux-riscv64", "Linux-ppc64le",
    "macOS-x86_64", "macOS-aarch64",
    "Windows-x86_64", "Windows-aarch64",
    "FreeBSD-x86_64", "FreeBSD-aarch64",
    "OpenBSD-x86_64", "NetBSD-x86_64",
]

LEGEND = """\
| Marker | Meaning |
| ------ | ------- |
| ✅ | built and installed on that platform |
| ❌ | failed to build there |
| — | declares it does not support that platform (`platforms`) |
| ⏭️ | skipped: a dependency was unavailable in that run |
| *(blank)* | not tested on that platform |"""

INTRO = """\
One column per platform, and the set is open-ended: TSI is meant to run on any
OS and architecture, including custom Unix-likes. Common targets are always
listed; any other platform gets a column as soon as it has results. A platform
missing from this table is **untested, not unsupported** -- a package without a
`platforms` field is expected to build wherever TSI runs.

To add yours, build the catalogue there, commit the results file, and
regenerate this table (see `status-results/README.md`):

```sh
bash scripts/build-all-packages.sh
f="status-results/$(python3 scripts/platform_id.py).tsv"
{ echo "# source: <who/what>, $(date -u +%F)"; cat .build-logs/results.tsv; } > "$f"
python3 scripts/merge-status.py PACKAGES_STATUS.md
```"""


def read_results(path, default_source):
    rows, source = {}, default_source
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("# source:"):
            source = line.split(":", 1)[1].strip() or default_source
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        pkg, status = parts[0], parts[1] if len(parts) > 1 else ""
        note = parts[2] if len(parts) > 2 else ""
        rows[pkg] = (status, note)
    return rows, source


def render_table(columns, rows):
    widths = {c: max([len(c)] + [len(r.get(c, "")) for r in rows]) for c in columns}
    lines = [
        "| " + " | ".join(f"{c:<{widths[c]}}" for c in columns) + " |",
        "| " + " | ".join("-" * widths[c] for c in columns) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(f"{r.get(c, ''):<{widths[c]}}" for c in columns) + " |")
    return "\n".join(lines)


def canonical(pid):
    """One spelling per platform: "linux-x86_64" and "Linux-x86_64" are the
    same column."""
    return platform_id(*parse_platform_id(pid))


def ordered(platform_ids):
    """Baseline order first; other platforms grouped under their OS (known OSes
    in baseline order, the rest alphabetically), arches alphabetically."""
    os_rank = {}
    for i, pid in enumerate(BASELINE):
        os_rank.setdefault(parse_platform_id(pid)[0], i)

    def key(pid):
        os_name, arch = parse_platform_id(pid)
        base = BASELINE.index(pid) if pid in BASELINE else len(BASELINE)
        return (os_rank.get(os_name, len(BASELINE)), os_name, base, arch)

    return sorted(set(platform_ids), key=key)


def read_notes(path):
    notes = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise SystemExit(f"{path}: expected <package>\\t<platform|*>\\t<reason>: {line!r}")
        notes.append(tuple(p.strip() for p in parts))
    return notes


def main(argv):
    args = argv[1:]
    packages_dir = REPO / "packages"
    results_dir = REPO / "status-results"
    curated = []
    while len(args) >= 2 and args[0] in ("--packages-dir", "--results-dir", "--notes"):
        if args[0] == "--packages-dir":
            packages_dir = Path(args[1])
        elif args[0] == "--results-dir":
            results_dir = Path(args[1])
        else:
            curated = read_notes(args[1])
        args = args[2:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(args[0])

    legs, source = {}, {}
    if results_dir.is_dir():
        for f in sorted(results_dir.glob("*.tsv")):
            pid = canonical(f.stem)
            legs[pid], source[pid] = read_results(f, "contributed")
    for spec in args[1:]:
        if "=" not in spec:
            print(f"Expected <platform>=<results.tsv>, got: {spec}", file=sys.stderr)
            return 2
        name, path = spec.split("=", 1)
        if not Path(path).exists():
            print(f"warning: no results for {name} ({path}); treated as untested", file=sys.stderr)
            continue
        pid = canonical(name)
        legs[pid], source[pid] = read_results(path, "CI")

    if not legs:
        print("No results files found; refusing to write an empty table.", file=sys.stderr)
        return 1

    pkg_files = {p.stem: p for p in packages_dir.glob("*.json")} if packages_dir.is_dir() else {}
    declared = {pkg: declared_platforms(path) for pkg, path in pkg_files.items()}
    packages = sorted({p for rows in legs.values() for p in rows} | set(pkg_files))

    # A package naming a specific <os>-<arch> puts that platform in the table.
    named = set()
    for plats in declared.values():
        for p in plats:
            if "-" in p:
                named.add(canonical(p))
    platforms = ordered(BASELINE + list(legs) + list(named))

    table = []
    counts = {pid: {} for pid in platforms}
    for pkg in packages:
        plats = declared.get(pkg, [])
        cells = {"Package": pkg}
        notes = []
        for pid in platforms:
            if pid in legs:
                status, note = legs[pid].get(pkg, ("", ""))
                if note and note not in notes:
                    notes.append(note)
            elif not supports_platform(plats, *parse_platform_id(pid)):
                status = "unsupported"
            else:
                status = ""
            cells[pid] = MARK.get(status, "")
            key = status if status in MARK else "untested"
            counts[pid][key] = counts[pid].get(key, 0) + 1
        if plats and not any(n.endswith("-only") for n in notes):
            notes.append("/".join(plats) + "-only")
        # Curated reasons (--notes) show only where the package is not green,
        # and only on platforms that were tested: an untested column says
        # nothing about whether the reason still holds.
        for cpkg, plat, reason in curated:
            if cpkg != pkg:
                continue
            here = list(legs) if plat == "*" else [canonical(plat)]
            if any(pid in legs and legs[pid].get(pkg, ("", ""))[0] != "ok" for pid in here):
                text = reason if plat == "*" else f"{plat}: {reason}"
                if text not in notes:
                    notes.append(text)
        cells["Notes"] = "; ".join(notes)
        table.append(cells)

    summary = []
    for pid in platforms:
        c = counts[pid]
        summary.append({
            "Platform": pid,
            "Results from": source.get(pid, "not tested yet"),
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
        " workflow and status-results/. Do not edit by hand. -->",
        "",
        INTRO,
        "",
        LEGEND,
        "",
        "## Summary",
        "",
        render_table(list(summary[0]), summary),
        "",
        "## Packages",
        "",
        render_table(["Package"] + platforms + ["Notes"], table),
        "",
    ]
    out.write_text("\n".join(doc), encoding="utf-8")
    print(f"Wrote {out} ({len(packages)} packages x {len(platforms)} platforms, {len(legs)} tested)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
