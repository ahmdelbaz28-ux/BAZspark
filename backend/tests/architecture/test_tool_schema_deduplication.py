"""backend/tests/architecture/test_tool_schema_deduplication.py — AST Architecture Test for Tool Schema Deduplication.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 6 & Gate 6:
1. Tool schemas for LLMs must be derived automatically from Capability Contracts and ControlRequest.
2. Manual duplicate tool definitions are strictly prohibited.
3. Every registered capability must have an auto-derivable tool schema with 100% contract conformance.
"""

from __future__ import annotations

import ast
import os

import pytest

from backend.core.capability_registry import default_capability_registry
from backend.core.tool_schema_gen import (
    derive_all_tool_schemas,
    derive_tool_schema_from_capability,
    derive_tool_schema_from_control_request,
    format_tool_schemas_for_system_prompt,
    validate_tool_schema_conformance,
)

BACKEND_CORE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "core")
)


def test_tool_schemas_auto_derived_from_all_capabilities() -> None:
    """Verify that every registered capability in CapabilityRegistry produces a valid conforming tool schema."""
    caps = default_capability_registry.discover_authorized(scopes=["*"])
    assert len(caps) > 0, "Capability registry should have registered capabilities"

    derived_schemas = derive_all_tool_schemas(default_capability_registry, scopes=["*"], target_format="openai")
    assert len(derived_schemas) == len(caps)

    for cap in caps:
        cid = str(cap.get("capability_id") if isinstance(cap, dict) else getattr(cap, "capability_id", ""))
        cdesc = str(cap.get("description") if isinstance(cap, dict) else getattr(cap, "description", ""))
        schema = derive_tool_schema_from_capability(cap, target_format="openai")
        assert schema["type"] == "function"
        fn = schema["function"]
        assert fn["name"] == cid.replace(".", "_").replace("-", "_")
        assert fn["description"] == cdesc
        assert isinstance(fn["parameters"], dict)
        assert validate_tool_schema_conformance(schema, cap) is True

        # Also test with typed CapabilityDefinition object
        cap_def = default_capability_registry.get(cid)
        if cap_def is not None:
            def_schema = derive_tool_schema_from_capability(cap_def, target_format="openai")
            assert validate_tool_schema_conformance(def_schema, cap_def) is True


def test_control_request_tool_schema_derivation() -> None:
    """Verify that ControlRequest meta tool schema is derived automatically from its Pydantic JSON Schema."""
    openai_tool = derive_tool_schema_from_control_request(target_format="openai")
    assert openai_tool["type"] == "function"
    assert openai_tool["function"]["name"] == "submit_control_request"
    assert "properties" in openai_tool["function"]["parameters"]

    anthropic_tool = derive_tool_schema_from_control_request(target_format="anthropic")
    assert anthropic_tool["name"] == "submit_control_request"
    assert "properties" in anthropic_tool["input_schema"]


def test_format_tool_schemas_for_system_prompt() -> None:
    """Verify that system prompt tool formatting is deterministic and contains input schemas."""
    caps = default_capability_registry.discover_authorized(scopes=["*"])
    formatted = format_tool_schemas_for_system_prompt(caps)
    assert len(formatted) > 50
    assert "- Capability ID:" in formatted
    assert "Input Schema:" in formatted


def test_ast_no_manual_tool_schema_definitions() -> None:
    """AST Test: backend/core must not contain manual OpenAI tool definition dicts bypassing tool_schema_gen."""
    # Walk all python files in backend/core except tool_schema_gen.py
    for fname in os.listdir(BACKEND_CORE_DIR):
        if not fname.endswith(".py") or fname == "tool_schema_gen.py":
            continue

        fpath = os.path.join(BACKEND_CORE_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=fpath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                # Check for manual {"type": "function", "function": ...} patterns
                keys = [
                    k.value if isinstance(k, ast.Constant) and isinstance(k.value, str) else None
                    for k in node.keys
                    if k is not None
                ]
                if "type" in keys and "function" in keys:
                    pytest.fail(
                        f"Manual tool schema definition detected in {fname}:{node.lineno}. "
                        f"All tool schemas must be derived via backend.core.tool_schema_gen."
                    )
