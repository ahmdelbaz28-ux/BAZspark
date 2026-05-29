"""
FireAI NFPA 72 Rules Engine — Safety-Critical Declarative Rules System
======================================================================

A pure-Python forward-chaining rules engine designed specifically for
NFPA 72 fire alarm compliance. Inspired by the Rete algorithm from
durable_rules (jruizgit/rules) but rebuilt from scratch with:

1. Full audit trail for every rule evaluation (safety-critical requirement)
2. Truth Maintenance System (TMS) — derived conclusions retract when
   base facts change
3. Priority-based conflict resolution with deterministic ordering
4. Thread-safe operation for concurrent analysis sessions
5. No C dependencies — pure Python for memory safety and auditability
6. Structured rule definitions with NFPA section references

Architecture:
    Fact → Alpha Network (condition matching) → Beta Network (join evaluation)
    → Action Scheduling → Conflict Resolution → Action Execution → TMS Update

Reference: NFPA 72-2022, IEC 60079-10-1:2015, NEC Chapter 9
"""

from fireai.core.rules_engine.engine import (
    RulesEngine,
    Rule,
    Fact,
    RulePriority,
    RuleResult,
    RuleAuditEntry,
)

from fireai.core.rules_engine.truth_maintenance import (
    TruthMaintenanceSystem,
    DependencyRecord,
)

from fireai.core.rules_engine.nfpa72_rules import NFPA72RuleSet

__all__ = [
    "RulesEngine",
    "Rule",
    "Fact",
    "RulePriority",
    "RuleResult",
    "RuleAuditEntry",
    "TruthMaintenanceSystem",
    "DependencyRecord",
    "NFPA72RuleSet",
]

__version__ = "1.0.0"
