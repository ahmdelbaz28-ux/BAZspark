"""
fireai/agents/cua_agent.py — Computer-Use Agent (CUA) driver for V151.

Integrates fireai/vision/cua_loop.py::analyze_screenshot() into a real agent
loop that captures screenshots, analyzes them via OpenAI Vision (or OpenCV
fallback), and emits structured actions.

V151.1 INTEGRATION
------------------
This module closes the gap identified in the V151 review (I1: "CUA loop not
integrated with any agent"). It provides:

  - CUAAgent class with a simple step() API
  - Screenshot capture via mss (cross-platform) with PIL fallback
  - Deterministic action extraction from the VisionAnalysisResult
  - Never-raises contract (matches cua_loop.py safety pattern)
  - Logging of provider used (openai-db / openai-env / opencv / none)

USAGE
-----
    from fireai.agents.cua_agent import CUAAgent
    agent = CUAAgent(prompt="Identify fire alarm devices in this engineering UI")
    result = agent.step()  # captures primary screen, analyzes, returns action
    if result.ok:
        print(result.description)

SAFETY CONTRACT (per agent.md Rule 1 + Rule 4)
----------------------------------------------
- step() NEVER raises. It always returns a CUAAgentResult.
- If screenshot capture fails, returns ok=False with error.
- If analysis fails (all providers), returns ok=False with error.
- The agent does NOT execute actions autonomously — it only SUGGESTS them.
  The caller (UI automation framework) decides whether to execute.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fireai.vision.cua_loop import VisionAnalysisResult, analyze_screenshot

logger = logging.getLogger(__name__)


# ── Result type ──────────────────────────────────────────────────────────────


@dataclass
class CUAAgentResult:
    """
    Result of one CUA step (screenshot + analysis + suggested action).

    `provider` mirrors VisionAnalysisResult.provider:
      - "openai-db"  : OpenAI Vision, key from DB
      - "openai-env" : OpenAI Vision, key from env var
      - "opencv"     : OpenCV offline fallback
      - "none"       : All providers failed
    """

    ok: bool
    provider: str = "none"
    description: str = ""
    suggested_action: Dict[str, Any] = field(default_factory=dict)
    screenshot_captured: bool = False
    analysis: Optional[VisionAnalysisResult] = None
    error: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "screenshot_captured": self.screenshot_captured,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ── Screenshot capture ───────────────────────────────────────────────────────


def _capture_screenshot() -> Optional[bytes]:
    """
    Capture the primary screen as PNG bytes.

    Tries mss (fast, cross-platform) first, falls back to PIL ImageGrab.
    Returns None if both fail (e.g. headless server with no display).

    NEVER raises — returns None on any failure.
    """
    # Try mss first (faster, multi-monitor aware)
    try:
        import mss
        import mss.tools
        from PIL import Image
        import io

        with mss.mss() as sct:
            # Primary monitor (index 0 is "all monitors combined"; 1 is primary)
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except ImportError:
        pass  # mss not installed — try PIL
    except Exception as e:
        logger.debug("mss screenshot failed: %s", type(e).__name__)

    # Fallback: PIL ImageGrab (works on Windows + macOS, limited on Linux without X)
    try:
        from PIL import ImageGrab
        import io

        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        logger.debug("PIL not installed — cannot capture screenshot")
        return None
    except Exception as e:
        logger.debug("PIL screenshot failed: %s", type(e).__name__)
        return None


# ── Action extraction ────────────────────────────────────────────────────────


def _extract_suggested_action(analysis: VisionAnalysisResult) -> Dict[str, Any]:
    """
    Extract a structured suggested action from the VisionAnalysisResult.

    For OpenAI providers: parses the text description for UI element references.
    For OpenCV: returns the detected rectangles as clickable regions.
    For none: returns an empty dict.

    This is a SUGGESTION only — the caller decides whether to execute.
    """
    if not analysis.ok:
        return {}

    if analysis.provider == "opencv":
        # OpenCV gives us concrete rectangles — suggest clicking the largest
        if analysis.elements:
            largest = max(analysis.elements, key=lambda r: r.get("w", 0) * r.get("h", 0))
            return {
                "type": "click",
                "target": largest,
                "reason": "Largest detected UI element (OpenCV contour)",
            }
        return {"type": "none", "reason": "No UI elements detected by OpenCV"}

    # OpenAI providers — the description is free text; we surface it as-is
    return {
        "type": "describe",
        "description": analysis.description,
        "elements": analysis.elements,
    }


# ── CUAAgent ─────────────────────────────────────────────────────────────────


class CUAAgent:
    """
    Computer-Use Agent that captures screenshots and analyzes them via
    OpenAI Vision (preferred) or OpenCV (fallback).

    The agent is stateless between steps — each step() call captures a fresh
    screenshot and analyzes it independently. This matches the deterministic
    behavior required by agent.md Rule 5.

    NEVER raises. step() always returns a CUAAgentResult.
    """

    def __init__(self, prompt: str = "Analyze this screenshot and describe what you see.") -> None:
        self.prompt = prompt
        self._step_count = 0

    def step(self, screenshot_bytes: Optional[bytes] = None) -> CUAAgentResult:
        """
        Execute one CUA step: capture (or use provided) screenshot → analyze → suggest.

        Args:
            screenshot_bytes: Optional pre-captured screenshot. If None, the
                              agent captures the primary screen.

        Returns:
            CUAAgentResult — never raises.
        """
        self._step_count += 1
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Capture screenshot (or use provided one)
        if screenshot_bytes is None:
            screenshot_bytes = _capture_screenshot()

        if not screenshot_bytes:
            return CUAAgentResult(
                ok=False,
                provider="none",
                screenshot_captured=False,
                error="Failed to capture screenshot (no display or capture library unavailable)",
                timestamp=timestamp,
            )

        # 2. Analyze via cua_loop (DB → env → OpenCV fallback)
        try:
            analysis = analyze_screenshot(screenshot_bytes, prompt=self.prompt)
        except Exception as e:
            # cua_loop should never raise, but defend-in-depth
            logger.error("CUA loop raised unexpectedly: %s", type(e).__name__)
            return CUAAgentResult(
                ok=False,
                provider="none",
                screenshot_captured=True,
                error=f"Analysis failed: {type(e).__name__}",
                timestamp=timestamp,
            )

        # 3. Extract suggested action
        suggested = _extract_suggested_action(analysis)

        # 4. Log provider used (for observability — no plaintext keys)
        logger.info(
            "CUA step %d: provider=%s ok=%s elements=%d",
            self._step_count,
            analysis.provider,
            analysis.ok,
            len(analysis.elements),
        )

        return CUAAgentResult(
            ok=analysis.ok,
            provider=analysis.provider,
            description=analysis.description,
            suggested_action=suggested,
            screenshot_captured=True,
            analysis=analysis,
            error=analysis.error,
            timestamp=timestamp,
        )

    def run(self, max_steps: int = 10, interval_seconds: float = 1.0) -> list[CUAAgentResult]:
        """
        Run multiple steps with a sleep interval between them.

        Stops early if a step fails to capture a screenshot (likely headless).
        Returns the list of all step results.

        NEVER raises.
        """
        results: list[CUAAgentResult] = []
        for i in range(max_steps):
            result = self.step()
            results.append(result)
            if not result.screenshot_captured:
                logger.warning("Stopping CUA run: screenshot capture failed at step %d", i + 1)
                break
            time.sleep(interval_seconds)
        return results


__all__ = ["CUAAgent", "CUAAgentResult", "_capture_screenshot"]
