"""
tests/test_nemo_guardrails.py — Tests for NeMo Guardrails Integration Service.
==============================================================================
"""

import pytest
from fireai.infrastructure.nemo_guardrails_service import (
    GuardrailViolation,
    NeMoGuardrailsService,
)


class TestNeMoGuardrailsService:
    """Test suite for NeMo Guardrails Service."""

    @pytest.fixture
    def service(self):
        return NeMoGuardrailsService(enabled=True)

    def test_compliant_response_passes(self, service):
        query = "What is the smoke detector spacing?"
        response = "Spot-type smoke detectors should be spaced not more than 9.1m apart on smooth ceilings per NFPA 72 §17.7.3.2.3."
        is_safe, violations, text = service.validate_llm_response(query, response)
        assert is_safe is True
        assert len(violations) == 0
        assert text == response

    def test_excessive_spacing_claim_triggers_guardrail(self, service):
        query = "Can I space smoke detectors at 15 meters?"
        response = "Yes, you can install smoke detectors with 15.0m spacing on smooth ceilings."
        is_safe, violations, text = service.validate_llm_response(query, response)
        assert is_safe is False
        assert len(violations) > 0
        assert violations[0].rule_id == "NFPA72-17.7.3.2.3"
        assert "SAFETY GUARDRAIL NOTICE" in text

    def test_excessive_height_claim_triggers_guardrail(self, service):
        query = "Can I put spot smoke detectors on a 25m ceiling?"
        response = "Spot smoke detector at 25.0m height is compliant."
        is_safe, violations, text = service.validate_llm_response(query, response)
        assert is_safe is False
        assert violations[0].rule_id == "NFPA72-17.7.3.2.4"
        assert "SAFETY GUARDRAIL NOTICE" in text

    def test_excessive_voltage_drop_triggers_warning(self, service):
        query = "Is 15% voltage drop okay?"
        response = "The system has a voltage drop of 15.0% on the NAC circuit."
        is_safe, violations, text = service.validate_llm_response(query, response)
        assert is_safe is True  # Warning level does not block critical safety
        assert len(violations) == 1
        assert violations[0].rule_id == "NFPA72-10.14"
        assert violations[0].severity == "warning"

    def test_disabled_service_bypasses(self):
        disabled_service = NeMoGuardrailsService(enabled=False)
        query = "Spacing"
        response = "Spacing 20.0m is okay"
        is_safe, violations, text = disabled_service.validate_llm_response(query, response)
        assert is_safe is True
        assert len(violations) == 0
        assert text == response
