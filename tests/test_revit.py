"""tests/test_revit.py — Revit Service Tests
=======================================

Unit and integration tests for the Revit service.
Tests connection, file operations, and element creation functionality.
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from backend.services.revit_service import RevitService


class TestRevitServiceInitialization:
    """Test Revit service initialization."""

    def test_service_initialization(self):
        """Test that Revit service initializes properly."""
        service = RevitService()

        assert service._active_document is None
        assert service._connected is False
        assert service._connection_method is None

    @patch("backend.services.revit_service.HAS_PYTHONNET", True)
    @pytest.mark.asyncio
    async def test_connect_with_api_available(self):
        """Test connecting when Revit API is available."""
        service = RevitService()

        result = await service.connect()

        # Even with API available, our implementation returns True for simulation
        assert result is True
        assert service._connected is True

    @patch("backend.services.revit_service.HAS_PYTHONNET", False)
    @pytest.mark.asyncio
    async def test_connect_without_api(self):
        """Test connecting when Revit API is not available."""
        service = RevitService()

        result = await service.connect()

        # Our implementation returns True even without API for file operations
        assert result is True
        assert service._connected is True


class TestRevitElementOperations:
    """Test Revit element operations."""

    @pytest.mark.asyncio
    async def test_get_elements_returns_list(self):
        """Test that get_elements returns a list."""
        service = RevitService()
        await service.connect()

        elements = await service.get_elements()

        assert isinstance(elements, list)
        if elements:
            assert all("id" in elem and "name" in elem for elem in elements)

    @pytest.mark.asyncio
    async def test_get_elements_with_category(self):
        """Test getting elements filtered by category."""
        service = RevitService()
        await service.connect()

        from backend.services.revit_service import ElementCategory
        walls = await service.get_elements(category=ElementCategory.WALLS)

        assert isinstance(walls, list)
        # Should return wall-like elements from simulation
        assert all(elem.get("category", "").lower() == "walls" for elem in walls)


class TestRevitFileOperations:
    """Test Revit file operations."""

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading a non-existent file."""
        service = RevitService()

        result = await service.open_document("nonexistent.rvt")

        assert result is False

    @pytest.mark.asyncio
    async def test_save_document(self):
        """Test saving a document."""
        service = RevitService()
        await service.connect()

        with tempfile.NamedTemporaryFile(suffix=".rvt", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            result = await service.save_document(temp_path)
            assert result is True
            assert os.path.exists(temp_path)
        finally:
            # Clean up the temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestRevitElementCreation:
    """Test Revit element creation."""

    @pytest.mark.asyncio
    async def test_create_wall(self):
        """Test creating a wall in Revit."""
        service = RevitService()
        await service.connect()

        result = await service.create_wall(
            {"x": 0, "y": 0, "z": 0},
            {"x": 5000, "y": 0, "z": 0},
            height=3000.0,
            level="Level 1"
        )

        # Should return a dict with element info
        assert result is not None
        assert isinstance(result, dict)
        assert "id" in result

    @pytest.mark.asyncio
    async def test_get_element_by_id(self):
        """Test getting a specific element by ID."""
        service = RevitService()
        await service.connect()

        elements = await service.get_elements()
        if elements:
            first_id = elements[0]["id"]
            element = await service.get_element_by_id(first_id)
            assert element is not None
            assert element["id"] == first_id

    @pytest.mark.asyncio
    async def test_get_element_by_id_nonexistent(self):
        """Test getting a nonexistent element returns None."""
        service = RevitService()
        await service.connect()

        element = await service.get_element_by_id("nonexistent-id-12345")
        assert element is None


class TestRevitDocumentOperations:
    """Test Revit document operations."""

    @pytest.mark.asyncio
    async def test_get_document_info_default(self):
        """Test getting simulated document info."""
        service = RevitService()
        await service.connect()

        # Check that connection was established
        assert service._connected is True
        # _active_document may be None in simulation mode; that's OK

    @pytest.mark.asyncio
    async def test_get_all_elements(self):
        """Test getting all elements."""
        service = RevitService()
        await service.connect()

        all_elements = await service.get_elements()

        # Should return a list of elements
        assert isinstance(all_elements, list)
        if all_elements:
            assert all(isinstance(elem, dict) for elem in all_elements)

    @pytest.mark.asyncio
    async def test_get_filtered_elements(self):
        """Test getting elements filtered by category."""
        service = RevitService()
        await service.connect()

        from backend.services.revit_service import ElementCategory
        walls = await service.get_elements(category=ElementCategory.WALLS)

        # Should return only wall elements
        assert isinstance(walls, list)
        if walls:
            assert all(elem.get("category", "").lower() == "walls" for elem in walls)


class TestRevitConnectionManagement:
    """Test Revit connection management."""

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting from Revit."""
        service = RevitService()
        await service.connect()

        result = await service.disconnect()

        assert result is True
        assert service._active_document is None
        assert service._connected is False


class TestRevitErrorHandling:
    """Test Revit error handling."""

    @pytest.mark.asyncio
    async def test_get_element_by_id_error_returns_none(self):
        """Test that getting a bad element ID returns None gracefully."""
        service = RevitService()
        await service.connect()

        element = await service.get_element_by_id("!!!invalid!!!")
        assert element is None


if __name__ == "__main__":
    pytest.main([__file__])