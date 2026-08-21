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
    # The version has to appear in the URL: the validator checks that, because a
    # bumped `version` with a stale URL is how icu came to fetch 74.2 while
    # claiming 78.1.
    data = {
        "name": name,
        "version": "1.0",
        "source": {"type": "tarball", "url": f"https://example.com/{name}-1.0.tar.gz"},
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
        (d / "lonely.json").unlink()   # its bogus dep would fail later dir-wide runs

        r = run(d / "does-not-exist.json")
        assert r.returncode == 1, r.stdout

        # A version number that appears nowhere in its own URL.
        write(d, "drifted", good("drifted", version="9.9"))
        r = run(d)
        assert r.returncode == 1 and "appears nowhere in its URL" in r.stdout, r.stdout
        (d / "drifted.json").unlink()

        # Two entries with the same version number: the second is unreachable.
        write(d, "dupe", {"name": "dupe", "versions": [good("dupe"), good("dupe")]})
        r = run(d)
        assert r.returncode == 1 and "declared 2 times" in r.stdout, r.stdout
        (d / "dupe.json").unlink()

        # Metapackages: no source, but they must pull in something.
        write(d, "meta-ok", {
            "name": "meta-ok", "version": "1.0",
            "build_system": "meta", "dependencies": ["zlib"],
        })
        r = run(d)
        assert r.returncode == 0, r.stdout

        write(d, "meta-ok", {
            "name": "meta-ok", "version": "1.0", "build_system": "meta",
            "dependencies": ["zlib"],
            "source": {"type": "tarball", "url": "https://example.com/x-1.0.tar.gz"},
        })
        r = run(d)
        assert r.returncode == 1 and "must not declare a source" in r.stdout, r.stdout

        write(d, "meta-ok", {"name": "meta-ok", "version": "1.0", "build_system": "meta"})
        r = run(d)
        assert r.returncode == 1 and "does nothing at all" in r.stdout, r.stdout

        # Non-source checks still apply to metapackages.
        write(d, "meta-ok", {
            "name": "meta-ok", "version": "1.0", "build_system": "meta",
            "dependencies": ["zlib"], "platforms": "linux",
        })
        r = run(d)
        assert r.returncode == 1 and "must be an array" in r.stdout, r.stdout
        (d / "meta-ok.json").unlink()

    print("validate-packages self-check passed")


if __name__ == "__main__":
    main()
