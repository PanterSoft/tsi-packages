#!/usr/bin/env python3
"""Update Markdown status table with build results"""
import argparse
import platform
import os
from pathlib import Path

def detect_os_arch():
    system = platform.system()
    machine = platform.machine().lower()

    os_map = {"Linux": "Linux", "Darwin": "macOS", "Windows": "Windows"}
    arch_map = {
        "x86_64": "x86_64", "amd64": "x86_64",
        "arm64": "aarch64", "aarch64": "aarch64",
        "armv7l": "armv7l", "i386": "i386", "i686": "i686"
    }

    return f"{os_map.get(system, system)}-{arch_map.get(machine, machine)}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--result", choices=["success", "failure"], required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    os_arch = detect_os_arch()
    status_file = Path(args.status_file).resolve()
    log_file = Path(args.log).resolve()

    columns = ["Package"]
    table_data = {}

    if status_file.exists():
        content = status_file.read_text().strip()
        if content:
            lines = [l.strip() for l in content.splitlines()]
            if len(lines) >= 2 and "|" in lines[0]:
                raw_cols = [c.strip() for c in lines[0].strip("|").split("|")]
                columns = [c for c in raw_cols if c]
                for line in lines[2:]:
                    if not line.strip(): continue
                    parts = [c.strip() for c in line.strip("|").split("|")]
                    if parts:
                        pkg = parts[0]
                        if pkg:
                            table_data[pkg] = {}
                            for i, val in enumerate(parts):
                                if i < len(columns):
                                    table_data[pkg][columns[i]] = val.strip()

    # Ensure standard columns exist
    if os_arch not in columns:
        columns.append(os_arch)
    if "Notes" not in columns:
        columns.append("Notes")

    if args.package not in table_data:
        table_data[args.package] = {}

    table_data[args.package][os_arch] = "✅" if args.result == "success" else "❌"

    # Derive an optional note from the log file.
    # Keep status notes deterministic:
    # - success: clear stale notes
    # - failure with known skip/unsupported reason: set corresponding note
    # - failure without known reason: clear stale skip/unsupported notes
    note = ""
    if args.result == "failure" and log_file.exists():
        try:
            first_line = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
        except IndexError:
            first_line = ""

        dep_prefix = "Skipped because dependency '"
        unsupported_prefix = "Unsupported on platform '"
        if first_line.startswith(dep_prefix) and first_line.endswith(" earlier in this run."):
            dep_name = first_line[len(dep_prefix):].split("'", 1)[0]
            note = f"skipped: {dep_name}"
        elif first_line.startswith(unsupported_prefix):
            platform_name = first_line[len(unsupported_prefix):].split("'", 1)[0]
            note = f"unsupported: {platform_name}"

    if note:
        table_data[args.package]["Notes"] = note
    elif "Notes" in table_data[args.package]:
        del table_data[args.package]["Notes"]

    # Rebuild table
    widths = {c: len(c) for c in columns}
    all_pkgs = sorted(table_data.keys())
    for p in all_pkgs:
        widths["Package"] = max(widths["Package"], len(p))
        for c in columns[1:]:
            val = table_data[p].get(c, "")
            widths[c] = max(widths[c], len(val))

    rows = []
    # Header
    rows.append("| " + " | ".join(f"{c:<{widths[c]}}" for c in columns) + " |")
    # Separator
    rows.append("| " + " | ".join("-" * widths[c] for c in columns) + " |")

    for p in all_pkgs:
        cells = [f"{p:<{widths['Package']}}"]
        for c in columns[1:]:
            cells.append(f"{table_data[p].get(c, ''):<{widths[c]}}")
        rows.append("| " + " | ".join(cells) + " |")

    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text("\n".join(rows) + "\n")
    print(f"Updated {status_file} column {os_arch} for {args.package}")

if __name__ == "__main__":
    main()
