# TSI Package Repository

This repository contains the official package definitions for [TSI](https://github.com/PanterSoft/tsi) (The Source Installer). Each package is defined as a JSON file in the `packages/` directory.

## For TSI Users

When you run `tsi update`, TSI clones this repository (by default) and copies the package definitions to your local repository at `~/.tsi/packages/`. You can then install packages with `tsi install <name>`.

To use a custom package repository:

```bash
tsi update --repo https://github.com/user/your-packages.git
tsi update --local /path/to/packages
```

## Package Format

Package format and fields are documented in the [TSI documentation](https://github.com/PanterSoft/tsi/blob/main/docs/user-guide/package-format.md). Each file in `packages/` should be valid JSON and follow the single-version or multi-version format.

## Contributing

- **Adding or editing packages:** Submit a pull request that adds or modifies JSON files under `packages/`.
- **Validation:** The Package Validation workflow runs on push/PR and checks JSON syntax, required fields, source types, build systems, and that all dependencies reference existing packages in this repository.
- **Version discovery:** The discover-versions workflow can add new versions to existing packages; see `scripts/README.md` for the discovery script usage.

## Repository Layout

```
packages/          # One .json file per package (e.g. zlib.json, openssl.json)
scripts/           # Package tooling (validate, discover-versions, merge-external)
.github/workflows/ # CI: Package Validation, discover-versions, sync-external-packages
```

TSI expects a `packages/` directory at the repository root when using `tsi update`.
