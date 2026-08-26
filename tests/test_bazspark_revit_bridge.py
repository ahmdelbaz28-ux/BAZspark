from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
ADDIN_DIR = REPO_ROOT / "revit_addin" / "BazSparkRevitBridge"


def test_revit_addin_structure():
    """Verify that the C# Revit Add-in bridge project files are present and match specifications."""
    assert ADDIN_DIR.exists()

    csproj = ADDIN_DIR / "BazSparkRevitBridge.csproj"
    assert csproj.exists()

    content = csproj.read_text(encoding="utf-8")
    assert "RevitAPI" in content
    assert "RevitAPIUI" in content
    assert "Newtonsoft.Json" in content

    # Check application files
    app_cs = ADDIN_DIR / "Application.cs"
    assert app_cs.exists()
    app_content = app_cs.read_text(encoding="utf-8")
    assert "IExternalApplication" in app_content
    assert "OnStartup" in app_content
    assert "OnShutdown" in app_content
    assert "bazspark_revit" in app_content

    # Check event handler files
    handler_cs = ADDIN_DIR / "BazSparkExternalEventHandler.cs"
    assert handler_cs.exists()
    handler_content = handler_cs.read_text(encoding="utf-8")
    assert "IExternalEventHandler" in handler_content
    assert "Execute" in handler_content
    assert "create_wall" in handler_content
    assert "create_floor" in handler_content

    # Check named pipe server files
    server_cs = ADDIN_DIR / "LocalAgentServer.cs"
    assert server_cs.exists()
    server_content = server_cs.read_text(encoding="utf-8")
    assert "NamedPipeServerStream" in server_content
    assert "bazspark_revit" in server_content

    # Check addin manifest files
    manifest = ADDIN_DIR / "BazSparkRevitBridge.addin"
    assert manifest.exists()
    manifest_content = manifest.read_text(encoding="utf-8")
    assert "BazSparkRevitBridge.dll" in manifest_content
    assert "FullClassName" in manifest_content


def test_local_agent_named_pipe_routing():
    """Verify the local agent routes commands via Named Pipe dispatcher when available."""
    from scripts.local_agent import RevitNamedPipeDispatcher, _dispatch_revit

    # Force available=True
    with patch.object(RevitNamedPipeDispatcher, "available", True):
        # Mock the send method to verify it is called
        mock_send = MagicMock(return_value={"success": True, "data": {"id": 123}})
        with patch.object(RevitNamedPipeDispatcher, "send", new=mock_send):
            res = _dispatch_revit("create_wall", {"start_point": [0, 0], "end_point": [10, 10]})

            assert res == {"success": True, "data": {"id": 123}}
            # A2 contract: params are normalized to the C# add-in shape
            # ({start_point,end_point} → {x1,y1,x2,y2}) before hitting the pipe.
            mock_send.assert_called_once_with(
                "create_wall",
                {"x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0},
            )


def test_local_agent_command_registry_routing():
    """A2/D4: unregistered commands are rejected; canonical names map to C# actions."""
    from core import command_registry

    assert command_registry.is_allowed("revit", "delete_element")
    assert command_registry.is_allowed("revit", "get_views")
    assert not command_registry.is_allowed("revit", "format_c_drive")
    assert command_registry.resolve_addin_action("revit", "get_views") == "list_views"
    assert command_registry.resolve_addin_action("autocad", "draw_line") == "draw_line"

    err = command_registry.validate_params("revit", "delete_element", {})
    assert err is not None and "element_id" in err
