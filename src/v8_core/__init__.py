"""
FireCalc Pro V8.0 — Core Safety Modules
========================================
Deterministic NFPA/NEC calculator with audit trail.
NOT an AI. NOT a self-learning system. NOT a simulator.

Every public function in this package:
  1. Returns a DecisionProvenance object (never a bare scalar).
  2. Cites the NFPA/NEC clause it applies.
  3. Requires a licensed PE to approve before any real-world use.

Module map:
  code_authority       — Versioned, FPE-signed code constants (NFPA 72, NEC).
  decision_provenance  — Structured output objects with citations + confidence.
  safety_optimizer     — Constrained optimization (safety-margin first, cost second).
  pattern_library      — Manually curated, FPE-approved precedent library.
  smoke_estimator      — Pre-screening estimator (±50%). NOT a simulation.
  linter_rules         — CI lint gates (banned words, literal constants, etc.).
"""
__version__ = "8.0.0"
__product_name__ = "FireCalc Pro"
__authority_model__ = "Software Vendor / Human-in-the-Loop / PE Required"
