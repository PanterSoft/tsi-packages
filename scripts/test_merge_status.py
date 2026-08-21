#!/usr/bin/env python3
"""Self-check for merge-status.py: python3 scripts/test_merge_status.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "linux.tsv").write_text(
            "zlib\tok\t\nlibcap\tok\t\ngit\tfail\t\nonly-on-linux\tok\t\n"
        )
        (td / "mac.tsv").write_text(
            "zlib\tok\t\nlibcap\tunsupported\tlinux-only\ngit\tskipped\tneeds libcap\n"
        )
        out = td / "STATUS.md"
        subprocess.run(
            [sys.executable, str(HERE / "merge-status.py"), str(out),
             f"Linux-x86_64={td/'linux.tsv'}", f"macOS-aarch64={td/'mac.tsv'}"],
            check=True, capture_output=True,
        )
        text = out.read_text()
        rows = {l.split("|")[1].strip(): [c.strip() for c in l.split("|")[1:-1]]
                for l in text.splitlines()[2:]}

        assert rows["zlib"] == ["zlib", "✅", "✅", ""], rows["zlib"]
        assert rows["libcap"] == ["libcap", "✅", "—", "linux-only"], rows["libcap"]
        assert rows["git"] == ["git", "❌", "⏭️", "needs libcap"], rows["git"]
        # Package missing from a leg renders blank, not as a failure.
        assert rows["only-on-linux"] == ["only-on-linux", "✅", "", ""], rows["only-on-linux"]
        # Header carries one column per platform, in argument order.
        header = [c.strip() for c in text.splitlines()[0].split("|")[1:-1]]
        assert header == ["Package", "Linux-x86_64", "macOS-aarch64", "Notes"], header

        # A missing results file is a warning, not a crash: the leg is dropped.
        r = subprocess.run(
            [sys.executable, str(HERE / "merge-status.py"), str(out),
             f"Linux-x86_64={td/'linux.tsv'}", f"Nope={td/'nope.tsv'}"],
            check=True, capture_output=True, text=True,
        )
        assert "column skipped" in r.stderr, r.stderr
        assert "Nope" not in out.read_text()

    print("merge-status self-check passed")


if __name__ == "__main__":
    main()
