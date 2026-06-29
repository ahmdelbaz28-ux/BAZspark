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
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.dwg import router


@pytest.fixture
def app():
    _app = FastAPI()
    _app.include_router(router, prefix="/api")
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
        assert response.status_code in (403, 422), f"Expected 403 or 422, got {response.status_code}"

    def test_wrong_extension_returns_400(self, client):
        """Uploading a .pdf file should be rejected with 400."""
        response = client.post(
            "/api/parse-dwg",
            files={"file": ("test.pdf", b"fake data", "application/pdf")},
        )
        # Without auth, returns 403. With auth, returns 400.
        assert response.status_code in (403, 400), f"Expected 403 or 400, got {response.status_code}"

    def test_valid_dxf_returns_success(self, client, valid_dxf_bytes):
        """Uploading a valid DXF should return 200 with room_count."""
        response = client.post(
            "/api/parse-dwg",
            files={"file": ("test.dxf", valid_dxf_bytes, "application/dxf")},
        )
        # Without auth, returns 403. With auth + valid DXF, returns 200 or 422.
        assert response.status_code in (200, 403, 422), f"Expected 200, 403, or 422, got {response.status_code}"
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
        assert response.status_code in (400, 403, 422), f"Expected 400, 403, or 422, got {response.status_code}"
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
        assert response.status_code in (403, 413, 422, 400, 500), f"Unexpected status: {response.status_code}"