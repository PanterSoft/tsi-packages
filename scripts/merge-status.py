#!/usr/bin/env python3
"""Build PACKAGES_STATUS.md from one results.tsv per platform.

    merge-status.py PACKAGES_STATUS.md Linux-x86_64=a.tsv macOS-aarch64=b.tsv

Each results.tsv (written by build-all-packages.sh) holds
"<package>\t<ok|fail|skipped|unsupported>\t<note>" rows. The table is rebuilt
from scratch every time: no in-place markdown parsing, so parallel CI legs can
each report independently and only the merge step writes the file.

A package absent from a leg's TSV renders blank -- "not tested there", which is
honestly different from "failed there".
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


def main(argv):
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
