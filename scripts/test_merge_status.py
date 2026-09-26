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


def run(out, *legs, pkgdir):
    return subprocess.run(
        [sys.executable, str(HERE / "merge-status.py"), "--packages-dir", str(pkgdir), str(out), *legs],
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
        for pid in ("Linux-x86_64", "Linux-aarch64", "macOS-x86_64", "macOS-aarch64",
                    "Windows-x86_64", "FreeBSD-x86_64"):
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
        assert summary["Linux-x86_64"]["Validated in CI"] == "yes"
        assert summary["Linux-x86_64"]["✅"] == "3" and summary["Linux-x86_64"]["❌"] == "1"
        assert summary["Windows-x86_64"]["Validated in CI"] == "not yet"
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

        # An unknown platform with results is appended rather than dropped.
        run(out, f"Haiku-x86_64={td/'linux.tsv'}", pkgdir=pkgs)
        header3, rows3 = section(out.read_text(), "Packages")
        assert header3[-2] == "Haiku-x86_64", header3
        assert rows3["zlib"]["Haiku-x86_64"] == "✅"

    print("merge-status self-check passed")


if __name__ == "__main__":
    main()
