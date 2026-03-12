# TSI Scripts

This directory contains utility scripts for TSI package management.

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

Automatically discovers available versions for packages and adds them to package definitions.

### Usage

```bash
# Discover versions for a specific package
python3 discover-versions.py <package-name> [--max-versions N] [--dry-run]

# Discover versions for all packages
python3 discover-versions.py --all [--max-versions N] [--dry-run]
```

### Arguments

- `package-name`: Name of the package to update (or use `--all` for all packages)
- `--all`: Update all packages in the repository
- `--max-versions N`: Maximum number of versions to discover per package (default: 10)
- `--dry-run`: Show what would be added without modifying files
- `--packages-dir PATH`: Path to packages directory (default: `packages`)

### Examples

```bash
# Discover versions for curl
python3 discover-versions.py curl

# Discover versions for curl (dry run)
python3 discover-versions.py curl --dry-run

# Discover versions for all packages
python3 discover-versions.py --all --max-versions 5

# Discover versions with custom packages directory
python3 discover-versions.py git --packages-dir /path/to/packages
```

### Supported Discovery Methods

1. **GitHub Releases/Tags**: Automatically discovers versions from GitHub repositories using the GitHub API
2. **Git Tags**: For git-based sources, discovers versions from repository tags
3. **Website-specific**: Special handlers for specific websites (e.g., curl.se)

### Behavior

- Discovers available versions from package sources (GitHub, git repos, etc.)
- Generates version definitions based on the latest existing version
- Automatically updates source URLs with new version numbers
- Adds new versions to the `versions` array (preserving all existing versions)
- Skips versions that already exist
- Converts single-version packages to multi-version format automatically

### How It Works

1. Reads the package definition file
2. Extracts source information (URL, type, etc.)
3. Discovers available versions using appropriate method:
   - For GitHub: Uses GitHub API to fetch releases/tags
   - For git repos: Fetches tags from the repository
   - For specific sites: Uses custom discovery logic
4. Generates new version definitions by:
   - Copying the latest version as a template
   - Replacing version numbers in URLs and metadata
5. Adds new versions to the package file (if not already present)

### Integration

This script is integrated into a GitHub Actions workflow (`.github/workflows/discover-versions.yml`) that:
- Runs weekly to discover new versions
- Can be triggered manually for specific packages
- Creates pull requests automatically when new versions are found

### Limitations

- Currently works best with GitHub-hosted projects
- Some websites require custom discovery logic
- Rate limiting may apply when checking many packages
- Version format must be consistent (semantic versioning recommended)

