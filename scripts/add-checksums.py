#!/usr/bin/env python3
"""Fill in missing `source.sha256` for tarball/zip package versions.

    python3 scripts/add-checksums.py brotli fmt      # named packages
    python3 scripts/add-checksums.py --all           # every package
    python3 scripts/add-checksums.py --all --check   # verify, change nothing

Downloads each source archive and records its SHA-256 so TSI verifies the
download before extracting it. Existing checksums are left alone.

--check writes nothing and fails on a mismatch, a missing checksum, or a URL
that no longer resolves -- which is how CI catches a re-cut tarball or a dead
download without building anything.

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
import time
import urllib.request
from pathlib import Path

CHUNK = 1 << 20


ATTEMPTS = 3


class Unreachable(Exception):
    """The source could not be fetched in full -- says nothing about its content."""


def sha256_url(url):
    """sha256 of what `url` serves, or Unreachable.

    Retries, because a single attempt makes a transient failure look permanent:
    a whole CI run reported every ftp.gnu.org package as broken when the runner
    had no route to their IPv6 addresses, while TSI itself downloaded from them
    fine on the same day.

    Checks the length too. A connection dropped mid-download ends the read loop
    normally and yields the hash of a partial file, which then gets reported as
    a checksum MISMATCH -- the one message that should mean "this file is not
    what we pinned". gmp was reported that way while serving exactly its
    recorded bytes.
    """
    last = None
    for attempt in range(1, ATTEMPTS + 1):
        h = hashlib.sha256()
        read = 0
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "tsi-packages/add-checksums"}
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                expected = r.headers.get("Content-Length")
                while chunk := r.read(CHUNK):
                    h.update(chunk)
                    read += len(chunk)
            if expected is not None and read != int(expected):
                raise Unreachable(
                    f"truncated: got {read} of {expected} bytes"
                )
            return h.hexdigest()
        except Exception as e:
            last = e
            if attempt < ATTEMPTS:
                time.sleep(2 ** attempt)
    raise Unreachable(f"{last} (after {ATTEMPTS} attempts)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="*", help="package names (default: --all)")
    ap.add_argument("--all", action="store_true", help="process every package")
    ap.add_argument("--all-versions", action="store_true", help="not just the newest version")
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify checksums and write nothing; fails on a mismatch or a "
             "missing checksum. An unreachable URL is reported, not fatal.",
    )
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
    unreachable = 0
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
            except Exception as e:
                # Kept distinct from a checksum mismatch on purpose: "we could
                # not fetch this" and "this is not the file we pinned" call for
                # completely different reactions, and merging them taught
                # readers to skim past both.
                print(f"⚠ {label}: unreachable: {e}")
                unreachable += 1
                continue

            if existing:
                if existing.lower() == digest:
                    print(f"✓ {label}: checksum matches")
                else:
                    print(f"❌ {label}: checksum MISMATCH\n    recorded {existing}\n    actual   {digest}")
                    failed = True
            elif args.check:
                # --check means "every source is pinned and still matches".
                # Silently passing an unpinned source would make the CI gate
                # green for exactly the package that has no protection.
                print(f"❌ {label}: no recorded sha256 (run add-checksums.py {data.get('name', path.stem)})")
                failed = True
            else:
                source["sha256"] = digest
                changed = True
                print(f"+ {label}: {digest}")

        if changed and not args.check:
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    if unreachable:
        print(f"\n{unreachable} source(s) could not be fetched; see the ⚠ lines above.")

    # A source we could not fetch does not fail the run. This checker cannot
    # tell "upstream is gone" from "the runner had a bad minute", and it once
    # called 16 live ftp.gnu.org packages broken in a single run -- a gate that
    # wrong gets skimmed past, taking the real findings with it. A URL that is
    # genuinely dead breaks an actual build, which is the signal worth acting
    # on. A checksum that does not match still fails, always.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
