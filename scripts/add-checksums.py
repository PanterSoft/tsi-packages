#!/usr/bin/env python3
"""Fill in missing `source.sha256` for tarball/zip package versions.

    python3 scripts/add-checksums.py brotli fmt      # named packages
    python3 scripts/add-checksums.py --all           # every package
    python3 scripts/add-checksums.py --all --check   # verify, change nothing

Downloads each source archive and records its SHA-256 so TSI verifies the
download before extracting it. Existing checksums are left alone unless
--check is given, which re-downloads and reports mismatches instead of writing.

Only the newest version of each package is processed by default; --all-versions
walks every entry, which for a package with 100+ versions means 100+ downloads.

This pins the artifact; it does not establish provenance. A checksum recorded
here says "every later download must be byte-identical to the one taken when
this package was added", which catches a tampered mirror, a re-cut tarball and
a truncated download -- but not a source that was already wrong. When upstream
publishes its own checksum or signature, check the recorded value against it.
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

CHUNK = 1 << 20


def sha256_url(url):
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "tsi-packages/add-checksums"})
    with urllib.request.urlopen(req, timeout=120) as r:
        while chunk := r.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="*", help="package names (default: --all)")
    ap.add_argument("--all", action="store_true", help="process every package")
    ap.add_argument("--all-versions", action="store_true", help="not just the newest version")
    ap.add_argument("--check", action="store_true", help="verify existing checksums, write nothing")
    ap.add_argument("--packages-dir", default=str(Path(__file__).resolve().parent.parent / "packages"))
    args = ap.parse_args()

    packages_dir = Path(args.packages_dir)
    if args.all:
        files = sorted(packages_dir.glob("*.json"))
    elif args.packages:
        files = [packages_dir / f"{n}.json" for n in args.packages]
    else:
        ap.error("name packages, or pass --all")

    failed = False
    for path in files:
        if not path.exists():
            print(f"❌ no such package file: {path}")
            failed = True
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        multi = isinstance(data.get("versions"), list) and data["versions"]
        versions = data["versions"] if multi else [data]
        if not args.all_versions:
            versions = versions[:1]

        changed = False
        for v in versions:
            source = v.get("source") or {}
            if source.get("type") not in ("tarball", "zip") or not source.get("url"):
                continue
            existing = source.get("sha256")
            if existing and not args.check:
                continue

            label = f"{data.get('name', path.stem)}@{v.get('version')}"
            try:
                digest = sha256_url(source["url"])
            except Exception as e:  # network/HTTP/anything: report, keep going
                print(f"❌ {label}: {e}")
                failed = True
                continue

            if existing:
                if existing.lower() == digest:
                    print(f"✓ {label}: checksum matches")
                else:
                    print(f"❌ {label}: checksum MISMATCH\n    recorded {existing}\n    actual   {digest}")
                    failed = True
            else:
                source["sha256"] = digest
                changed = True
                print(f"+ {label}: {digest}")

        if changed and not args.check:
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
