"""D3: End-to-end proof of the REST -> WS -> Named Pipe control chain.

Runs a Python *fake* add-in named-pipe server that mimics each C# command
table, connects ``scripts/local_agent.py`` over a real WebSocket to a real
uvicorn instance serving the agent router, and drives commands through
``send_agent_command`` exactly like the backend routers do.

No Revit/AutoCAD required. Skipped automatically where named pipes are
unavailable (non-Windows / missing pywin32).
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException

pytestmark = [
    pytest.mark.timeout(120),
]

if sys.platform == "win32":
    try:
        import pywintypes  # noqa: F401
        import win32file  # noqa: F401
        import win32pipe  # noqa: F401

        _HAS_PIPES = True
    except ImportError:
        _HAS_PIPES = False
else:
    _HAS_PIPES = False

pytestmark.append(pytest.mark.skipif(not _HAS_PIPES, reason="Windows + pywin32 required"))


# ──────────────────────────────────────────────────────────────────────────────
# Fake C# add-in named-pipe server
# ──────────────────────────────────────────────────────────────────────────────


class FakeAddinPipeServer:
    """Mimics LocalAgentServer.cs: one JSON command per connection."""

    def __init__(self, pipe_name: str, responder: Callable[[str, dict], dict]):
        self.pipe_name = pipe_name
        self.responder = responder
        self.received: list[tuple[str, dict]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        import win32pipe  # type: ignore

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                win32pipe.WaitNamedPipe(self.pipe_name, 200)
                return
            except Exception:
                continue

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import pywintypes  # type: ignore
        import win32file  # type: ignore
        import win32pipe  # type: ignore

        while not self._stop.is_set():
            pipe = None
            try:
                pipe = win32pipe.CreateNamedPipe(
                    self.pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE
                    | win32pipe.PIPE_READMODE_MESSAGE
                    | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    1024 * 1024,
                    1024 * 1024,
                    0,
                    None,
                )
                win32pipe.ConnectNamedPipe(pipe, None)

                # Mirror LocalAgentServer.cs: serve many messages over one
                # connection until the client closes the pipe.
                win32pipe.SetNamedPipeHandleState(
                    pipe, win32pipe.PIPE_READMODE_MESSAGE, None, None
                )
                buffer = b""
                while True:
                    try:
                        _, chunk = win32file.ReadFile(pipe, 64 * 1024)
                    except pywintypes.error:
                        break  # client closed / pipe ended
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, _, rest = buffer.partition(b"\n")
                        buffer = rest
                        msg = json.loads(line.decode("utf-8").strip())
                        self.received.append(
                            (str(msg.get("action")), dict(msg.get("params") or {}))
                        )
                        response = self.responder(
                            str(msg.get("action")), dict(msg.get("params") or {})
                        )
                        win32file.WriteFile(
                            pipe, (json.dumps(response) + "\n").encode("utf-8")
                        )
            except pywintypes.error:
                if not self._stop.is_set():
                    time.sleep(0.05)
            except Exception:  # noqa: BLE001 — keep the fake server alive
                time.sleep(0.05)
            finally:
                if pipe is not None:
                    try:
                        win32pipe.DisconnectNamedPipe(pipe)
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        win32file.CloseHandle(pipe)
                    except Exception:  # noqa: BLE001
                        pass


def _revit_responder(action: str, _params: dict) -> dict:
    table: dict[str, Callable[[dict], Any]] = {
        "get_info": lambda p: {"title": "project.rvt", "path": "", "is_workshared": False},
        "list_views": lambda p: {
            "count": 1,
            "views": [{"id": 7, "name": "Level 1", "type": "FloorPlan"}],
        },
        "create_wall": lambda p: {"id": 111, "length_mm": 5000.0},
        "delete_element": lambda p: {"deleted_id": int(p.get("element_id", p.get("id", -1)))},
        "set_parameter": lambda p: {"updated": True},
        "capture_screen": lambda p: {"image_base64": "ZmFrZXBuZw==", "format": "png"},
    }
    fn = table.get(action)
    if fn is None:
        return {"success": False, "error": f"fake add-in has no arm for {action}"}
    return {"success": True, "data": fn(_params)}


def _autocad_responder(action: str, _params: dict) -> dict:
    table: dict[str, Callable[[dict], Any]] = {
        "get_info": lambda p: {"filename": "plan.dwg"},
        "draw_line": lambda p: {"handle": "2A", "success": True},
        "capture_screen": lambda p: {"image_base64": "ZmFrZXBuZw==", "format": "png"},
    }
    fn = table.get(action)
    if fn is None:
        return {"success": False, "error": f"fake add-in has no arm for {action}"}
    return {"success": True, "data": fn(_params)}


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures: real uvicorn serving the agent router + fake add-in pipes
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def agent_ws_server(monkeypatch):
    """Real uvicorn server exposing ONLY the agent_ws router (auth stubbed)."""
    import uvicorn

    import backend.routers.agent_ws as agent_ws_module

    monkeypatch.setattr(
        agent_ws_module,
        "validate_api_key",
        lambda key: SimpleNamespace(role="engineer", name="e2e-agent", email="e2e@test"),
    )
    monkeypatch.setattr(agent_ws_module, "has_permission", lambda role, perm: True)

    app = FastAPI()
    app.include_router(agent_ws_module.router, prefix="/api/v1")

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 15
    while time.time() < deadline and not server.started:
        time.sleep(0.1)
    assert server.started, "uvicorn did not start"

    port = None
    for sock in getattr(server, "servers", []) or []:
        for s in sock.sockets:
            port = s.getsockname()[1]
            break
    assert port, "could not determine uvicorn port"

    yield f"ws://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def fake_addins(monkeypatch):
    """Start fake pipe servers and reset local_agent dispatcher singletons."""
    import scripts.local_agent as local_agent_module

    revit_srv = FakeAddinPipeServer(r"\\.\pipe\bazspark_revit", _revit_responder)
    autocad_srv = FakeAddinPipeServer(r"\\.\pipe\bazspark_autocad", _autocad_responder)
    revit_srv.start()
    autocad_srv.start()

    # Reset cached dispatchers/services so routing re-detects the fresh pipes.
    monkeypatch.setattr(local_agent_module, "_revit_pipe", None)
    monkeypatch.setattr(local_agent_module, "_autocad_pipe", None)
    monkeypatch.setattr(local_agent_module, "_revit_svc", None)
    monkeypatch.setattr(local_agent_module, "_autocad_svc", None)

    yield {"revit": revit_srv, "autocad": autocad_srv}

    revit_srv.stop()
    autocad_srv.stop()


# ──────────────────────────────────────────────────────────────────────────────
# The chain test
# ──────────────────────────────────────────────────────────────────────────────


async def _drive_chain(ws_base: str, scenario: Callable[[], Any]) -> None:
    """Connect scripts/local_agent.py as THE agent, then drive backend-side calls."""
    import scripts.local_agent as local_agent_module

    uri = f"{ws_base}/api/v1/agent/ws"

    async def agent_session() -> None:
        await local_agent_module._agent_loop(uri, api_key="e2e-key")

    task = asyncio.create_task(agent_session())
    try:
        # Wait until the backend registers the agent connection.
        from backend.routers.agent_ws import has_active_agent

        for _ in range(50):
            if task.done():
                # Surface the real connection error instead of timing out.
                exc = task.exception()
                raise AssertionError(f"agent session died early: {exc!r}")
            if has_active_agent():
                break
            await asyncio.sleep(0.1)
        assert has_active_agent(), "agent never registered"

        await scenario()
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


def test_full_chain_rest_to_pipe(agent_ws_server, fake_addins):
    """A2/A3/A11 acceptance: REST-shaped commands reach the pipes correctly shaped."""

    async def scenario() -> None:
        from backend.routers.agent_ws import send_agent_command

        # 1. create_wall: REST shape in, C# shape out.
        wall = await send_agent_command(
            "revit",
            "create_wall",
            {"start_point": [0, 0, 0], "end_point": [5000, 0, 3000], "height": 3200},
        )
        assert isinstance(wall, dict) and wall["success"] is True
        assert wall["data"]["id"] == 111

        # 2. delete_element carries element_id (A1 contract).
        deleted = await send_agent_command("revit", "delete_element", {"element_id": 4242})
        assert deleted["data"]["deleted_id"] == 4242

        # 3. get_views maps to the add-in's list_views arm.
        views = await send_agent_command("revit", "get_views", {})
        assert views["data"]["views"][0]["name"] == "Level 1"

        # 4. update_parameters fans out into set_parameter calls.
        upd = await send_agent_command(
            "revit",
            "update_parameters",
            {"element_id": 9, "parameters": {"Comments": "a", "Mark": "b"}},
        )
        assert upd["success"] is True and upd["updated"] == 2

        # 5. AutoCAD draw_line reaches the AutoCAD add-in pipe.
        line = await send_agent_command(
            "autocad",
            "draw_line",
            {"start_point": [0, 0], "end_point": [100, 100]},
        )
        assert line["data"]["handle"] == "2A"

        # 6. capture_screen returns an inline PNG (T2).
        shot = await send_agent_command("revit", "capture_screen", {})
        assert shot["data"]["image_base64"] == "ZmFrZXBuZw=="

        # 7. D4: unregistered commands never leave the server.
        with pytest.raises(HTTPException) as excinfo:
            await send_agent_command("revit", "format_the_model", {})
        assert excinfo.value.status_code == 400

    asyncio.run(_drive_chain(agent_ws_server, scenario))

    # ── Assertions on what actually hit the fake C# add-ins ──
    revit_actions = [a for a, _p in fake_addins["revit"].received]
    assert revit_actions.count("create_wall") == 1
    assert revit_actions.count("list_views") >= 1          # get_views mapped
    assert revit_actions.count("set_parameter") == 2        # fan-out
    assert revit_actions.count("capture_screen") == 1
    assert "delete_element" in revit_actions

    wall_params = next(p for a, p in fake_addins["revit"].received if a == "create_wall")
    assert {"x1", "y1", "x2", "y2", "height"} <= set(wall_params)
    assert "start_point" not in wall_params                  # normalized away

    del_params = next(p for a, p in fake_addins["revit"].received if a == "delete_element")
    assert del_params.get("element_id") == 4242              # A1 unified key

    autocad_actions = [a for a, _p in fake_addins["autocad"].received]
    assert autocad_actions.count("draw_line") == 1
