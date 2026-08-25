"""Agent-branch endpoint coverage (Sonar new-code gate).

Exercises the A3/A11 agent-first branches and the B2/B4 endpoints with the
desktop-agent layer monkeypatched, plus the A7 honest-failure endpoints.
No real CAD, no real agent sockets.

The shared ``fake_send`` mirrors the real C# add-in envelopes per command so
response-model assertions exercise the production contracts, not a generic
stub shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.rbac import Role

# Module-level capture list so assertions never depend on TestClient
# attribute plumbing; the fixture resets it before each test.
# Entries are (agent_type, action, args) 3-tuples — compare with _called().
AGENT_CALLS: list[tuple[str, str, dict]] = []


def _called(agent_type: str, action: str) -> bool:
    """True when the fixture captured at least one matching agent call."""
    return any(t[0] == agent_type and t[1] == action for t in AGENT_CALLS)


@pytest.fixture
def client(monkeypatch):
    """Test app with revit+autocad+facp routers, auth stubbed to ENGINEER,
    desktop agent 'connected' and send_agent_command captured."""
    from backend.routers import autocad as autocad_router
    from backend.routers import facp as facp_router
    from backend.routers import revit as revit_router

    AGENT_CALLS.clear()

    async def fake_send(agent_type: str, action: str, args: dict, *_a, **_k):
        AGENT_CALLS.append((agent_type, action, args))
        # Shape-matched envelopes mirroring the real C# add-in responses.
        data: dict = {"id": 777, "handle": "FF"}
        if action in ("get_views", "get_levels", "get_grids", "get_worksets"):
            data = {"count": 1, "views": [{"id": 1}], "elements": [{"id": 1}]}
        elif action == "delete_element":
            data = {"deleted_id": int(args.get("element_id", -1))}
        elif action == "set_parameter":
            data = {"updated": True}
        elif action == "capture_screen":
            data = {"image_base64": "QUJD", "format": "png"}
        elif action == "send_command":
            # SendStringToExecute queues on the AutoCAD main thread.
            data = {"queued": True}
        return {"success": True, "data": data}

    monkeypatch.setattr(revit_router, "has_active_agent", lambda *a, **k: True)
    monkeypatch.setattr(revit_router, "send_agent_command", fake_send)
    monkeypatch.setattr(autocad_router, "has_active_agent", lambda *a, **k: True)
    monkeypatch.setattr(autocad_router, "send_agent_command", fake_send)

    app = FastAPI()

    @app.middleware("http")
    async def mock_auth(request, call_next):
        request.state.fireai_role = Role.ENGINEER
        return await call_next(request)

    app.include_router(revit_router.router, prefix="/api")
    app.include_router(autocad_router.router, prefix="/api")
    app.include_router(facp_router.router, prefix="/api")

    return TestClient(app)


def test_revit_create_wall_routes_via_agent(client):
    res = client.post(
        "/api/revit/elements/create/wall",
        json={
            "start_point": [0, 0, 0],
            "end_point": [1000, 0, 0],
            "include_screenshot": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True and body["element_id"] == "777"
    assert _called("revit", "create_wall")


def test_revit_create_door_and_window_route_via_agent(client):
    payload = {"host_wall_id": "9", "location_point": [1, 2, 3]}
    for suffix, action in (("door", "create_door"), ("window", "create_window")):
        res = client.post(f"/api/revit/elements/create/{suffix}", json=dict(payload))
        assert res.status_code == 200, res.text
        assert _called("revit", action)


def test_revit_create_column_beam_family_route_via_agent(client):
    cases = [
        (
            "/api/revit/elements/create/column",
            "create_column",
            {"location_point": [0, 0, 0]},
        ),
        (
            "/api/revit/elements/create/beam",
            "create_beam",
            {"start_point": [0, 0, 0], "end_point": [5, 0, 0]},
        ),
        (
            "/api/revit/elements/create/family",
            "create_family",
            {"family_name": "F", "category": "Doors", "location_point": [0, 0, 0]},
        ),
    ]
    for path, action, body in cases:
        res = client.post(path, json=body)
        assert res.status_code == 200, res.text
        assert _called("revit", action)


def test_revit_delete_and_update_parameters_via_agent(client):
    res = client.delete("/api/revit/elements/123")
    assert res.status_code == 200, res.text
    assert res.json()["deleted_id"] == 123
    assert _called("revit", "delete_element")

    res = client.put(
        "/api/revit/elements/123/parameters",
        json={"parameters": {"Mark": "M-1"}},
    )
    assert res.status_code == 200, res.text
    assert _called("revit", "update_parameters")


def test_revit_views_levels_grids_worksets_via_agent(client):
    for path in ("/views", "/levels", "/grids", "/worksets"):
        res = client.get(f"/api/revit{path}")
        assert res.status_code == 200, f"{path}: {res.text}"


def test_revit_execute_ai_command_via_agent(client):
    res = client.post("/api/revit/execute", json={"command": "create wall"})
    assert res.status_code == 200, res.text
    assert _called("revit", "execute_ai_command")


def test_autocad_draw_endpoints_route_via_agent(client):
    ok = client.post(
        "/api/autocad/draw_line",
        json={"start_point": [0, 0], "end_point": [10, 10]},
    )
    assert ok.status_code == 200 and ok.json()["handle"] == "FF"
    ok = client.post("/api/autocad/draw_polyline", json={"vertices": [[0, 0], [5, 5]]})
    assert ok.status_code == 200
    ok = client.post("/api/autocad/draw_circle", json={"center": [0, 0], "radius": 4})
    assert ok.status_code == 200
    ok = client.post(
        "/api/autocad/draw_text", json={"text": "hi", "insertion_point": [0, 0]}
    )
    assert ok.status_code == 200


def test_autocad_delete_modify_save_via_agent(client, tmp_path):
    res = client.delete("/api/autocad/entity/1A2F")
    assert res.status_code == 200, res.text
    assert _called("autocad", "delete_entity")

    res = client.put(
        "/api/autocad/entity/1A2F",
        json={"handle": "1A2F", "properties": {"color": 3}},
    )
    assert res.status_code == 200, res.text
    assert _called("autocad", "modify_entity")

    # /save validates the target path exists before agent dispatch (path
    # guard), so point it at a real temp drawing file.
    drawing = tmp_path / "out.dwg"
    drawing.write_bytes(b"")
    res = client.post(
        "/api/autocad/save",
        json={"filepath": str(drawing)},
    )
    assert res.status_code == 200, res.text
    assert _called("autocad", "save_as")


def test_autocad_native_command_passthrough(client):
    res = client.post("/api/autocad/send_command", json={"command_string": "_.ZOOM _E"})
    assert res.status_code == 200, res.text
    assert res.json()["queued"] is True
    assert _called("autocad", "send_command")


def test_autocad_capture_screen_endpoint(client):
    got = client.get("/api/autocad/capture_screen")
    # fake_send mirrors the add-in capture envelope; endpoint must pass the
    # base64 image through untouched on success.
    assert got.status_code == 200
    body = got.json()
    assert body["success"] is True and body["image_base64"] == "QUJD"
    assert _called("autocad", "capture_screen")


def test_autocad_remote_status_connected(client):
    res = client.get("/api/autocad/remote/status")
    assert res.status_code == 200 and res.json()["agent_connected"] is True


def test_facp_cluster_status_honest_501(client):
    res = client.get("/api/facp/cluster/status")
    assert res.status_code == 501
    detail = res.json()["detail"]
    assert detail["demo"] is True
