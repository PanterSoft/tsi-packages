# status-results

One `<platform-id>.tsv` per platform: the raw build results that
`scripts/merge-status.py` turns into `PACKAGES_STATUS.md`. The table is rebuilt
from this directory alone, so it can be regenerated anywhere without losing
columns.

- **CI platforms** are written here by the weekly *Validate All Packages*
  workflow (`# source: CI <date>`).
- **Every other platform** — another architecture, another BSD, a custom Unix,
  anything TSI runs on — is added by committing its results here. There is no
  list of allowed platforms: the file name *is* the column.

## Adding a platform

On the machine, with `tsi` on `PATH`:

```sh
bash scripts/build-all-packages.sh            # add --exclude-slow to skip gcc, llvm, ...
f="status-results/$(python3 scripts/platform_id.py).tsv"
{ echo "# source: <your name or machine>, $(date -u +%F)"; cat .build-logs/results.tsv; } > "$f"
python3 scripts/merge-status.py PACKAGES_STATUS.md
git add "$f" PACKAGES_STATUS.md
```

`platform_id.py` names the platform the same way the `platforms` field in
package files does (`darwin` → `macOS`, `arm64` → `aarch64`, `i686` → `x86`);
any OS or CPU it does not recognise is used under its own lower-cased name, e.g.
`haiku-x86_64` or `myos-riscv64`.

## File format

```
# source: CI 2026-09-06
zlib	ok
libcap	unsupported	linux-only
git	skipped	needs libcap
gcc		not built here (slow)
```

Tab-separated `<package>`, `<ok|fail|skipped|unsupported|empty>`, `<note>`.
Lines starting with `#` are comments; `# source:` labels the column's origin in
the summary table. Re-running on the same platform overwrites the file.
