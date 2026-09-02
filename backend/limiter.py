"""
backend/limiter.py — Rate Limiter Configuration.
===============================================

Centralized rate limiter configuration to avoid circular imports.
Import this module directly instead of importing from backend.app.

Usage:
    from backend.limiter import limiter, get_remote_address

Akamai integration (added 2026-07-09):
    When the request transits Akamai Edge, the canonical client IP is the
    True-Client-IP header (set by Akamai AFTER authenticating the request).
    The legacy X-Forwarded-For chain is untrusted because:
      - It can be spoofed by the client (just set the header)
      - It contains multiple hops (comma-separated) that complicate parsing
      - Akamai overwrites it with True-Client-IP at the edge

    The key_func below reads True-Client-IP first, falling back to
    X-Forwarded-For (first hop) and finally request.client.host. This
    makes rate limiting accurate behind Akamai while still working in
    local dev (where True-Client-IP is absent).

    backend/akamai_middleware.py also overwrites X-Forwarded-For with
    True-Client-IP at the ASGI scope level, so downstream code that reads
    X-Forwarded-For directly also gets the correct IP.
"""

from __future__ import annotations

import logging
import os

from slowapi import Limiter
from starlette.requests import Request

logger = logging.getLogger(__name__)


_PROXY_ENABLED_VALUES = ("true", "1", "yes", "on")


def _trusted_proxy_list() -> list[str]:
    """Parse the comma-separated TRUSTED_PROXIES env var."""
    return [p.strip() for p in os.environ.get("TRUSTED_PROXIES", "").split(",") if p.strip()]


def _peer_is_trusted_proxy(request: Request) -> bool:
    """True when the TCP peer (request.client.host) is a configured trusted proxy."""
    if not request.client or not request.client.host:
        return False
    return request.client.host in _trusted_proxy_list()


def _cdn_enabled() -> bool:
    """True when Cloudflare or Akamai integration is enabled via env flags."""
    for var in ("CF_ENABLED", "AKAMAI_ENABLED"):
        if os.environ.get(var, "false").strip().lower() in _PROXY_ENABLED_VALUES:
            return True
    return False


def get_remote_address(request: Request) -> str:
    """Get the client IP address for rate limiting.

    SECURITY (C-01): Client-supplied proxy headers are only trusted when we
    can establish that the request actually transited that proxy:

      1. ``CF-Connecting-IP`` (Cloudflare) is trusted only when Cloudflare
         integration is enabled (``CF_ENABLED=true``) or the TCP peer is a
         configured trusted proxy.
      2. ``True-Client-IP`` (Akamai) is trusted only when Akamai integration
         is enabled (``AKAMAI_ENABLED=true``) or the TCP peer is a configured
         trusted proxy.
      3. ``X-Forwarded-For`` is spoofable, so it is only honored when the TCP
         peer is a configured trusted proxy, and we take the LAST entry (the
         value the proxy appended from ``$remote_addr``, not a client-supplied
         hop).
      4. ``request.client.host`` (the TCP peer) is used as the safe default —
         including local dev where no proxy headers are present.

    Returns "0.0.0.0" if no IP can be determined (should never happen
    in practice, but prevents a None key_func crash if it does).
    """
    # SECURITY (C-01 & Phase 13 Hardening): Proxy headers are trusted ONLY
    # when the direct TCP peer is confirmed to be a configured trusted proxy.
    if _peer_is_trusted_proxy(request):
        # 1. Cloudflare CF-Connecting-IP
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            ip = cf_ip.strip().split(",")[0].strip()
            if ip:
                return ip

        # 2. Akamai True-Client-IP
        true_client_ip = request.headers.get("True-Client-IP")
        if true_client_ip:
            ip = true_client_ip.strip().split(",")[0].strip()
            if ip:
                return ip

        # 3. X-Forwarded-For — last hop from trusted proxy
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            ip = xff.split(",")[-1].strip()
            if ip:
                return ip

    # 4. Direct connection (untrusted peer, local dev, or no proxy)
    if request.client and request.client.host:
        return request.client.host

    # Fallback — prevents None key_func crash
    return "0.0.0.0"


# Without storage_uri, slowapi defaults to in-memory storage which is
# per-worker. With N uvicorn workers, the effective rate limit becomes N×
# the configured limit (each worker has its own counter).
# When REDIS_URL is set, all workers share a single counter via Redis.
_redis_url = os.getenv("REDIS_URL")
if _redis_url:
    # Use Redis for distributed rate limiting (production)
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=_redis_url,
        strategy="fixed-window",
    )
    logger.info("Rate limiter using Redis storage at %s", _redis_url)
else:
    # In-memory storage (development only — per-worker, not shared)
    limiter = Limiter(key_func=get_remote_address)
    logger.warning(
        "REDIS_URL not set — rate limiter using in-memory storage. "
        "Rate limits are per-worker and will be N×configured with N workers. "
        "Set REDIS_URL for production."
    )

__all__ = ["get_remote_address", "limiter"]
