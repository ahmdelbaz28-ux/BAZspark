"""Unit coverage for the external-control plane (Sonar new-code gate).

Covers the pure-logic additions of the external-control upgrade without
requiring Windows pipes or live CAD apps:
- core.command_registry resolution / normalization / expansion
- backend.routers.agent_ws allow-list validation, ticket lifecycle,
  nonce TTL pruning, agent-bucket resolution
- revit/autocad router response-shaping helpers
- schemas Generic[T] response wrappers
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import command_registry

# ──────────────────────────────────────────────────────────────────────────────
# core.command_registry
# ──────────────────────────────────────────────────────────────────────────────


def test_registry_loads_and_lists_services():
    assert set(command_registry.get_service_names()) == {"revit", "autocad"}


def test_registry_alias_resolution_both_directions():
    # canonical -> addin action
    assert command_registry.resolve_addin_action("revit", "get_views") == "list_views"
    assert command_registry.resolve_addin_action("revit", "get_elements") == "list_elements"
    # alias lookup resolves to same entry as canonical name
    via_alias = command_registry.get_command_entry("revit", "list_elements")
    via_canonical = command_registry.get_command_entry("revit", "get_elements")
    assert via_alias is via_canonical


def test_registry_unknown_service_and_command():
    assert command_registry.get_command_entry("nosuchsvc", "x") is None
    assert command_registry.is_allowed("revit", "rm_rf_all_worksets") is False
    assert command_registry.resolve_addin_action("autocad", "nope") is None


@pytest.mark.parametrize(
    ("canonical", "rest_params", "expected_subset"),
    [
        (
            "create_wall",
            {"start_point": [1, 2], "end_point": [3, 4], "height": 2500},
            {"x1": 1.0, "y1": 2.0, "x2": 3.0, "y2": 4.0, "height": 2500},
        ),
        ("create_floor", {"boundary_points": [[0, 0]]}, {"points": [[0, 0]]}),
        (
            "create_door",
            {"host_wall_id": "9", "location_point": [5, 6, 7], "family_type": "D"},
            {"host_id": "9", "family": "D", "symbol": "D"},
        ),
        (
            "place_family_instance",
            {"family_name": "F", "location_point": [1, 1]},
            {"x": 1.0, "y": 1.0, "z": 0.0, "family": "F", "family_name": "F"},
        ),
        ("set_parameter", {"element_id": 7, "name": "n", "value": "v"}, {"id": 7}),
    ],
)
def test_normalize_params_shapes(canonical, rest_params, expected_subset):
    service = "revit"
    out = command_registry.normalize_params(service, canonical, dict(rest_params))
    for key, value in expected_subset.items():
        assert out[key] == value, f"{canonical}: {key} expected {value}, got {out.get(key)}"


def test_normalize_autocad_passthrough_is_copy():
    src = {"start_point": [0, 0]}
    out = command_registry.normalize_params("autocad", "draw_line", src)
    assert out == src
    assert out is not src


def test_expand_update_parameters_fans_out_with_ids():
    target, calls = command_registry.expand_update_parameters(
        {"element_id": 12, "parameters": {"a": 1, "b": 2}}
    )
    assert target == "set_parameter"
    assert len(calls) == 2
    assert all(c["element_id"] == 12 and c["id"] == 12 for c in calls)


def test_validate_params_reports_missing_required():
    err = command_registry.validate_params("autocad", "draw_circle", {"center": [0, 0]})
    assert err is not None and "radius" in err
    assert (
        command_registry.validate_params("autocad", "draw_circle", {"center": [0, 0], "radius": 5})
        is None
    )


# ──────────────────────────────────────────────────────────────────────────────
# backend.routers.agent_ws — validation, tickets, nonces, buckets
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def agent_ws_module(monkeypatch):
    import backend.routers.agent_ws as aw

    aw._ws_tickets.clear()
    yield aw
    aw._ws_tickets.clear()


def test_validate_command_against_registry_paths(agent_ws_module):
    from fastapi import HTTPException as _HE

    # Allowed + params complete -> no exception
    agent_ws_module._validate_command_against_registry("revit", "delete_element", {"element_id": 1})
    # Unknown command -> 400
    with pytest.raises(_HE) as exc_unknown:
        agent_ws_module._validate_command_against_registry("revit", "nuke_model", {})
    assert exc_unknown.value.status_code == 400
    # Missing required param -> 400
    with pytest.raises(_HE) as exc_missing:
        agent_ws_module._validate_command_against_registry("autocad", "delete_entity", {})
    assert exc_missing.value.status_code == 400


def test_agent_bucket_resolution(agent_ws_module):
    assert agent_ws_module.has_active_agent("revit") is False
    assert agent_ws_module.has_active_agent("autocad") is False
    assert agent_ws_module.has_active_agent() is False  # default bucket


def _ticket_info(name="tester"):
    return SimpleNamespace(role="engineer", name=name, email=f"{name}@t")


def test_ws_ticket_single_use_burn(agent_ws_module):
    ticket = agent_ws_module._issue_ws_ticket(_ticket_info(), origin=None)
    first = agent_ws_module._consume_ws_ticket(ticket, origin=None)
    second = agent_ws_module._consume_ws_ticket(ticket, origin=None)
    assert first is not None and first.role == "engineer"
    assert second is None, "ticket must be burned on first use"


def test_ws_ticket_rejects_expired(agent_ws_module, monkeypatch):
    ticket = agent_ws_module._issue_ws_ticket(_ticket_info(), origin=None)
    # Force expiry by rewinding the stored deadline.
    agent_ws_module._ws_tickets[ticket]["expires"] -= 10_000
    assert agent_ws_module._consume_ws_ticket(ticket, origin=None) is None


def test_ws_ticket_origin_binding(agent_ws_module):
    ticket = agent_ws_module._issue_ws_ticket(_ticket_info(), origin="https://app.example")
    assert agent_ws_module._consume_ws_ticket(ticket, origin="https://evil.example") is None
    # Burned by the failed attempt (pop-before-validate) — single use holds.
    assert agent_ws_module._consume_ws_ticket(ticket, origin="https://app.example") is None


def test_nonce_ttl_prune_evicts_old_entries(agent_ws_module):
    import time as time_mod

    aw = agent_ws_module
    aw._seen_agent_nonces.clear()
    aw._nonce_timestamps.clear()
    now = time_mod.monotonic()
    # Cap of 50 with 51 entries forces the prune pass; only the entry whose
    # TTL elapsed may be evicted (post-prune size lands back at the cap,
    # so the hard-cap fallback must NOT fire).
    for i in range(50):
        n = f"fresh-{i}"
        aw._seen_agent_nonces.add(n)
        aw._nonce_timestamps[n] = now
    old = "ancient"
    aw._seen_agent_nonces.add(old)
    aw._nonce_timestamps[old] = now - 10_000

    aw._SEEN_AGENT_NONCES_MAX = 50
    try:
        aw._prune_seen_nonces()
        assert old not in aw._seen_agent_nonces
        assert len(aw._seen_agent_nonces) == 50
        assert "fresh-0" in aw._seen_agent_nonces
    finally:
        aw._SEEN_AGENT_NONCES_MAX = 20000


def test_nonce_duplicate_rejected(agent_ws_module):
    msg = {"type": "response", "nonce": "abc123"}
    assert agent_ws_module._validate_agent_nonce(msg) is True
    assert agent_ws_module._validate_agent_nonce(msg) is False
    # Nonce-less frames always pass.
    assert agent_ws_module._validate_agent_nonce({"type": "pong"}) is True


# ──────────────────────────────────────────────────────────────────────────────
# Router response-shaping helpers
# ──────────────────────────────────────────────────────────────────────────────


def test_flatten_revit_agent_envelope():
    from backend.routers.revit import _flatten_agent_result

    envelope = {"success": True, "data": {"id": 5, "length_mm": 100.0}}
    flat = _flatten_agent_result(envelope)
    assert flat["success"] is True and flat["id"] == 5 and "data" not in flat
    passthrough = {"success": True, "message": "local"}
    assert _flatten_agent_result(passthrough) == passthrough
    malformed = _flatten_agent_result("junk")
    assert malformed["success"] is False


def test_as_element_response_pipe_shape_and_simulation_flag():
    from backend.routers.revit import ElementResponse, _as_element_response

    res = _as_element_response({"success": True, "data": {"id": 42}}, "Wall created")
    assert isinstance(res, ElementResponse)
    assert res.success is True and res.element_id == "42" and res.simulation_mode is False

    sim = _as_element_response({}, "Wall created", simulation_mode=True)
    assert sim.success is False and sim.simulation_mode is True and sim.message


def test_maybe_capture_screenshot_noop_without_agent(monkeypatch):
    """Sync wrapper: exercises the async helper via asyncio.run."""
    import asyncio

    from backend.routers import revit as revit_router

    monkeypatch.setattr(revit_router, "has_active_agent", lambda *_a, **_k: False)
    assert asyncio.run(revit_router._maybe_capture_screenshot(True)) is None
    assert asyncio.run(revit_router._maybe_capture_screenshot(False)) is None


def test_maybe_capture_screenshot_returns_image(monkeypatch):
    import asyncio

    from backend.routers import revit as revit_router

    async def fake_send(*_a, **_k):
        return {"success": True, "data": {"image_base64": "QUJD", "format": "png"}}

    monkeypatch.setattr(revit_router, "has_active_agent", lambda *_a, **_k: True)
    monkeypatch.setattr(revit_router, "send_agent_command", fake_send)
    assert asyncio.run(revit_router._maybe_capture_screenshot(True)) == "QUJD"


def test_agent_operation_response_shapes():
    from backend.routers.autocad import OperationResponse, _agent_operation_response

    ok = _agent_operation_response({"success": True, "data": {"handle": "2A"}}, "Line drawn")
    assert isinstance(ok, OperationResponse) and ok.handle == "2A"

    bad = _agent_operation_response({"success": False, "error": "boom"}, "Line drawn")
    assert bad.success is False and "boom" in bad.message


# ──────────────────────────────────────────────────────────────────────────────
# Schemas Generic[T] wrappers
# ──────────────────────────────────────────────────────────────────────────────


def test_api_response_generic_subscription_and_payload():
    from backend.schemas import ApiResponse

    payload = ApiResponse[dict](success=True, data={"x": 1})
    assert payload.data == {"x": 1} and payload.success is True
    bare = ApiResponse(success=False)
    assert bare.data is None and bare.message is None


def test_paginated_data_generic_subscription():
    from backend.schemas import PaginatedData

    # Init via the camelCase alias, attribute access via the pythonic name.
    page = PaginatedData[int](items=[1, 2, 3], total=3, page=1, page_size=10, totalPages=1)
    assert page.items == [1, 2, 3] and page.total_pages == 1
