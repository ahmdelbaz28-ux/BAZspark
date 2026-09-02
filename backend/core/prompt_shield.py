"""backend/core/prompt_shield.py — Prompt Injection Shield & File Content Isolation.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 (S4 Deliverable):
- File contents NEVER enter LLM prompt strings: strictly identifier references only (`file_id` + server-side verified summary).
- Adversarial defense against injection vectors: instruction overrides, mutation hijacking, exfiltration links.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Comprehensive permanent adversarial injection patterns suite (Phase 13 hardening)
_INJECTION_PATTERNS = [
    # 1. Instruction Overrides & Reset Attempts
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|rules|guidelines)", re.IGNORECASE),
    re.compile(r"system\s+override\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    # 2. Roleplay Jailbreaks & Unrestricted Persona Modes
    re.compile(r"\b(?:DAN\s+mode|developer\s+mode\s+enabled|jailbreak\s+mode|unrestricted\s+mode|do\s+anything\s+now)\b", re.IGNORECASE),
    # 3. LLM Special Delimiters & Framing Tokens
    re.compile(r"<\s*(?:system|assistant|admin|user|function|tool_call|tool_response)\s*>", re.IGNORECASE),
    re.compile(r"<\s*/\s*(?:system|assistant|admin|user|function|tool_call|tool_response)\s*>", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|<s>|</s>", re.IGNORECASE),
    # 4. System Prompt Extraction & Secret Harvesting
    re.compile(r"(?:repeat|print|output|display|show|reveal|leak|dump)\s+(?:all\s+)?(?:the\s+)?(?:words\s+above|system\s+prompt|initial\s+prompt|system\s+instructions|developer\s+message|admin\s+keys|raw\s+admin\s+keys|secret\s+keys)", re.IGNORECASE),
    # 5. External Exfiltration Links & Webhook Calls
    re.compile(r"(?:https?://[^\s<>\"']+|ftp://[^\s<>\"']+)", re.IGNORECASE),
    re.compile(r"!\[.*?\]\(https?://[^\)]+\)", re.IGNORECASE),
    # 6. Database / Mutation SQL Hijacking
    re.compile(r"(?:DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|UNION\s+SELECT|EXEC\s*\()", re.IGNORECASE),
    # 7. Security Policy, Guardrail & RBAC Bypasses
    re.compile(r"bypass\s+(?:security|policy|guardrails?|auth|rbac|filters?)", re.IGNORECASE),
]


class PromptInjectionShield:
    """Isolates file content from prompt assembly and sanitizes user input against prompt injection."""

    @staticmethod
    def sanitize_user_prompt(prompt: str) -> tuple[str, bool, list[str]]:
        """Sanitize prompt text, stripping injection vectors and returning (clean_prompt, was_sanitized, detected_patterns)."""
        clean = prompt
        detected: list[str] = []
        was_sanitized = False

        for pat in _INJECTION_PATTERNS:
            matches = pat.findall(clean)
            if matches:
                detected.extend([str(m) for m in matches])
                clean = pat.sub("[REDACTED_INJECTION_ATTEMPT]", clean)
                was_sanitized = True

        if was_sanitized:
            logger.warning(
                "PromptInjectionShield sanitized input: detected %d injection patterns: %s",
                len(detected),
                detected[:3],
            )

        return clean.strip(), was_sanitized, detected

    @staticmethod
    def format_safe_file_reference(
        file_id: str,
        server_verified_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Produce a server-side verified file reference with ZERO raw file content exposure."""
        clean_file_id = str(file_id).strip()
        summary = dict(server_verified_summary or {})

        # Extract only verified scalar metadata fields; discard any raw text or binary payload
        safe_ref = {
            "file_id": clean_file_id,
            "filename": str(summary.get("sanitized_filename", summary.get("filename", "drawing.dxf"))),
            "format": str(summary.get("detected_format", summary.get("format", "dxf"))),
            "room_count": int(summary.get("estimated_rooms", summary.get("room_count", 0))),
            "device_count": int(summary.get("estimated_devices", summary.get("device_count", 0))),
            "layer_count": int(summary.get("estimated_layers", summary.get("layer_count", 0))),
        }
        return safe_ref
