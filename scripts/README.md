# TSI Scripts

This directory contains utility scripts for TSI package management.

## changed-packages.sh

Outputs package names (one per line) for `packages/*.json` files changed since a given git ref. Used by the Test Build Packages CI workflow to decide which packages to test-build.

### Usage

```bash
./changed-packages.sh <base_ref> [path_filter]
```

### Arguments

- `base_ref`: Git ref to diff against (e.g. `origin/main`, `HEAD^`)
- `path_filter`: Path prefix for changed files (default: `packages/`)

### Examples

```bash
# Packages changed since main
./changed-packages.sh origin/main

# Packages changed in last commit
./changed-packages.sh HEAD^
```

### Integration

The Test Build workflow (`.github/workflows/test-build-packages.yml`) runs on push/PR when package JSONs change: it installs TSI from source, points it at this repo’s `packages/` directory, and runs a real build for each changed package (latest version only). Known slow packages (e.g. gcc, llvm) are excluded. TSI must be buildable from the [PanterSoft/TheSourceInstaller](https://github.com/PanterSoft/TheSourceInstaller) repository in CI.

## slow-packages.txt

Packages too slow to build on every CI run, one per line. Read by
`build-all-packages.sh` and by the test-build-packages workflow, so the list
lives in one place instead of drifting between them.

Excluded packages still get a row in `PACKAGES_STATUS.md` — blank cell, with a
note. Dropping them from the results would delete them from the table entirely.

## build-all-packages.sh

Builds all packages locally with TSI once to verify they are buildable. Requires TSI on your PATH (e.g. after `tsi update --local` or using this repo’s packages).

### Usage

```bash
./build-all-packages.sh [--exclude-slow] [--packages-dir DIR]
```

### Arguments

- `--exclude-slow`: Skip known slow packages (gcc, llvm, clang, rust, python, boost, mongodb, mysql, mariadb, postgresql, ros2, emacs)
- `--packages-dir DIR`: Path to the packages directory (default: repo root `packages/`)

### Examples

```bash
# Build all packages (from repo root or scripts/)
./build-all-packages.sh

# Build all except slow ones
./build-all-packages.sh --exclude-slow

# Use a custom packages directory
./build-all-packages.sh --packages-dir /path/to/packages
```

Exit code is 0 if every build succeeded, 1 if any failed. At the end the script prints a summary (succeeded vs failed lists) and, for each failed package, the path to its build log (`.build-logs/<package>.log`) for debugging.

## merge-external-package.py

Merges an external `.tsi.json` file (single-version format) into the TSI packages repository (multi-version format).

### Usage

```bash
python3 merge-external-package.py <external-tsi.json> <packages-dir> [package-name]
```

### Arguments

- `external-tsi.json`: Path to the external package definition file (single-version format)
- `packages-dir`: Path to the TSI packages directory
- `package-name`: (Optional) Package name. If not provided, extracted from the JSON file

### Examples

```bash
# Merge a package, auto-detect name
python3 merge-external-package.py /tmp/example.json packages/

# Merge a package with explicit name
python3 merge-external-package.py /tmp/example.json packages/ my-package
```

### Behavior

- If the package file doesn't exist, creates a new one with the version
- If the package file exists but the version doesn't, **adds** the version to the `versions` array (preserving all existing versions)
- If the version already exists, updates it with the new definition
- New versions are inserted at the beginning of the `versions` array (latest first)
- **All existing versions are preserved** - the script never removes old versions
- If the existing package uses single-version format, it is automatically converted to multi-version format

### Exit Codes

- `0`: Package was successfully merged (new version added or updated)
- `1`: Version already exists (no changes made) or error occurred

## discover-versions.py

Finds new upstream releases for packages and adds them to package definitions.

### Usage

```bash
python3 discover-versions.py <package-name> [--dry-run]
python3 discover-versions.py --all [--skip gcc,llvm] [--dry-run]
```

### Arguments

- `package-name` / `--all`: one package, or every package
- `--skip a,b`: with `--all`, leave these packages alone
- `--max-versions N`: how many upstream tags/releases to look at (default: all)
- `--backfill`: add every missing stable version instead of just a newer latest release
- `--dry-run`: show what would be added without modifying files
- `--packages-dir PATH`: packages directory (default: `packages`)
- `--check-version V`: add exactly version V if upstream has it

### Behavior

- Adds **one** version per package: the newest stable upstream release, and only if it is newer than every version already recorded. Prereleases (rc/alpha/beta/pre) are never picked. Older missing releases are not backfilled unless `--backfill` is given.
- The new entry is copied from the newest existing version with the version replaced in the source URL / git tag. The template's `sha256` is **not** copied; run `add-checksums.py` to record the real one.
- Versions stay deduplicated and newest-first, the order `sort-versions.py` enforces.

Discovery sources: GitHub releases/tags (most packages) and curl.se. Others are skipped.

Self-check: `python3 scripts/test_discover_versions.py`.

### Integration

`.github/workflows/discover-versions.yml` runs this weekly, then for each updated package records the checksum (dropping it if the guessed URL does not download), builds it on Linux-x86_64, Linux-aarch64 and macOS-aarch64 with a linkage check, and commits the packages that pass everywhere directly to `main`. Failures go on one tracking issue that is rewritten each run and closed once empty. No PRs or branches are created.

## platform_id.py

Host platform identity plus queries against a package JSON. Single python entry point for the shell drivers.

```bash
python3 scripts/platform_id.py                              # -> macOS-aarch64
python3 scripts/platform_id.py --supports packages/libcap.json   # exit 0/1
python3 scripts/platform_id.py --platforms packages/libcap.json  # -> linux
python3 scripts/platform_id.py --deps packages/git.json          # deps + build deps
```

`--supports` reads the package's `platforms` field (see `docs/developer-guide/os-specific-config.md` in the TSI repo). An absent or empty field means "supported everywhere".

## build-all-packages.sh

Builds every package on the current host and writes `.build-logs/results.tsv`:

```
<package>\t<ok|fail|skipped|unsupported>\t<note>
```

One results.tsv per platform. Nothing in this script parses or edits `PACKAGES_STATUS.md` — that is `merge-status.py`'s job, so parallel CI legs never race on the same file.

## merge-status.py

Merges one results.tsv per platform into the multi-platform `PACKAGES_STATUS.md` table:

```bash
python3 scripts/merge-status.py PACKAGES_STATUS.md \
  Linux-x86_64=results/Linux-x86_64/results.tsv \
  Linux-aarch64=results/Linux-aarch64/results.tsv \
  macOS-aarch64=results/macOS-aarch64/results.tsv
```

Markers: `✅` built, `❌` failed, `—` unsupported on that platform, `⏭️` skipped because a dependency was unavailable, blank means not tested there. The table is rebuilt from scratch every run.

Self-check: `python3 scripts/test_merge_status.py`.

## add-checksums.py

Records `source.sha256` for tarball/zip sources so TSI verifies a download before extracting it.

```bash
python3 scripts/add-checksums.py brotli fmt   # named packages, newest version
python3 scripts/add-checksums.py --all        # every package, newest version
python3 scripts/add-checksums.py --all --check  # verify, write nothing
python3 scripts/add-checksums.py fmt --all-versions
```

Existing checksums are left alone unless `--check` is given. Run it whenever a package or a version is added.

This pins the artifact, it does not establish provenance: it guarantees later downloads are byte-identical to the one taken when the package was added. Cross-check the value against upstream's own published checksum when there is one.

## check-linkage.sh

Reports installed binaries whose dynamic dependencies cannot be resolved.

```bash
bash scripts/check-linkage.sh ~/.tsi              # everything installed
bash scripts/check-linkage.sh ~/.tsi postgresql   # named packages only
```

A package that compiles, links and installs can still produce libraries that will not load. icu recorded a bare `install_name`, so `postgres` died at startup with "Library not loaded: libicui18n.74.dylib" while its package showed ✅. This is what stops that shipping green again.

Inspection only — `ldd` on Linux, `otool -L` on macOS — so it never executes an installed binary and cannot hang on a program that ignores `--version`. A file whose *own* install_name is relative is not flagged unless something actually depends on it (coreutils ships `libstdbuf.so` that way, and nothing links it).

Self-check: `bash scripts/test_check_linkage.sh`.

