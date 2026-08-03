"""
backend/llm_constants.py — Shared LLM safety constants.

PURPOSE
-------
Single source of truth for the AI advisory disclaimer and the chat persona
whitelist, shared by the LLM service (streaming + non-streaming paths) and the
LLM router. Previously the disclaimer lived only in ``backend/routers/llm.py``
(``_AI_DISCLAIMER``), which the streaming service could not import without an
upward dependency (service -> router). Hoisting it here removes that coupling
and guarantees every LLM output path carries the same safety label.

SAFETY NOTE
-----------
The disclaimer is part of the advisory-only contract: all AI-generated output
must be flagged as requiring verification by a licensed fire-protection
engineer against the published NFPA 72 / NEC code.
"""

from __future__ import annotations

from typing import Final

# Standard disclaimer appended to all AI-generated narratives.
# This protects the engineer and the AHJ (Authority Having Jurisdiction) by
# making it explicit that AI output is advisory and must be verified.
AI_DISCLAIMER: Final[str] = (
    "⚠️ AI-GENERATED CONTENT — Advisory only. This output was produced by an "
    "LLM and must be verified against the published NFPA 72 / NEC code by a "
    "licensed fire-protection engineer before use in a submittal."
)

# ── Chat role whitelist (F5a) ────────────────────────────────────────────────
# Replaces the free-text ``system`` field on POST /llm/chat. The server owns
# the persona text; callers may only select a predefined role. This prevents
# persona hijacking / system-prompt injection through the chat endpoint.

ENGINEER_ASSISTANT_ROLE = "engineer_assistant"
CODE_EXPLAINER_ROLE = "code_explainer"
NARRATIVE_WRITER_ROLE = "narrative_writer"

CHAT_ROLES: Final[tuple[str, ...]] = (
    ENGINEER_ASSISTANT_ROLE,
    CODE_EXPLAINER_ROLE,
    NARRATIVE_WRITER_ROLE,
)

PERSONAE: Final[dict[str, str]] = {
    ENGINEER_ASSISTANT_ROLE: (
        "You are a licensed fire-protection engineer assistant. Answer NFPA 72 "
        "and NEC code questions precisely, cite the relevant code sections, "
        "and flag any non-compliance. Do NOT invent code sections. All output "
        "is advisory and must be verified by a licensed engineer."
    ),
    CODE_EXPLAINER_ROLE: (
        "You are a licensed fire-protection engineer explaining NFPA 72 and "
        "NEC calculation results to a colleague. Be precise, cite the relevant "
        "code section, and flag any non-compliance. Do NOT invent code sections."
    ),
    NARRATIVE_WRITER_ROLE: (
        "You are a fire-protection engineer drafting compliance narratives for "
        "submittals. Use formal technical language, cite NFPA 72-2022 sections "
        "precisely, and do NOT invent requirements. If a calculation result is "
        "missing, note it as 'to be verified'."
    ),
}
