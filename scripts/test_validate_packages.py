#!/usr/bin/env python3
"""Self-check for validate-packages.py: python3 scripts/test_validate_packages.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate-packages.py"


def run(*targets):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *map(str, targets)],
        capture_output=True, text=True,
    )


def write(d, name, data):
    (d / f"{name}.json").write_text(json.dumps(data))


def good(name, **over):
    data = {
        "name": name,
        "version": "1",
        "source": {"type": "tarball", "url": "https://example.com/x.tar.gz"},
        "build_system": "make",
    }
    data.update(over)
    return data


def main():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        write(d, "zlib", good("zlib"))
        write(d, "curl", good("curl", dependencies=["zlib"]))
        r = run(d)
        assert r.returncode == 0, r.stdout

        # Deps are checked inside versions[], not just at the top level.
        write(d, "curl", {"name": "curl", "versions": [
            dict(good("curl"), dependencies=["nope"]),
        ]})
        r = run(d)
        assert r.returncode == 1 and "names no package" in r.stdout, r.stdout

        # Single-version files are validated too, not silently skipped.
        write(d, "curl", good("curl"))
        write(d, "bad", good("bad", build_system="autoconf"))
        r = run(d)
        assert r.returncode == 1 and "invalid build_system" in r.stdout, r.stdout

        write(d, "bad", good("bad", platforms=["macos"]))
        r = run(d)
        assert r.returncode == 1 and "invalid platform" in r.stdout, r.stdout

        write(d, "bad", good("bad", platforms=["linux", "darwin-aarch64"]))
        r = run(d)
        assert r.returncode == 0, r.stdout

        # Two files claiming the same package name.
        write(d, "bad", good("zlib"))
        r = run(d)
        assert r.returncode == 1 and "Duplicate package name" in r.stdout, r.stdout
        (d / "bad.json").unlink()

        (d / "broken.json").write_text("{not json")
        r = run(d)
        assert r.returncode == 1 and "Invalid JSON" in r.stdout, r.stdout
        (d / "broken.json").unlink()

        # A single file has no view of the catalogue: its deps are not resolved.
        write(d, "lonely", good("lonely", dependencies=["nope"]))
        r = run(d / "lonely.json")
        assert r.returncode == 0, r.stdout

        r = run(d / "does-not-exist.json")
        assert r.returncode == 1, r.stdout

    print("validate-packages self-check passed")


if __name__ == "__main__":
    main()
