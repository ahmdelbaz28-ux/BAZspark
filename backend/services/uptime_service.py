"""
backend/services/uptime_service.py — UptimeRobot Keep-Awake and Monitoring Integration.
========================================================================================

Handles:
1. Periodic heartbeat pings to UptimeRobot push/heartbeat monitor.
2. Querying UptimeRobot API to fetch real-time monitor status and statistics.
3. Keep-awake behavior to prevent Hugging Face Spaces / server sleep.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Keys and Configuration ───────────────────────────────────────────────────
# SECURITY: Keys MUST be set via environment variables. Never hardcode them.
# set UPTIMEROBOT_USER_KEY (read-only key recommended) and
# UPTIMEROBOT_MONITOR_KEY (heartbeat monitor key) in your environment.
# Get keys from: https://dashboard.uptimerobot.com/integrations

HEARTBEAT_INTERVAL = int(os.getenv("UPTIMEROBOT_HEARTBEAT_INTERVAL", "300"))  # 5 minutes

if not os.getenv("UPTIMEROBOT_USER_KEY", ""):
    logger.warning(
        "UPTIMEROBOT_USER_KEY is not set. Monitor status API will be disabled. "
        "set it in your environment to enable UptimeRobot monitoring."
    )
if not os.getenv("UPTIMEROBOT_MONITOR_KEY", ""):
    logger.warning(
        "UPTIMEROBOT_MONITOR_KEY is not set. Heartbeat pings will be disabled. "
        "set it in your environment to enable keep-awake heartbeats."
    )

# ── Singleton Pattern ──────────────────────────────────────────────────────────

_instance: UptimeService | None = None
_lock = threading.Lock()


def get_uptime_service() -> UptimeService:
    """Get the UptimeService singleton instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = UptimeService()
    return _instance


class UptimeService:
    """Service to handle keep-awake push heartbeats and fetch UptimeRobot stats."""

    def __init__(self) -> None:
        self._loop_running = False
        self._task: asyncio.Task[None] | None = None
        self._last_ping_status = "never"
        self._last_ping_time: float = 0.0

    def start_heartbeat_loop(self) -> None:
        """Start the periodic heartbeat ping background task."""
        if self._loop_running:
            return

        self._loop_running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("UptimeRobot Heartbeat background task started.")

    async def stop_heartbeat_loop(self) -> None:
        """Stop the background heartbeat task.

        Uses ``asyncio.wait({task})`` instead of ``await task`` so that the
        ``CancelledError`` raised by the *cancelled child task* is NOT
        propagated to the caller. This distinction matters:

        * If the child task is cancelled (our intent here — we called
          ``self._task.cancel()`` above), ``asyncio.wait`` returns it in the
          ``done`` set and does not re-raise. Swallowing is safe and correct
          because the cancellation was initiated by us, not by the event loop
          cancelling the current coroutine.

        * If the *current* coroutine (``stop_heartbeat_loop`` itself) is
          cancelled while awaiting (e.g. a shutdown timeout), ``asyncio.wait``
          raises ``CancelledError`` which correctly propagates up — satisfying
          Sonar S7497 without forcing every caller to catch-and-re-raise in a
          chain.

        The previous implementation awaited the task directly and re-raised
        ``CancelledError``, which forced ``app.py`` to swallow it (S7497
        violation). This refactor removes that violation at the source.
        """
        self._loop_running = False
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            # `asyncio.wait` does NOT re-raise exceptions from the awaited
            # tasks; it returns them in the `done` set. The current coroutine
            # can still be cancelled externally (CancelEvent on shutdown),
            # in which case `asyncio.wait` raises CancelledError — that one
            # MUST propagate (and does, automatically).
            await asyncio.wait({task})
        self._task = None
        logger.info("UptimeRobot Heartbeat background task stopped.")

    async def _heartbeat_loop(self) -> None:
        """Background loop executing the ping requests."""
        # Warmup delay to let the app initialize fully
        await asyncio.sleep(5)

        async with httpx.AsyncClient(timeout=10.0) as client:
            while self._loop_running:
                try:
                    await self._ping_heartbeat(client)
                except Exception as e:
                    logger.warning("UptimeRobot heartbeat loop error: %s", e)

                await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _ping_heartbeat(self, client: httpx.AsyncClient) -> bool:
        """Send a single heartbeat ping to UptimeRobot."""
        # Check env at call time (not import time) so tests can set it dynamically
        monitor_key = os.getenv("UPTIMEROBOT_MONITOR_KEY", "")
        if not monitor_key:
            logger.warning("UptimeRobot Monitor Key is not set. Skipping heartbeat ping.")
            self._last_ping_status = "disabled"
            return False

        # Heartbeat endpoint format: https://heartbeat.uptimerobot.com/MONITOR_KEY
        url = f"https://heartbeat.uptimerobot.com/{monitor_key}"
        try:
            res = await client.get(url)
            if res.status_code == 200:
                self._last_ping_status = "success"
                self._last_ping_time = time.time()
                logger.debug("Successfully sent UptimeRobot heartbeat ping.")
                return True
            else:
                self._last_ping_status = f"failed (HTTP {res.status_code})"
                logger.warning("UptimeRobot heartbeat returned HTTP %s", res.status_code)
                return False
        except httpx.HTTPError as e:
            self._last_ping_status = f"failed ({type(e).__name__})"
            logger.warning("UptimeRobot heartbeat network failure: %s", e)
            return False

    async def fetch_monitor_status(self) -> dict[str, Any]:
        """
        Query the UptimeRobot API using the user key to get monitor statuses.
        """
        # Check env at call time so tests and runtime can set it dynamically
        user_key = os.getenv("UPTIMEROBOT_USER_KEY", "")
        if not user_key:
            return {"success": False, "error": "User API Key is not configured."}

        url = "https://api.uptimerobot.com/v2/getMonitors"
        payload = {
            "api_key": user_key,
            "format": "json",
            "logs": 1
        }
        headers = {
            "content-type": "application/x-www-form-urlencoded"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, data=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("stat") == "ok":
                        return {"success": True, "monitors": data.get("monitors", [])}
                    return {"success": False, "error": data.get("error", {}).get("message", "API Error")}
                return {"success": False, "error": f"HTTP {res.status_code}"}
        except Exception as e:
            logger.exception("Failed to query UptimeRobot API: %s", e)
            return {"success": False, "error": str(e)}

    def get_local_status(self) -> dict[str, Any]:
        """Return the status of the local keep-awake loop."""
        return {
            "loop_running": self._loop_running,
            "last_ping_status": self._last_ping_status,
            "last_ping_time": self._last_ping_time,
            "interval_seconds": HEARTBEAT_INTERVAL,
        }
