"""
tests/test_python_import_boundaries.py — CI Import Boundaries & Cycle Guard.

Enforces:
1. Python backend packages (fireai, backend, core, adapters, etc.) have ZERO circular imports.
2. Architecture boundary invariants:
   - low-level core calculation engines do not import high-level web framework/routers (backend.routers).
"""

from __future__ import annotations

import ast
import glob
import os
from collections import defaultdict


def build_import_graph() -> tuple[dict[str, list[str]], set[str]]:
    """Build the internal dependency graph for all workspace Python modules."""
    package_roots = ["backend", "fireai", "core", "adapters", "parsers", "services", "qomn_fire", "facp_system"]
    modules: dict[str, list[str]] = {}

    for root_dir in package_roots:
        if not os.path.exists(root_dir):
            continue
        for fpath in glob.glob(f"{root_dir}/**/*.py", recursive=True):
            if "test" in os.path.basename(fpath) or "__pycache__" in fpath:
                continue
            rel = os.path.relpath(fpath, ".").replace("\\", "/")
            mod_name = os.path.splitext(rel)[0].replace("/", ".")

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    tree = ast.parse(fp.read())
            except Exception:
                continue

            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append(n.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            modules[mod_name] = imports

    all_modules = set(modules.keys())
    graph: dict[str, set[str]] = defaultdict(set)

    for mod, imps in modules.items():
        for imp in imps:
            for target in all_modules:
                if target == imp or target.startswith(imp + ".") or imp.startswith(target + "."):
                    if target != mod:
                        graph[mod].add(target)

    # Convert sets to lists
    graph_dict = {k: list(v) for k, v in graph.items()}
    return graph_dict, all_modules


def test_zero_circular_imports_in_python_backend():
    """Verify that there are no circular dependency cycles among Python modules."""
    graph, all_modules = build_import_graph()
    assert len(all_modules) > 50, f"Expected >50 modules scanned, got {len(all_modules)}"

    visited: dict[str, int] = {}
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited[node] = 1  # In recursion stack
        path.append(node)
        for neighbor in graph.get(node, []):
            if visited.get(neighbor) == 1:
                idx = path.index(neighbor)
                cycles.append(path[idx:] + [neighbor])
            elif visited.get(neighbor) != 2:
                dfs(neighbor, path)
        visited[node] = 2  # Completed
        path.pop()

    for mod in list(all_modules):
        if visited.get(mod) != 2:
            dfs(mod, [])

    formatted_cycles = [" -> ".join(c) for c in cycles]
    assert not cycles, f"Found {len(cycles)} circular import cycle(s):\n" + "\n".join(formatted_cycles)


def test_core_does_not_import_web_routers():
    """Verify that fireai/core calculation modules do not import web routers."""
    graph, _ = build_import_graph()
    boundary_violations = []

    for mod, targets in graph.items():
        if mod.startswith("fireai.core") or mod.startswith("fireai.constants"):
            for t in targets:
                if t.startswith("backend.routers") or t.startswith("backend.app"):
                    boundary_violations.append((mod, t))

    assert not boundary_violations, f"Architecture boundary violations detected: {boundary_violations}"
