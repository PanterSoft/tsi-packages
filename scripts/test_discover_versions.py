#!/usr/bin/env python3
"""Self-check for discover-versions.py: python3 scripts/test_discover_versions.py"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "discover_versions", Path(__file__).resolve().parent / "discover-versions.py"
)
dv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dv)


def main():
    sel = dv.select_new_versions

    # An update is the newest stable release, and only when it is newer.
    assert sel(["1.2.0"], ["1.3.0", "1.2.1", "1.1.0"]) == ["1.3.0"]
    assert sel(["1.9"], ["1.10"]) == ["1.10"]
    # Nothing newer upstream: nothing to add, even if older tags are missing.
    assert sel(["2.0.0"], ["1.9.0", "1.8.0"]) == []
    assert sel(["2.0.0"], ["2.0.0"]) == []
    # Prereleases are never picked, even when they are the newest tag.
    assert sel(["1.8.2"], ["1.9.0-rc1", "1.8.3"]) == ["1.8.3"]
    assert sel(["1.8.2"], ["1.9.0rc1", "1.9.0-beta2"]) == []
    # Backfill: every missing stable version, newest-first.
    assert sel(["1.2.0"], ["1.1.0", "1.3.0", "1.2.0", "1.3.0-rc1"], backfill=True) == ["1.3.0", "1.1.0"]

    # A generated version never inherits the template's checksum.
    base = {
        "version": "1.2.0",
        "source": {"type": "tarball", "url": "https://x/pkg-1.2.0.tar.gz", "sha256": "ab" * 32},
    }
    new = dv.generate_version_definition(base, "1.3.0")
    assert new["source"]["url"] == "https://x/pkg-1.3.0.tar.gz", new
    assert "sha256" not in new["source"], new
    assert base["source"]["sha256"] == "ab" * 32  # template untouched

    # A version spelled with '-' and '_' in the URL is replaced in both
    # spellings; left alone, icu's "new" version pointed at the old tarball.
    icu = {"version": "74.2", "source": {"type": "tarball", "url":
           "https://github.com/unicode-org/icu/releases/download/release-74-2/icu4c-74_2-src.tgz"}}
    new = dv.generate_version_definition(icu, "77.1")
    assert new["source"]["url"] == (
        "https://github.com/unicode-org/icu/releases/download/release-77-1/icu4c-77_1-src.tgz"), new
    # ...also next to the dotted spelling, which alone used to end the search.
    expat = {"version": "2.6.2", "source": {"type": "tarball", "url":
             "https://github.com/libexpat/libexpat/releases/download/R_2_6_2/expat-2.6.2.tar.xz"}}
    new = dv.generate_version_definition(expat, "2.8.5")
    assert new["source"]["url"] == (
        "https://github.com/libexpat/libexpat/releases/download/R_2_8_5/expat-2.8.5.tar.xz"), new

    # End to end on a file: one version added, file stays newest-first.
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "pkg.json"
        f.write_text(json.dumps({"name": "pkg", "versions": [base, {**base, "version": "1.1.0"}]}))
        added, _ = dv.add_versions_to_package(f, ["1.0.0", "1.3.0", "1.4.0-rc1"], select=True)
        versions = [v["version"] for v in json.loads(f.read_text())["versions"]]
        assert added == 1, added
        assert versions == ["1.3.0", "1.2.0", "1.1.0"], versions

    print("discover-versions self-check passed")


if __name__ == "__main__":
    main()
