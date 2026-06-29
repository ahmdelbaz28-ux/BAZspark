"""tests/test_autocad.py — AutoCAD Service Tests
==========================================

Unit and integration tests for the AutoCAD service.
Tests connection, file operations, and drawing functionality.
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from backend.services.autocad_service import AutoCADService


class TestAutoCADServiceInitialization:
    """Test AutoCAD service initialization."""

    def test_service_initialization(self):
        """Test that AutoCAD service initializes properly."""
        service = AutoCADService()

        assert service.acad_app is None
        assert service.acad_doc is None
        assert service.connected is False
        assert service._sim_entities == {}

    @patch("backend.services.autocad_service.HAS_AUTOCAD_API", True)
    @patch("backend.services.autocad_service.win32com.client")
    @patch("backend.services.autocad_service.pythoncom")
    def test_connect_with_api_available(self, mock_pythoncom, mock_win32com):
        """Test connecting when AutoCAD API is available."""
        service = AutoCADService()

        # Mock the AutoCAD application
        mock_app = Mock()
        mock_doc = Mock()
        mock_util = Mock()

        mock_win32com.client.GetActiveObject.return_value = mock_app
        mock_app.ActiveDocument = mock_doc
        mock_doc.Utility = mock_util

        result = service.connect()

        # Verify the connection attempt
        assert result is True
        assert service.connected is True

    @patch("backend.services.autocad_service.HAS_AUTOCAD_API", False)
    def test_connect_without_api(self):
        """Test connecting when AutoCAD API is not available returns False."""
        service = AutoCADService()

        result = service.connect()

        assert result is False
        assert service.connected is False


class TestAutoCADEntityOperations:
    """Test AutoCAD entity operations."""

    def test_read_dwg_not_connected_returns_error(self):
        """Test reading a DWG when not connected returns error."""
        service = AutoCADService()

        result = service.read_dwg("test.dwg")

        assert result["success"] is False
        assert "not connected" in result["error"].lower()

    def test_read_dwg_nonexistent_file(self):
        """Test reading a non-existent file when connected."""
        service = AutoCADService()
        service.connected = True

        result = service.read_dwg("nonexistent_file.dwg")

        assert result["success"] is False
        assert "not found" in result.get("error", "").lower()


class TestAutoCADFileOperations:
    """Test AutoCAD file operations."""

    def test_write_dwg_with_entities(self):
        """Test writing entities to a DWG file."""
        service = AutoCADService()
        service.connected = True

        with tempfile.NamedTemporaryFile(suffix=".dwg", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            result = service.write_dwg(temp_path, [])
            assert result is True
        finally:
            # Clean up the temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_write_dwg_without_connection_returns_false(self):
        """Test writing DWG when not connected returns False."""
        service = AutoCADService()

        result = service.write_dwg("/tmp/test.dwg", [])
        assert result is False


class TestAutoCADDrawingOperations:
    """Test AutoCAD drawing operations."""

    def test_draw_line_when_connected(self):
        """Test drawing a line."""
        service = AutoCADService()
        service.connected = True

        result = service.draw_line(start_point=[0, 0, 0], end_point=[1000, 0, 0])

        assert result is not None
        assert result["type"] == "LINE"
        assert result["start"] == [0, 0, 0]
        assert result["end"] == [1000, 0, 0]

    def test_draw_circle_when_connected(self):
        """Test drawing a circle."""
        service = AutoCADService()
        service.connected = True

        result = service.draw_circle(center=[500, 500, 0], radius=250.0)

        assert result is not None
        assert result["type"] == "CIRCLE"
        assert result["center"] == [500, 500, 0]
        assert result["radius"] == 250.0

    def test_draw_text_when_connected(self):
        """Test drawing text."""
        service = AutoCADService()
        service.connected = True

        result = service.draw_text(text="Hello World", insertion_point=[100, 100, 0], height=2.5)

        assert result is not None
        assert result["type"] == "TEXT"
        assert result["text"] == "Hello World"
        assert result["at"] == [100, 100, 0]
        assert result["height"] == 2.5

    def test_draw_line_not_connected_returns_none(self):
        """Test drawing a line without connection returns None."""
        service = AutoCADService()

        result = service.draw_line(start_point=[0, 0, 0], end_point=[1000, 0, 0])

        assert result is None


class TestAutoCADConnectionManagement:
    """Test AutoCAD connection management."""

    @patch("backend.services.autocad_service.HAS_AUTOCAD_API", False)
    def test_disconnect(self):
        """Test disconnecting from AutoCAD."""
        service = AutoCADService()
        service.connected = True
        service.acad_app = Mock()

        result = service.disconnect()

        assert result is True
        assert service.acad_app is None
        assert service.acad_doc is None
        assert service.connected is False


class TestAutoCADDocumentInfo:
    """Test AutoCAD document info operations."""

    def test_get_document_info_not_connected_returns_empty(self):
        """Test getting document info without connection."""
        service = AutoCADService()

        doc_info = service.get_document_info()
        assert doc_info == {}

    def test_get_document_info_connected(self):
        """Test getting document info when connected."""
        service = AutoCADService()
        service.connected = True
        service.acad_doc = Mock()
        service.acad_doc.Name = "TestDrawing.dwg"
        service.acad_doc.Path = "C:\\Drawings"

        doc_info = service.get_document_info()
        assert doc_info["name"] == "TestDrawing.dwg"
        assert doc_info["path"] == "C:\\Drawings"


if __name__ == "__main__":
    pytest.main([__file__])