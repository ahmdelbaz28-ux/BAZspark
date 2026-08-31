"""backend/core/tool_schema_gen.py — Automatic Tool Interface & Schema Derivation Engine.

BAZspark V2.2 Phase 6 Tool Interface Generator:
- Automatically derives LLM tool/function calling schemas from Capability Contracts and ControlRequest.
- Eliminates manual and duplicated tool definitions per BAZSPARK_PLAN_V2_2 §5 Phase 6 Principle 11.
- Supports multiple LLM targets (OpenAI, Anthropic, JSON Schema).
- Single authoritative generator serving planner prompt synthesis and LLM tool calling.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from backend.core.capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.control_request import ControlRequest


def sanitize_tool_name(capability_id: str) -> str:
    """Convert a dotted capability ID (e.g. 'spatial.place_devices') to a valid tool identifier ('spatial_place_devices')."""
    return capability_id.replace(".", "_").replace("-", "_")


def derive_tool_schema_from_capability(
    capability: Any,
    target_format: Literal["openai", "anthropic", "json_schema"] = "openai",
) -> dict[str, Any]:
    """Derive an LLM tool calling schema automatically from a CapabilityDefinition or capability dict."""
    if isinstance(capability, dict):
        cid = str(capability.get("capability_id") or "")
        name = str(capability.get("name") or cid)
        description = str(capability.get("description") or f"Execute {name}")
        parameters = capability.get("input_schema") or {}
    else:
        cid = getattr(capability, "capability_id", "")
        name = getattr(capability, "name", cid)
        description = getattr(capability, "description", f"Execute {name}")
        parameters = getattr(capability, "input_schema", {})
        if not parameters and getattr(capability, "contract", None):
            parameters = getattr(capability.contract, "input_schema", {})

    tool_name = sanitize_tool_name(cid)

    if not parameters or not isinstance(parameters, dict):
        parameters = {"type": "object", "properties": {}}

    if target_format == "openai":
        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": parameters,
            },
        }
    elif target_format == "anthropic":
        return {
            "name": tool_name,
            "description": description,
            "input_schema": parameters,
        }
    elif target_format == "json_schema":
        return {
            "title": tool_name,
            "description": description,
            **parameters,
        }
    else:
        raise ValueError(f"Unsupported tool schema target format: '{target_format}'")


def derive_tool_schema_from_control_request(
    target_format: Literal["openai", "anthropic", "json_schema"] = "openai",
) -> dict[str, Any]:
    """Derive the meta ControlRequest tool schema automatically from ControlRequest Pydantic model."""
    schema = ControlRequest.get_json_schema()
    description = "Submit a Universal ControlRequest for autonomous planning, validation, and execution."

    if target_format == "openai":
        return {
            "type": "function",
            "function": {
                "name": "submit_control_request",
                "description": description,
                "parameters": schema,
            },
        }
    elif target_format == "anthropic":
        return {
            "name": "submit_control_request",
            "description": description,
            "input_schema": schema,
        }
    elif target_format == "json_schema":
        return {
            "title": "submit_control_request",
            "description": description,
            **schema,
        }
    else:
        raise ValueError(f"Unsupported tool schema target format: '{target_format}'")


def derive_all_tool_schemas(
    registry: CapabilityRegistry | None = None,
    scopes: list[str] | None = None,
    target_format: Literal["openai", "anthropic", "json_schema"] = "openai",
) -> list[dict[str, Any]]:
    """Derive tool schemas for all authorized capabilities in the registry without hardcoding."""
    reg = registry or default_capability_registry
    authorized_caps = reg.discover_authorized(scopes=scopes)

    tool_schemas: list[dict[str, Any]] = []
    for cap in authorized_caps:
        tool_schemas.append(
            derive_tool_schema_from_capability(cap, target_format=target_format)
        )
    return tool_schemas


def format_tool_schemas_for_system_prompt(
    capabilities_or_schemas: list[Any],
) -> str:
    """Format tool specifications for LLM prompt ingestion deterministically from contracts."""
    lines: list[str] = []
    for item in capabilities_or_schemas:
        if isinstance(item, CapabilityDefinition):
            cid = item.capability_id
            cat = item.category
            desc = item.description
            risk = item.risk_class
            schema = item.input_schema or (item.contract.input_schema if item.contract else {})
        elif isinstance(item, dict) and "capability_id" in item:
            cid = item["capability_id"]
            cat = item.get("category", "")
            desc = item.get("description", "")
            risk = item.get("risk", item.get("risk_class", "LOW"))
            schema = item.get("input_schema", {})
        elif isinstance(item, dict) and item.get("type") == "function":
            fn = item["function"]
            cid = fn.get("name", "")
            cat = "general"
            desc = fn.get("description", "")
            risk = "LOW"
            schema = fn.get("parameters", {})
        else:
            cid = getattr(item, "capability_id", str(item))
            cat = getattr(item, "category", "")
            desc = getattr(item, "description", "")
            risk = getattr(item, "risk_class", "LOW")
            schema = getattr(item, "input_schema", {})

        lines.append(
            f"- Capability ID: {cid}\n"
            f"  Category: {cat}\n"
            f"  Description: {desc}\n"
            f"  Risk Class: {risk}\n"
            f"  Input Schema: {json.dumps(schema or {})}\n"
        )
    return "\n".join(lines)


def validate_tool_schema_conformance(
    tool_schema: dict[str, Any],
    capability: Any,
) -> bool:
    """Verify that an LLM tool schema strictly conforms to the CapabilityContract with zero discrepancy."""
    derived = derive_tool_schema_from_capability(capability, target_format="openai")
    return (
        tool_schema.get("type") == derived.get("type")
        and tool_schema.get("function", {}).get("name") == derived.get("function", {}).get("name")
        and tool_schema.get("function", {}).get("description") == derived.get("function", {}).get("description")
        and tool_schema.get("function", {}).get("parameters") == derived.get("function", {}).get("parameters")
    )
