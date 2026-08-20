"""backend/tests/test_analyze_endpoints.py — Unit tests for analyze.py endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.routers.analyze import (
    BatteryRequest,
    RoomAnalyzeRequest,
    VoltageRequest,
    _physics_guard_detail,
    analyze_battery,
    analyze_project_room,
    analyze_voltage,
)
from fireai.core.qomn_kernel import PhysicsGuardError


def _make_request(path: str = "/api/analyze") -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
    })


class TestAnalyzeEndpoints:
    """Test suite for analyze router functions."""

    def test_physics_guard_detail_helper(self):
        err = PhysicsGuardError("field_x", -1.0, "value is out of bounds", "NFPA 72 §1.1")
        detail = _physics_guard_detail(err)
        assert detail["error_type"] == "physics_guard_violation"
        assert detail["field"] == "field_x"
        assert detail["reason"] == "value is out of bounds"
        assert detail["code_ref"] == "NFPA 72 §1.1"

        fallback = _physics_guard_detail(RuntimeError("generic"))
        assert fallback["error_type"] == "physics_guard_violation"
        assert "hint" in fallback

    @pytest.mark.asyncio
    async def test_analyze_battery_success(self):
        req = _make_request("/api/analyze/battery")
        req_data = BatteryRequest(
            standby_load_a=0.5,
            alarm_load_a=2.0,
            standby_hours=24.0,
            alarm_minutes=5.0,
        )
        res = await analyze_battery(req, req_data)
        assert res["success"] is True
        assert "data" in res
        assert "nfpa_section" in res

    @pytest.mark.asyncio
    async def test_analyze_battery_physics_guard_error(self):
        req = _make_request("/api/analyze/battery")
        req_data = BatteryRequest(
            standby_load_a=0.5,
            alarm_load_a=2.0,
        )
        with patch("backend.routers.analyze.QOMNKernel.battery_capacity", side_effect=PhysicsGuardError("load", -5.0, "too high", "SEC-1")):
            with pytest.raises(HTTPException) as exc_info:
                await analyze_battery(req, req_data)
            assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_voltage_success(self):
        req = _make_request("/api/analyze/voltage")
        req_data = VoltageRequest(
            current_a=1.5,
            length_m=50.0,
            awg_gauge="14",
            supply_voltage_v=24.0,
        )
        res = await analyze_voltage(req, req_data)
        assert res["success"] is True
        assert "data" in res
        assert "nfpa_section" in res

    @pytest.mark.asyncio
    async def test_analyze_voltage_physics_guard_error(self):
        req = _make_request("/api/analyze/voltage")
        req_data = VoltageRequest(
            current_a=1.5,
            length_m=50.0,
            awg_gauge="14",
            supply_voltage_v=24.0,
        )
        with patch("backend.routers.analyze.QOMNKernel.voltage_drop", side_effect=PhysicsGuardError("awg", "99", "invalid gauge", "NEC")):
            with pytest.raises(HTTPException) as exc_info:
                await analyze_voltage(req, req_data)
            assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_project_room_success(self):
        req = _make_request("/api/projects/proj-1/analyze/room")
        req_data = RoomAnalyzeRequest(
            room_id="proj-1-room-1",
            room_polygon=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
            ceiling_height_m=3.0,
            detector_type="smoke",
        )
        res = await analyze_project_room(req, "proj-1", req_data)
        assert "success" in res
        assert res["data"]["project_id"] == "proj-1"

    @pytest.mark.asyncio
    async def test_analyze_project_room_physics_guard_error(self):
        req = _make_request("/api/projects/proj-1/analyze/room")
        req_data = RoomAnalyzeRequest(
            room_id="proj-1-room-1",
            room_polygon=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
            ceiling_height_m=3.0,
            detector_type="smoke",
        )
        with patch("backend.routers.analyze.analyze_room", side_effect=PhysicsGuardError("poly", [], "degenerate", "NFPA")):
            with pytest.raises(HTTPException) as exc_info:
                await analyze_project_room(req, "proj-1", req_data)
            assert exc_info.value.status_code == 422
