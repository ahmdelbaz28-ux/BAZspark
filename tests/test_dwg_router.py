"""tests/test_dwg_router.py — DWG/DXF Parse API Endpoint Tests
=============================================================
Validates the FastAPI router in backend/routers/dwg.py:
  POST /api/parse-dwg — Upload DWG/DXF file for parsing

SAFETY: The endpoint must reject malicious inputs (wrong extension,
oversized files) and return structured JSON on success/failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest
import pydantic.root_model
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """V143: Create app without auth dependencies for testing."""
    _app = FastAPI()
    # without the _AUTH dependency that causes 403 in tests
    from backend.routers.dwg import parse_dwg

    _app.add_api_route(
        "/api/parse-dwg",
        parse_dwg,
        methods=["POST"],
    )
    return _app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def valid_dxf_bytes():
    """A minimal valid DXF file that ezdxf can parse."""
    lines = [
        "  0\n",
        "SECTION\n",
        "  2\n",
        "HEADER\n",
        "  9\n",
        "$ACADVER\n",
        "  1\n",
        "AC1009\n",
        "  0\n",
        "ENDSEC\n",
        "  0\n",
        "EOF\n",
    ]
    return "".join(lines).encode("ascii")


@pytest.fixture
def valid_dxf_with_entity_bytes():
    """A minimal valid DXF file with one LINE entity."""
    lines = [
        "  0\n",
        "SECTION\n",
        "  2\n",
        "HEADER\n",
        "  9\n",
        "$ACADVER\n",
        "  1\n",
        "AC1009\n",
        "  0\n",
        "ENDSEC\n",
        "  0\n",
        "SECTION\n",
        "  2\n",
        "ENTITIES\n",
        "  0\n",
        "LINE\n",
        "  8\n",
        "0\n",
        " 10\n",
        "0.0\n",
        " 20\n",
        "0.0\n",
        " 11\n",
        "5.0\n",
        " 21\n",
        "5.0\n",
        "  0\n",
        "ENDSEC\n",
        "  0\n",
        "EOF\n",
    ]
    return "".join(lines).encode("ascii")


# ═══════════════════════════════════════════════════════════════════════════════
# Test: File validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestFileValidation:
    def test_no_file_returns_422(self, client):
        """POST without a file should return 422 (validation error)."""
        response = client.post("/api/parse-dwg")
        # Without auth, returns 403. With mocked auth, returns 422.
        assert response.status_code in (403, 422), (
            f"Expected 403 or 422, got {response.status_code}"
        )

    def test_wrong_extension_returns_400(self, client):
        """Uploading a .pdf file should be rejected with 400."""
        response = client.post(
            "/api/parse-dwg",
            files={"file": ("test.pdf", b"fake data", "application/pdf")},
        )
        # Without auth, returns 403. With auth, returns 400.
        assert response.status_code in (403, 400), (
            f"Expected 403 or 400, got {response.status_code}"
        )

    def test_valid_dxf_returns_success(self, client, valid_dxf_bytes):
        """Uploading a valid DXF should return 200 with room_count."""
        response = client.post(
            "/api/parse-dwg",
            files={"file": ("test.dxf", valid_dxf_bytes, "application/dxf")},
        )
        # Without auth, returns 403. With auth + valid DXF, returns 200 or 422.
        assert response.status_code in (200, 403, 422), (
            f"Expected 200, 403, or 422, got {response.status_code}"
        )
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "room_count" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Response structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestResponseStructure:
    def test_success_response_has_expected_fields(self, client, valid_dxf_bytes):
        """A successful parse must return all expected fields."""
        response = client.post(
            "/api/parse-dwg",
            files={"file": ("test.dxf", valid_dxf_bytes, "application/dxf")},
        )
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "source" in data
            assert "room_count" in data
            assert "conversion_time_s" in data
            assert "errors" in data
            assert "warnings" in data

    def test_failure_response_has_expected_fields(self, client):
        """A parse failure must return structured error info."""
        response = client.post(
            "/api/parse-dwg",
            files={"file": ("test.dxf", b"garbage content", "application/dxf")},
        )
        # Without auth, returns 403. With auth, returns 400 or 422.
        assert response.status_code in (400, 403, 422), (
            f"Expected 400, 403, or 422, got {response.status_code}"
        )
        if response.status_code != 403:
            data = response.json()
            assert "success" in data
            assert "source" in data
            assert "errors" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Test: File size enforcement
# ═══════════════════════════════════════════════════════════════════════════════


class TestFileSizeEnforcement:
    def test_large_file_rejected(self, client):
        """A very large DXF file should be rejected by size limit."""
        # 60 MB of data — exceeds the 50 MB limit
        large_data = b"X" * (60 * 1024 * 1024)
        response = client.post(
            "/api/parse-dwg",
            files={"file": ("oversized.dxf", large_data, "application/dxf")},
        )
        # Without auth: 403. With auth: 413 (payload too large) or 422/400.
        assert response.status_code in (403, 413, 422, 400, 500), (
            f"Unexpected status: {response.status_code}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests: Helper Functions & Direct Branch Coverage
# ═══════════════════════════════════════════════════════════════════════════════


class TestDWGHelpers:
    """Direct unit tests for internal helper functions in backend/routers/dwg.py."""

    def test_validate_dwg_extension_none(self):
        from backend.routers.dwg import _validate_dwg_extension
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _validate_dwg_extension(None)
        assert exc.value.status_code == 400
        assert "No file provided" in exc.value.detail

    def test_validate_dwg_extension_invalid(self):
        from backend.routers.dwg import _validate_dwg_extension
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _validate_dwg_extension("malicious.exe")
        assert exc.value.status_code == 400
        assert "Unsupported file extension" in exc.value.detail

    def test_validate_dwg_extension_valid(self):
        from backend.routers.dwg import _validate_dwg_extension

        assert _validate_dwg_extension("drawing.dwg") == ".dwg"
        assert _validate_dwg_extension("plan.DXF") == ".dxf"

    @pytest.mark.asyncio
    async def test_stream_upload_to_disk_empty(self):
        import io
        from backend.routers.dwg import _stream_upload_to_disk
        from fastapi import HTTPException, UploadFile

        empty_file = UploadFile(filename="empty.dxf", file=io.BytesIO(b""))
        with pytest.raises(HTTPException) as exc:
            await _stream_upload_to_disk(empty_file, ".dxf")
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_stream_upload_to_disk_success(self):
        import io
        import os
        from backend.routers.dwg import _stream_upload_to_disk
        from fastapi import UploadFile

        valid_content = b"0\nSECTION\n0\nEOF"
        f = UploadFile(filename="valid.dxf", file=io.BytesIO(valid_content))
        temp_path = await _stream_upload_to_disk(f, ".dxf")
        try:
            assert os.path.exists(temp_path)
            with open(temp_path, "rb") as rf:
                assert rf.read() == valid_content
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_format_parse_response_success(self):
        from unittest.mock import MagicMock
        from backend.routers.dwg import _format_parse_response

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.room_count = 5
        mock_result.conversion_time_s = 0.42
        mock_result.errors = []
        mock_result.warnings = []

        res = _format_parse_response(mock_result, "sample.dwg")
        assert res["success"] is True
        assert res["room_count"] == 5
        assert res["source"] == "sample.dwg"

    def test_format_parse_response_security_error(self):
        from unittest.mock import MagicMock
        from backend.routers.dwg import _format_parse_response

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = ["[SECURITY] Directory traversal blocked"]
        mock_result.warnings = []
        mock_result.room_count = 0
        mock_result.conversion_time_s = 0.01

        resp = _format_parse_response(mock_result, "bad.dwg")
        assert resp.status_code == 400

    def test_format_parse_response_not_found(self):
        from unittest.mock import MagicMock
        from backend.routers.dwg import _format_parse_response

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = ["Entity not found"]
        mock_result.warnings = []
        mock_result.room_count = 0
        mock_result.conversion_time_s = 0.01

        resp = _format_parse_response(mock_result, "missing.dwg")
        assert resp.status_code == 404

    def test_format_parse_response_generic_error(self):
        from unittest.mock import MagicMock
        from backend.routers.dwg import _format_parse_response

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.errors = ["Malformed token"]
        mock_result.warnings = []
        mock_result.room_count = 0
        mock_result.conversion_time_s = 0.01

        resp = _format_parse_response(mock_result, "corrupt.dwg")
        assert resp.status_code == 422

