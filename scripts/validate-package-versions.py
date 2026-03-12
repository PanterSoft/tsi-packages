#!/usr/bin/env python3
"""Validate versions array in multi-version package files."""

import json
import sys

def validate_versions(pkg_file):
    """Validate structure and required fields of each version in a multi-version package file."""
    try:
        with open(pkg_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {pkg_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {pkg_file}: {e}")
        sys.exit(1)

    versions = data.get('versions', [])
    valid_types = ['git', 'tarball', 'zip', 'local']
    valid_build_systems = ['autotools', 'cmake', 'meson', 'make', 'custom']
    array_fields = ['dependencies', 'build_dependencies', 'configure_args', 'cmake_args', 'make_args', 'patches']

    failed = False

    for i, version in enumerate(versions):
        if 'version' not in version:
            print(f'❌ Version {i+1} missing version field in {pkg_file}')
            failed = True
            continue

        if 'source' not in version:
            print(f'❌ Version {i+1} missing source field in {pkg_file}')
            failed = True
            continue

        source = version.get('source', {})
        has_url = isinstance(source, dict) and 'type' in source and (
            'url' in source or (source.get('type') == 'local' and 'path' in source)
        )
        if not has_url:
            print(f'❌ Version {i+1} has invalid or missing source object in {pkg_file}')
            failed = True
            continue

        source_type = source.get('type', '')
        if source_type not in valid_types:
            print(f'❌ Version {i+1} has invalid source type {source_type} in {pkg_file}')
            failed = True
            continue

        build_system = version.get('build_system', '')
        if build_system and build_system not in valid_build_systems:
            print(f'❌ Version {i+1} has invalid build_system {build_system} in {pkg_file}')
            failed = True
            continue

        for field in array_fields:
            if field in version and not isinstance(version[field], list):
                print(f'❌ Version {i+1} field {field} must be an array in {pkg_file}')
                failed = True

        if 'env' in version and not isinstance(version.get('env'), dict):
            print(f'❌ Version {i+1} field env must be an object in {pkg_file}')
            failed = True

    if failed:
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <package-file>')
        sys.exit(1)

    validate_versions(sys.argv[1])

