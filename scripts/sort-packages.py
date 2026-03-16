#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Add script directory to path to import lib_json
sys.path.append(str(Path(__file__).parent))
try:
    from lib_json import load_json
except ImportError:
    # If standard import fails, define load_json locally
    def load_json(path):
        with open(path) as f:
            return json.load(f)

def get_pkg_deps(pkg_path):
    try:
        data = load_json(pkg_path)
        deps = set()
        # Only check the first version (assumed default/latest)
        versions = data.get("versions", [])
        if versions:
            v = versions[0]
            # Runtime deps
            # Ensure dependencies is a list
            runtime_deps = v.get("dependencies", [])
            if isinstance(runtime_deps, list):
                deps.update(runtime_deps)

            # Build deps
            build_deps = v.get("build_dependencies", [])
            if isinstance(build_deps, list):
                deps.update(build_deps)
        return deps
    except Exception as e:
        print(f"Error reading {pkg_path}: {e}", file=sys.stderr)
        return set()

def main():
    if len(sys.argv) < 2:
        print("Usage: sort-packages.py <packages_dir>", file=sys.stderr)
        sys.exit(1)

    pkgs_dir = Path(sys.argv[1])
    if not pkgs_dir.is_dir():
        print(f"Error: {pkgs_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Map package name -> set of dependency names
    graph = {}
    pkg_files = list(pkgs_dir.glob("*.json"))

    # First, collect all available package names
    available_pkgs = {p.stem for p in pkg_files}

    # Build dependency graph
    for p_file in pkg_files:
        pkg_name = p_file.stem
        raw_deps = get_pkg_deps(p_file)
        # Filter dependencies to include only those present in available_pkgs
        graph[pkg_name] = {d for d in raw_deps if d in available_pkgs}

    # Topological sort
    visited = set()
    temp_mark = set()
    sorted_list = []

    def visit(n):
        if n in temp_mark:
            print(f"Warning: Cyclic dependency involving {n}", file=sys.stderr)
            return
        if n not in visited:
            temp_mark.add(n)
            # Visit dependencies first
            # Sort dependencies for deterministic order on same level
            for m in sorted(graph.get(n, [])):
                visit(m)
            temp_mark.remove(n)
            visited.add(n)
            sorted_list.append(n)

    # Sort keys to insure deterministic output
    for node in sorted(graph.keys()):
        if node not in visited:
            visit(node)

    # Output
    for p in sorted_list:
        print(p)

if __name__ == "__main__":
    main()
