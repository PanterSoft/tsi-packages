#!/usr/bin/env python3
"""Build PACKAGES_STATUS.md from one results.tsv per platform.

    merge-status.py [--notes NOTES.tsv] PACKAGES_STATUS.md Linux-x86_64=a.tsv macOS-aarch64=b.tsv

Each results.tsv (written by build-all-packages.sh) holds
"<package>\t<ok|fail|skipped|unsupported>\t<note>" rows. The table is rebuilt
from scratch every time: no in-place markdown parsing, so parallel CI legs can
each report independently and only the merge step writes the file.

A package absent from a leg's TSV renders blank -- "not tested there", which is
honestly different from "failed there".

--notes names a hand-written "<package>\t<platform or *>\t<reason>" file saying
*why* a package does not build somewhere. A reason is shown only while that
package is not green on that platform, so a fixed package sheds its stale note
without anyone having to remember to delete it.
"""
import sys
from pathlib import Path

MARK = {"ok": "✅", "fail": "❌", "skipped": "⏭️", "unsupported": "—"}


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
    curated = []
    if len(argv) > 2 and argv[1] == "--notes":
        curated = read_notes(argv[2])
        argv = [argv[0]] + argv[3:]
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(argv[1])
    legs = []
    for spec in argv[2:]:
        if "=" not in spec:
            print(f"Expected <platform>=<results.tsv>, got: {spec}", file=sys.stderr)
            return 2
        name, path = spec.split("=", 1)
        if not Path(path).exists():
            print(f"warning: no results for {name} ({path}); column skipped", file=sys.stderr)
            continue
        legs.append((name, read_results(path)))

    if not legs:
        print("No results files found; refusing to write an empty table.", file=sys.stderr)
        return 1

    columns = ["Package"] + [name for name, _ in legs] + ["Notes"]
    packages = sorted({p for _, rows in legs for p in rows})

    table = {}
    for pkg in packages:
        cells = {"Package": pkg}
        notes = []
        for name, rows in legs:
            status, note = rows.get(pkg, ("", ""))
            cells[name] = MARK.get(status, "")
            if note and note not in notes:
                notes.append(note)
        for cpkg, plat, reason in curated:
            if cpkg != pkg:
                continue
            legs_here = [n for n, _ in legs] if plat == "*" else [plat]
            not_green = [n for n, rows in legs
                         if n in legs_here and rows.get(pkg, ("", ""))[0] != "ok"]
            if not_green:
                text = reason if plat == "*" else f"{plat}: {reason}"
                if text not in notes:
                    notes.append(text)
        cells["Notes"] = "; ".join(notes)
        table[pkg] = cells

    widths = {c: max([len(c)] + [len(table[p].get(c, "")) for p in packages]) for c in columns}
    lines = [
        "| " + " | ".join(f"{c:<{widths[c]}}" for c in columns) + " |",
        "| " + " | ".join("-" * widths[c] for c in columns) + " |",
    ]
    for pkg in packages:
        lines.append("| " + " | ".join(f"{table[pkg].get(c, ''):<{widths[c]}}" for c in columns) + " |")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(packages)} packages x {len(legs)} platforms)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
