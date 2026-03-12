#!/usr/bin/env python3
"""
Merge an external .tsi.json file into the TSI packages repository.

This script takes a single-version package definition (from a project's .tsi.json)
and merges it into the multi-version format used in packages/*.json files.

Usage:
    python3 merge-external-package.py <external-tsi.json> <packages-dir> [package-name]

If package-name is not provided, it will be extracted from the JSON file.
"""

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_json import load_json, save_json


def merge_package_version(external_pkg, packages_dir, package_name=None):
    """
    Merge a single-version package definition into the packages repository.

    Args:
        external_pkg: Dictionary containing the external package definition
        packages_dir: Path to the packages directory
        package_name: Optional package name (if not provided, extracted from external_pkg)

    Returns:
        Tuple of (package_file_path, was_created, was_updated)
    """
    # Extract package name
    if not package_name:
        package_name = external_pkg.get('name')
        if not package_name:
            raise ValueError("Package name not found in external package definition")

    # Determine package file path
    package_file = Path(packages_dir) / f"{package_name}.json"

    # Load existing package file or create new structure
    if package_file.exists():
        existing_pkg = load_json(package_file)
        was_created = False

        # Convert single-version format to multi-version format if needed
        if 'versions' not in existing_pkg and 'version' in existing_pkg:
            # This is a single-version format, convert to multi-version
            existing_version = {k: v for k, v in existing_pkg.items() if k != 'name'}
            existing_pkg = {
                "name": existing_pkg.get('name', package_name),
                "versions": [existing_version]
            }
    else:
        existing_pkg = {
            "name": package_name,
            "versions": []
        }
        was_created = True

    # Extract version from external package
    new_version = external_pkg.get('version')
    if not new_version:
        raise ValueError("Version not found in external package definition")

    # Check if this version already exists
    versions = existing_pkg.get('versions', [])
    version_exists = any(v.get('version') == new_version for v in versions)

    was_updated = False
    if version_exists:
        # Update existing version
        for i, v in enumerate(versions):
            if v.get('version') == new_version:
                # Merge the new definition, keeping the version object structure
                versions[i] = {k: v for k, v in external_pkg.items() if k != 'name'}
                was_updated = True
                break
    else:
        # Add new version (insert at the beginning to keep latest first)
        version_obj = {k: v for k, v in external_pkg.items() if k != 'name'}
        versions.insert(0, version_obj)
        was_updated = True

    # Ensure versions array exists
    existing_pkg['versions'] = versions

    # Save the updated package file
    save_json(package_file, existing_pkg)

    return package_file, was_created, was_updated and not version_exists


def main():
    if len(sys.argv) < 3:
        print("Usage: merge-external-package.py <external-tsi.json> <packages-dir> [package-name]")
        sys.exit(1)

    external_file = sys.argv[1]
    packages_dir = sys.argv[2]
    package_name = sys.argv[3] if len(sys.argv) > 3 else None

    # Validate inputs
    if not os.path.exists(external_file):
        print(f"Error: External package file not found: {external_file}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(packages_dir):
        print(f"Error: Packages directory not found: {packages_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        # Load external package
        try:
            external_pkg = load_json(external_file)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {external_file}: {e}", file=sys.stderr)
            sys.exit(1)

        # Merge into packages repository
        package_file, was_created, was_updated = merge_package_version(
            external_pkg, packages_dir, package_name
        )

        # Print results
        if was_created:
            print(f"Created new package file: {package_file}")
        elif was_updated:
            print(f"Updated package file: {package_file}")
        else:
            print(f"Version already exists in: {package_file}")

        # Exit with appropriate code
        sys.exit(0 if was_updated else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

