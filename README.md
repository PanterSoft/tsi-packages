# TSI Package Repository

This repository contains the official package definitions for [TSI](https://github.com/PanterSoft/TheSourceInstaller) (The Source Installer). Each package is defined as a JSON file in the `packages/` directory.

## For TSI Users

When you run `tsi update`, TSI clones this repository (by default) and copies the package definitions to your local repository at `~/.tsi/packages/`. You can then install packages with `tsi install <name>`.

To use a custom package repository:

```bash
tsi update --repo https://github.com/user/your-packages.git
tsi update --local /path/to/packages
```

## Package Format

Package format and fields are documented in the [TSI documentation](https://github.com/PanterSoft/TheSourceInstaller/blob/main/docs/user-guide/package-format.md). Each file in `packages/` should be valid JSON and follow the single-version or multi-version format.

## Contributing

- **Adding or editing packages:** Submit a pull request that adds or modifies JSON files under `packages/`.
- **Validation:** The Package Validation workflow runs on push/PR and checks JSON syntax, required fields, source types, build systems, and that all dependencies reference existing packages in this repository.
- **Test build:** The Test Build Packages workflow runs on push/PR when package definitions change and really builds each changed package (latest version only) on **Linux-x86_64, Linux-aarch64 and macOS-aarch64**. All three must pass: building on one architecture proves nothing about the others. TSI is built from source in CI; known slow packages (e.g. gcc, llvm) are skipped. See `scripts/README.md` for the changed-packages script.
- **Validate before you push:** from a TSI checkout with this repository as its `tsi-packages` submodule, `make validate PKGS="yourpackage"` builds it in containers on `linux/arm64` and `linux/amd64` locally, so you find an architecture-specific break before CI does.
- **Platform-restricted packages:** a package that genuinely cannot build everywhere (Linux kernel APIs, say) declares `"platforms": ["linux"]`. Do not use it to paper over a build that is merely broken — it removes the package from the validation matrix on every other platform.
- **Version discovery:** The discover-versions workflow can add new versions to existing packages; see `scripts/README.md` for the discovery script usage.

## What CI checks

| Workflow | When | What it proves |
|---|---|---|
| `package-validation` | every push / PR | schema, `platforms` values, duplicate package names, duplicate/misordered version entries, a version that appears nowhere in its own URL, unresolvable deps, script self-checks, shellcheck, actionlint, and that **changed** packages' sources are pinned and reachable |
| `test-build-packages` | every push / PR touching packages | changed packages really build on Linux-x86_64, Linux-aarch64 and macOS-aarch64, **and** their installed binaries can actually load |
| `verify-sources` | weekly | every package's default source still downloads and still matches its recorded sha256 |
| `validate-all-packages` | weekly + manual | the whole catalogue built on all three platforms, regenerating `PACKAGES_STATUS.md` |

Nothing here needs a local run to be trusted, but `make validate PKGS="…"` from a TSI checkout gives you the cross-architecture answer before you push.

## Package status

`PACKAGES_STATUS.md` holds one column per platform, regenerated from real build
results by the weekly **Validate All Packages** workflow:

| Marker | Meaning |
|--------|---------|
| ✅ | built and installed on that platform |
| ❌ | failed to build there |
| — | declares it does not support that platform (`platforms`) |
| ⏭️ | skipped: a dependency was unavailable in that run |
| *(blank)* | not tested on that platform |

## Repository Layout

```
packages/          # One .json file per package (e.g. zlib.json, openssl.json)
scripts/           # Package tooling (validate, build-all, merge-status, discover-versions)
.github/workflows/ # CI: package-validation, test-build-packages, validate-all-packages,
                   #     discover-versions, sync-external-packages
```

TSI expects a `packages/` directory at the repository root when using `tsi update`.
