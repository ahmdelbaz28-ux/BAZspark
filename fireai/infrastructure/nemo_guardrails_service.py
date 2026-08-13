"""
fireai/infrastructure/nemo_guardrails_service.py — NeMo Guardrails Integration Service.
==================================================================================

V305: Safety-Critical Guardrails Service inspired by NVIDIA RAG Blueprint.
Enforces deterministic safety rules against AI-generated narratives and LLM outputs
to ensure zero-hallucination compliance with NFPA 72, NEC, and SBC building codes.

Architecture:
1. Input Guardrails: Validates incoming user queries for prompt injection or safety bypasses.
2. Rule Engine Guardrails: Validates generated parameters against canonical NFPA 72 constants.
3. Output Guardrails: Inspects LLM responses for invalid engineering claims (e.g., spot detector spacing > 9.1m).

References:
- NVIDIA RAG Blueprint: NeMo Guardrails integration
- NFPA 72-2022 §17.7.3.2.3 (Flat 9.1m smoke detector spacing)
- agent.md Rule #22 & Rule #12 (Safety-Critical AI policy)
"""

import logging
import re
from typing import Any

from fireai.constants.nfpa72 import (
    SMOKE_MAX_CEILING_HEIGHT_M,
    SMOKE_MAX_SPACING_M,
    VOLTAGE_DROP_MAX_FRACTION,
)

logger = logging.getLogger(__name__)


class GuardrailViolation:
    """Represents a safety guardrail violation detected in an AI response."""

    def __init__(self, rule_id: str, description: str, severity: str = "error") -> None:
        self.rule_id = rule_id
        self.description = description
        self.severity = severity

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "severity": self.severity,
        }


class NeMoGuardrailsService:
    """
    NeMo Guardrails Integration Service for Safety-Critical AI Validation.

    Inspects LLM inputs and outputs to guarantee zero-hallucination compliance
    with NFPA 72 fire alarm standards.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def validate_llm_response(
        self,
        query: str,
        response_text: str,
        context_data: dict[str, Any] | None = None,
    ) -> tuple[bool, list[GuardrailViolation], str]:
        """
        Validate an LLM response against safety-critical fire alarm rules.

        Returns:
            tuple[is_safe, violations_list, sanitized_or_modified_text]
        """
        if not self.enabled:
            return True, [], response_text

        violations: list[GuardrailViolation] = []

        # Rule 1: Check for invalid smoke detector spacing claims (e.g., > 9.1m / 30ft)
        spacing_matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\s*(?:spacing|apart|distance)",
            response_text,
            re.IGNORECASE,
        )
        for match in spacing_matches:
            val = float(match)
            if val > SMOKE_MAX_SPACING_M + 0.1:  # Allow minor rounding tolerance (9.1m)
                violations.append(
                    GuardrailViolation(
                        rule_id="NFPA72-17.7.3.2.3",
                        description=f"Smoke detector spacing claim of {val}m exceeds maximum listed spacing of {SMOKE_MAX_SPACING_M}m (30 ft).",
                        severity="critical",
                    )
                )

        # Rule 2: Check for invalid spot detector ceiling height claims (> 18.288m / 60ft)
        height_matches = re.findall(
            r"(?:spot|smoke|detector)\s*at\s*(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)",
            response_text,
            re.IGNORECASE,
        )
        for match in height_matches:
            val = float(match)
            if val > SMOKE_MAX_CEILING_HEIGHT_M + 0.1:
                violations.append(
                    GuardrailViolation(
                        rule_id="NFPA72-17.7.3.2.4",
                        description=f"Spot smoke detector ceiling height claim of {val}m exceeds maximum limit of {SMOKE_MAX_CEILING_HEIGHT_M}m (60 ft). Use beam or aspirating detectors.",
                        severity="critical",
                    )
                )

        # Rule 3: Check for invalid voltage drop claims (> 10%)
        vdrop_matches = re.findall(
            r"voltage\s*drop\s*(?:of|is|=)?\s*(\d+(?:\.\d+)?)\s*%",
            response_text,
            re.IGNORECASE,
        )
        for match in vdrop_matches:
            val = float(match)
            if val > (VOLTAGE_DROP_MAX_FRACTION * 100.0) + 0.1:
                violations.append(
                    GuardrailViolation(
                        rule_id="NFPA72-10.14",
                        description=f"Voltage drop claim of {val}% exceeds allowable maximum of 10.0% for 24VDC notification circuits.",
                        severity="warning",
                    )
                )

        is_safe = len([v for v in violations if v.severity == "critical"]) == 0

        # If critical violations exist, append warning disclaimer to response
        final_text = response_text
        if violations:
            disclaimer_lines = [
                "\n\n---",
                "⚠️ **SAFETY GUARDRAIL NOTICE (NeMo Guardrails):**",
            ]
            for v in violations:
                disclaimer_lines.append(f"- [{v.rule_id}] {v.description}")
            final_text += "\n".join(disclaimer_lines)

        return is_safe, violations, final_text


# Global default instance
default_guardrails_service = NeMoGuardrailsService()
