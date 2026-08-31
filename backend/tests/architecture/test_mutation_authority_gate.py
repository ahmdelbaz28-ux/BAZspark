"""backend/tests/architecture/test_mutation_authority_gate.py — Architectural Mutation Authority Gate.

Enforces Phase 4 Gate 4 requirements:
1. Validates schema and authority classes in mutation_authority_inventory.yaml.
2. AST crawler on backend/routers/** and WebSocket handlers to ensure 100% coverage.
3. Bi-directional consistency between LEGACY_EXCEPTION entries and bypass_exceptions.yaml.
"""

import ast
from pathlib import Path
import pytest
import yaml

VALID_AUTHORITY_CLASSES = {
    "CANONICAL_COMMAND",
    "EXTERNAL_TRANSACTION",
    "SYSTEM_INFRASTRUCTURE",
    "LEGACY_EXCEPTION",
}

ARCH_DIR = Path(__file__).parent
INVENTORY_FILE = ARCH_DIR / "mutation_authority_inventory.yaml"
EXCEPTIONS_FILE = ARCH_DIR / "bypass_exceptions.yaml"
ROUTERS_DIR = ARCH_DIR.parent.parent / "routers"


def load_yaml(path: Path) -> dict:
    assert path.exists(), f"Required architecture file missing: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_inventory_schema_and_classes():
    data = load_yaml(INVENTORY_FILE)
    assert "version" in data, "Inventory must contain a version field"
    inventory = data.get("inventory", [])
    assert len(inventory) > 0, "Inventory must not be empty"

    seen_ids = set()
    for item in inventory:
        # Mandatory fields
        for field in ("id", "path_anchor", "method", "mutation_target", "authority_class", "evidence"):
            assert field in item and item[field], f"Item {item.get('id')} missing mandatory field '{field}'"

        # Unique IDs
        assert item["id"] not in seen_ids, f"Duplicate mutation item ID: {item['id']}"
        seen_ids.add(item["id"])

        # Authority class validity
        auth_class = item["authority_class"]
        assert auth_class in VALID_AUTHORITY_CLASSES, (
            f"Invalid authority_class '{auth_class}' for item {item['id']}. "
            f"Must be one of {VALID_AUTHORITY_CLASSES}"
        )

        # Legacy exceptions must specify owner and deadline
        if auth_class == "LEGACY_EXCEPTION":
            assert "owner" in item and item["owner"], f"LEGACY_EXCEPTION {item['id']} must specify 'owner'"
            assert "deadline" in item and item["deadline"], f"LEGACY_EXCEPTION {item['id']} must specify 'deadline'"


def test_ast_crawler_router_coverage():
    """AST crawler over backend/routers/** to verify all write routes are cataloged."""
    data = load_yaml(INVENTORY_FILE)
    inventory = data.get("inventory", [])
    inventory_anchors = {item["path_anchor"] for item in inventory}

    # Also build map by filename and function name
    cataloged_functions = set()
    for item in inventory:
        # Extract filename and func from path_anchor e.g. "backend/routers/elements.py:45 (create_element)"
        anchor = item.get("path_anchor", "")
        if "(" in anchor and ")" in anchor:
            func = anchor.split("(")[1].split(")")[0].strip()
            cataloged_functions.add(func)

    unaccounted_endpoints = []

    for router_file in sorted(ROUTERS_DIR.glob("*.py")):
        if router_file.name == "__init__.py":
            continue
        source = router_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(router_file))
        except Exception as exc:
            pytest.fail(f"Failed to parse {router_file}: {exc}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    call_node = decorator if isinstance(decorator, ast.Call) else None
                    if call_node and isinstance(call_node.func, ast.Attribute):
                        attr_name = call_node.func.attr
                        if attr_name in ("post", "put", "patch", "delete", "websocket"):
                            # Check if func is cataloged
                            if node.name not in cataloged_functions:
                                unaccounted_endpoints.append(
                                    f"{router_file.name}:{node.lineno} [{attr_name.upper()}] -> {node.name}"
                                )

    assert not unaccounted_endpoints, (
        f"Found {len(unaccounted_endpoints)} router endpoints missing from mutation_authority_inventory.yaml:\n"
        + "\n".join(unaccounted_endpoints)
    )


def test_bypass_exceptions_consistency():
    """Bi-directional consistency between inventory and bypass_exceptions.yaml."""
    inv_data = load_yaml(INVENTORY_FILE)
    exc_data = load_yaml(EXCEPTIONS_FILE)

    inventory = inv_data.get("inventory", [])
    exceptions = exc_data.get("exceptions", [])

    legacy_inventory_ids = {
        item["id"] for item in inventory if item["authority_class"] == "LEGACY_EXCEPTION"
    }
    exception_ids = {item["id"] for item in exceptions}

    # 1. Every LEGACY_EXCEPTION in inventory must be in exceptions file
    missing_in_exceptions = legacy_inventory_ids - exception_ids
    assert not missing_in_exceptions, (
        f"The following {len(missing_in_exceptions)} LEGACY_EXCEPTION items are missing from bypass_exceptions.yaml:\n"
        + "\n".join(sorted(missing_in_exceptions))
    )

    # 2. Every entry in exceptions file must be in inventory and marked LEGACY_EXCEPTION
    extra_in_exceptions = exception_ids - legacy_inventory_ids
    assert not extra_in_exceptions, (
        f"The following {len(extra_in_exceptions)} items in bypass_exceptions.yaml are not marked LEGACY_EXCEPTION in inventory:\n"
        + "\n".join(sorted(extra_in_exceptions))
    )

    # 3. Validate exception schema
    for exc in exceptions:
        for field in ("id", "reason", "owner", "deadline", "removal_condition"):
            assert field in exc and exc[field], f"Exception {exc.get('id')} missing mandatory field '{field}'"
