"""backend/core/disambiguation.py — Clarification & Disambiguation Loop for Autonomous Workflows.

Mandated by BAZSPARK_PLAN_V2_2 §5 Phase 5 (S3 Deliverable):
- Missing or ambiguous parameter -> Explicit clarifying question; GUESSING IS STRICTLY FORBIDDEN.
- Fallthrough never remains silent: explicit explanation of what was not understood and what is needed.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DisambiguationRequest:
    """Explicit clarification request when an intent is underspecified or ambiguous."""

    is_clarification_required: bool
    clarification_type: str  # "missing_parameter" | "ambiguous_parameter" | "intent_unclear" | "none"
    question: str
    missing_fields: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    context_summary: str = ""
    original_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DisambiguationRequiredError(Exception):
    """Raised when an intent requires explicit user clarification."""

    def __init__(self, disambiguation: DisambiguationRequest) -> None:
        super().__init__(disambiguation.question)
        self.disambiguation = disambiguation


class DisambiguationEngine:
    """Inspects natural language intents and structured specs for missing or ambiguous parameters."""

    @staticmethod
    def evaluate_intent(
        prompt: str,
        spec: dict[str, Any] | None = None,
        available_capabilities: list[str] | None = None,
    ) -> DisambiguationRequest:
        """Analyze intent. Returns DisambiguationRequest with is_clarification_required=True if missing/ambiguous."""
        p_clean = prompt.strip()
        p_lower = p_clean.lower()
        spec_dict = dict(spec or {})

        # 1. Detect Export Ambiguity: User asks to export/download but gives no format
        is_export_intent = any(
            w in p_lower for w in ("export", "download", "deliverable", "تصدير", "تحميل")
        )
        if is_export_intent and not any(
            w in p_lower
            for w in ("layout", "detector", "voltage", "battery", "hydraulic", "place", "calculate")
        ):
            has_format = bool(spec_dict.get("target_format") or spec_dict.get("format"))
            fmt_keywords = ("dxf", "ifc", "revit", "xlsx", "excel", "csv", "pdf", "json")
            if not has_format and not any(f in p_lower for f in fmt_keywords):
                is_arabic = any("\u0600" <= c <= "\u06FF" for c in prompt)
                q = (
                    "يرجى تحديد صيغة التصدير المطلوبة للمشروع."
                    if is_arabic
                    else "Please specify the target export format for the project deliverable."
                )
                return DisambiguationRequest(
                    is_clarification_required=True,
                    clarification_type="ambiguous_parameter",
                    question=q,
                    missing_fields=["target_format"],
                    options=["DXF", "IFC", "PDF", "XLSX", "JSON"],
                    context_summary="Export intent detected without specified target format.",
                    original_prompt=prompt,
                )

        # 2. Detect Spatial Layout Missing Parameters: User asks to place detectors/layout room but provides NO dimensions
        is_spatial_intent = any(
            w in p_lower
            for w in (
                "layout",
                "place",
                "detector",
                "detectors",
                "spacing",
                "توزيع",
                "كواشف",
                "حساسات",
            )
        )
        if is_spatial_intent and not any(
            w in p_lower for w in ("voltage", "battery", "pipe", "import", "export")
        ):
            has_spec_dims = bool(
                spec_dict.get("width_m")
                or spec_dict.get("width")
                or spec_dict.get("room_bounds")
                or spec_dict.get("entity_id")
                or spec_dict.get("entity_ids")
                or spec_dict.get("room_id")
                or spec_dict.get("zone")
            )
            has_prompt_dims = bool(
                re.search(r"\d+(?:\.\d+)?\s*(?:m|meter|x|by|×|\*)\s*\d+", p_lower)
            )
            has_named_zone = bool(
                re.search(r"\b(?:zone|room|area|sector|hall|building|غرفة|منطقة)\s+[\w-]+\b", p_lower)
            )
            if not has_spec_dims and not has_prompt_dims and not has_named_zone:
                is_arabic = any("\u0600" <= c <= "\u06FF" for c in prompt)
                q = (
                    "يرجى توضيح أبعاد الغرفة (الطول والعرض وارتفاع السقف) لحساب توزيع الكواشف وفق معيار NFPA 72."
                    if is_arabic
                    else "Please provide room dimensions (length, width, and ceiling height) to calculate compliant detector layout per NFPA 72."
                )
                return DisambiguationRequest(
                    is_clarification_required=True,
                    clarification_type="missing_parameter",
                    question=q,
                    missing_fields=["width_m", "length_m", "ceiling_height_m"],
                    options=[],
                    context_summary="Spatial detector layout intent detected without room dimensions.",
                    original_prompt=prompt,
                )

        # 3. Detect Electrical Circuit Missing Parameters: User asks for voltage drop calculation but provides no current/load or length
        is_electrical_intent = any(
            w in p_lower
            for w in (
                "voltage drop",
                "nac drop",
                "wire drop",
                "هبوط الجهد",
                "انخفاض الجهد",
            )
        )
        if is_electrical_intent and not any(
            w in p_lower for w in ("layout", "detector", "battery", "import", "export")
        ):
            has_spec_el = bool(
                spec_dict.get("current_a") or spec_dict.get("currentA") or spec_dict.get("circuit")
            )
            has_prompt_curr = bool(re.search(r"\d+(?:\.\d+)?\s*(?:a|amp|amperes|امبير)", p_lower))
            if not has_spec_el and not has_prompt_curr:
                is_arabic = any("\u0600" <= c <= "\u06FF" for c in prompt)
                q = (
                    "يرجى تحديد تيار الحمل (الأمبير) وطول الدائرة لحساب هبوط الجهد."
                    if is_arabic
                    else "Please specify circuit load current (Amperes) and run length to calculate voltage drop."
                )
                return DisambiguationRequest(
                    is_clarification_required=True,
                    clarification_type="missing_parameter",
                    question=q,
                    missing_fields=["current_a", "one_way_length_m"],
                    options=[],
                    context_summary="Electrical voltage drop calculation intent detected without load parameters.",
                    original_prompt=prompt,
                )

        # 4. Fallthrough Diagnostic (When intent is completely uninterpretable)
        if not p_clean:
            return DisambiguationRequest(
                is_clarification_required=True,
                clarification_type="intent_unclear",
                question="Please specify your engineering design or calculation request.",
                missing_fields=["intent"],
                options=[
                    "Layout smoke/heat detectors in room",
                    "Calculate NAC voltage drop",
                    "Size FACP battery backup",
                    "Calculate hydraulic pipe loss",
                    "Export engineering deliverable (DXF/IFC/PDF)",
                ],
                context_summary="Empty request received.",
                original_prompt=prompt,
            )

        return DisambiguationRequest(
            is_clarification_required=False,
            clarification_type="none",
            question="",
            missing_fields=[],
            options=[],
            context_summary="Intent appears complete.",
            original_prompt=prompt,
        )
