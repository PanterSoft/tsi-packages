#!/usr/bin/env python3
"""Self-check for merge-status.py: python3 scripts/test_merge_status.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def section(text, heading):
    """Rows of the markdown table under `## heading`, keyed by first cell."""
    lines = text.split(f"## {heading}\n", 1)[1].lstrip("\n").splitlines()
    table = []
    for l in lines:
        if not l.startswith("|"):
            break
        table.append(l)
    header = [c.strip() for c in table[0].split("|")[1:-1]]
    rows = {}
    for l in table[2:]:
        cells = [c.strip() for c in l.split("|")[1:-1]]
        rows[cells[0]] = dict(zip(header, cells))
    return header, rows


def run(out, *legs, pkgdir, resdir=None):
    resdir = resdir or pkgdir / "no-results"
    return subprocess.run(
        [sys.executable, str(HERE / "merge-status.py"), "--packages-dir", str(pkgdir),
         "--results-dir", str(resdir), str(out), *legs],
        check=True, capture_output=True, text=True,
    )


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pkgs = td / "packages"
        pkgs.mkdir()
        (pkgs / "libcap.json").write_text(json.dumps({"name": "libcap", "platforms": ["linux"]}))
        (pkgs / "never-built.json").write_text(json.dumps({"name": "never-built"}))
        (td / "linux.tsv").write_text(
            "zlib\tok\t\nlibcap\tok\t\ngit\tfail\t\nonly-on-linux\tok\t\n"
        )
        (td / "mac.tsv").write_text(
            "zlib\tok\t\nlibcap\tunsupported\tlinux-only\ngit\tskipped\tneeds libcap\n"
        )
        out = td / "STATUS.md"
        run(out, f"Linux-x86_64={td/'linux.tsv'}", f"macOS-aarch64={td/'mac.tsv'}", pkgdir=pkgs)
        text = out.read_text()
        header, rows = section(text, "Packages")

        # Every known platform gets a column, tested or not, OS-grouped.
        assert header[0] == "Package" and header[-1] == "Notes", header
        for pid in ("Linux-x86_64", "Linux-aarch64", "Linux-riscv64", "macOS-x86_64",
                    "macOS-aarch64", "Windows-x86_64", "FreeBSD-x86_64", "NetBSD-x86_64"):
            assert pid in header, (pid, header)
        assert header.index("Linux-aarch64") < header.index("macOS-aarch64"), header

        assert rows["zlib"]["Linux-x86_64"] == "✅" and rows["zlib"]["macOS-aarch64"] == "✅"
        assert rows["zlib"]["Windows-x86_64"] == "", rows["zlib"]
        assert rows["libcap"]["macOS-aarch64"] == "—" and rows["libcap"]["Notes"] == "linux-only"
        # Untested platforms still show a declared restriction...
        assert rows["libcap"]["Windows-x86_64"] == "—", rows["libcap"]
        assert rows["libcap"]["FreeBSD-x86_64"] == "—", rows["libcap"]
        # ...but not a guess about other Linux arches.
        assert rows["libcap"]["Linux-aarch64"] == "", rows["libcap"]
        assert rows["git"]["Linux-x86_64"] == "❌" and rows["git"]["macOS-aarch64"] == "⏭️"
        assert rows["git"]["Notes"] == "needs libcap", rows["git"]
        # Package missing from a leg renders blank, not as a failure.
        assert rows["only-on-linux"]["macOS-aarch64"] == "", rows["only-on-linux"]
        # A package in packages/ that no leg reported still gets a row.
        assert "never-built" in rows and rows["never-built"]["Linux-x86_64"] == ""

        _, summary = section(text, "Summary")
        assert summary["Linux-x86_64"]["Results from"] == "CI"
        assert summary["Linux-x86_64"]["✅"] == "3" and summary["Linux-x86_64"]["❌"] == "1"
        assert summary["Windows-x86_64"]["Results from"] == "not tested yet"
        assert summary["Windows-x86_64"]["—"] == "1", summary["Windows-x86_64"]

        # A package excluded from a run keeps its row, with a blank cell and the
        # reason. Without this, --exclude-slow would delete all twelve slow
        # packages from the table the first time the weekly job ran.
        (td / "excl.tsv").write_text("zlib\tok\t\ngcc\t\tnot built here (slow)\n")
        out2 = td / "EXCL.md"
        run(out2, f"Linux-x86_64={td/'excl.tsv'}", pkgdir=td / "none")
        _, rows2 = section(out2.read_text(), "Packages")
        assert rows2["gcc"]["Linux-x86_64"] == "" and rows2["gcc"]["Notes"] == "not built here (slow)"
        assert rows2["zlib"]["Linux-x86_64"] == "✅", rows2["zlib"]

        # A missing results file is a warning, not a crash: the leg is untested.
        r = run(out, f"Linux-x86_64={td/'linux.tsv'}", f"Nope={td/'nope.tsv'}", pkgdir=pkgs)
        assert "treated as untested" in r.stderr, r.stderr
        assert "Nope" not in out.read_text()

        # Any platform with results gets a column, however exotic, grouped
        # after the known OSes.
        run(out, f"Haiku-x86_64={td/'linux.tsv'}", pkgdir=pkgs)
        header3, rows3 = section(out.read_text(), "Packages")
        assert header3[-2] == "haiku-x86_64", header3
        assert rows3["zlib"]["haiku-x86_64"] == "✅"
        assert rows3["libcap"]["haiku-x86_64"] == "✅"  # reported, not inferred

        # Committed results for a platform CI does not have (a custom Unix, a
        # new arch) are merged in; spellings are normalised; CI wins a tie.
        res = td / "status-results"
        res.mkdir()
        (res / "myos-riscv64.tsv").write_text("# a comment\nzlib\tok\t\ngit\tfail\t\n")
        (res / "netbsd-aarch64.tsv").write_text("# source: CI 2026-09-20\nzlib\tok\t\n")
        (res / "linux-x86_64.tsv").write_text("zlib\tfail\t\n")
        run(out, f"Linux-x86_64={td/'linux.tsv'}", pkgdir=pkgs, resdir=res)
        text4 = out.read_text()
        header4, rows4 = section(text4, "Packages")
        _, summary4 = section(text4, "Summary")
        assert "myos-riscv64" in header4 and "linux-x86_64" not in header4, header4
        assert rows4["zlib"]["myos-riscv64"] == "✅" and rows4["git"]["myos-riscv64"] == "❌"
        assert rows4["libcap"]["myos-riscv64"] == ""  # not reported there
        assert rows4["zlib"]["Linux-x86_64"] == "✅", rows4["zlib"]
        assert summary4["myos-riscv64"]["Results from"] == "contributed"
        assert summary4["Linux-x86_64"]["Results from"] == "CI"
        assert summary4["NetBSD-aarch64"]["Results from"] == "CI 2026-09-20"
        # Committed results alone are enough to build the table.
        run(out, pkgdir=pkgs, resdir=res)
        assert "myos-riscv64" in section(out.read_text(), "Packages")[0]

        # A package naming a specific <os>-<arch> brings that column in, and
        # untested platforms it excludes still render "—".
        (pkgs / "vmm.json").write_text(json.dumps({"name": "vmm", "platforms": ["illumos-x86_64"]}))
        run(out, f"Linux-x86_64={td/'linux.tsv'}", pkgdir=pkgs)
        header5, rows5 = section(out.read_text(), "Packages")
        assert "illumos-x86_64" in header5, header5
        assert rows5["vmm"]["illumos-x86_64"] == "" and rows5["vmm"]["macOS-aarch64"] == "—"

    print("merge-status self-check passed")


if __name__ == "__main__":
    main()
