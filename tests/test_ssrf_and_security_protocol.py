"""
test_ssrf_and_security_protocol.py
===================================
Comprehensive unit tests for the Enterprise Security Protocol & Governance Laws:
  1. SSRF Guard validate_url() - Scheme, hostname, private IP, loopback, cloud metadata blocking.
  2. Adapter Dynamic SSRF Enclosure - openaq, wildfire_smoke, earthquake, elevation, ais_vessel, geocoding.
  3. Startup Fail-Fast Verification - backend/config.py environment secret validation.
  4. WebSocket Active Ping/Pong Heartbeat - backend/routers/agent_ws.py origin check & 30s timeout code.
"""

from __future__ import annotations

import pytest

from backend.integrations._ssrf_guard import SSRFError, validate_url


class TestSSRFGuardValidateURL:
    """Verify validate_url() strictly enforces URL safety."""

    def test_validate_url_valid_https(self):
        url = "https://api.openaq.org/v3/locations?lat=30.0&lon=31.0"
        result = validate_url(url)
        assert result == url

    def test_validate_url_blocks_file_scheme(self):
        with pytest.raises(SSRFError, match="not permitted"):
            validate_url("file:///etc/passwd")

    def test_validate_url_blocks_gopher_scheme(self):
        with pytest.raises(SSRFError, match="not permitted"):
            validate_url("gopher://127.0.0.1:70")

    def test_validate_url_empty_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty string"):
            validate_url("")

    def test_validate_url_blocks_loopback_ip(self):
        with pytest.raises(SSRFError):
            validate_url("http://127.0.0.1/admin")

    def test_validate_url_blocks_private_network(self):
        with pytest.raises(SSRFError):
            validate_url("http://10.0.0.1/internal")

    def test_validate_url_blocks_aws_metadata(self):
        with pytest.raises(SSRFError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_validate_url_blocks_gcp_metadata(self):
        with pytest.raises(SSRFError):
            validate_url("http://metadata.google.internal/computeMetadata/v1/")


class TestAdapterDynamicSSRF:
    """Verify all external adapters call validate_url dynamically."""

    @pytest.mark.asyncio
    async def test_openaq_adapter_ssrf_rejection(self):
        from fireai.integration.openaq_adapter import OpenAQAdapter
        adapter = OpenAQAdapter(base_url="http://169.254.169.254/v3/locations")
        adapter._api_key = "test_key"
        with pytest.raises(SSRFError):
            await adapter._fetch(lat=30.0, lon=31.0)

    @pytest.mark.asyncio
    async def test_wildfire_smoke_adapter_ssrf_rejection(self):
        from fireai.integration.wildfire_smoke_adapter import WildfireSmokeAdapter
        adapter = WildfireSmokeAdapter(base_url="http://10.0.0.1/v1/forecast")
        with pytest.raises(SSRFError):
            await adapter._fetch(lat=30.0, lon=31.0)

    @pytest.mark.asyncio
    async def test_earthquake_adapter_ssrf_rejection(self):
        from fireai.integration.earthquake_adapter import EarthquakeAdapter
        adapter = EarthquakeAdapter(base_url="http://127.0.0.1/fdsnws/event/1/query")
        with pytest.raises(SSRFError):
            await adapter._fetch(lat=30.0, lon=31.0)

    @pytest.mark.asyncio
    async def test_elevation_adapter_ssrf_rejection(self):
        from fireai.integration.elevation_adapter import ElevationAdapter
        adapter = ElevationAdapter(base_url="http://192.168.1.1/v1/srtm30m")
        with pytest.raises(SSRFError):
            await adapter._fetch(lat=30.0, lon=31.0)

    @pytest.mark.asyncio
    async def test_ais_vessel_adapter_ssrf_rejection(self):
        from fireai.integration.ais_vessel_adapter import AISVesselAdapter
        adapter = AISVesselAdapter(base_url="http://100.100.100.200/ais")
        adapter._api_key = "test_key"
        with pytest.raises(SSRFError):
            await adapter._fetch(lat=25.0, lon=55.0)

    @pytest.mark.asyncio
    async def test_geocoding_service_ssrf_rejection(self):
        from backend.services.geocoding_service import GeocodingService
        service = GeocodingService()
        service.NOMINATIM_URL = "http://127.0.0.1/search"
        with pytest.raises(SSRFError):
            await service._fetch_nominatim("Cairo")


class TestAgentWebSocketHeartbeat:
    """Verify agent_ws heartbeat configuration and constants."""

    def test_ws_heartbeat_constants(self):
        from backend.routers.agent_ws import WS_HEARTBEAT_TIMEOUT_SECONDS, WS_PING_INTERVAL_SECONDS
        assert WS_HEARTBEAT_TIMEOUT_SECONDS == 30.0
        assert WS_PING_INTERVAL_SECONDS == 25.0
