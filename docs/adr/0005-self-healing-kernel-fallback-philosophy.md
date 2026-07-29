# 0005 — Self-Healing Kernel Fallback Philosophy

## Status
Accepted

## Date
2026-07-27

## Context

The QOMN engineering kernel (`fireai/core/qomn_kernel.py`) performs
safety-critical calculations: detector spacing, voltage drop, battery
capacity, and NAC design. These calculations must never return incorrect
results silently.

Historically, when a calculation failed (e.g., due to invalid input,
boundary-condition bugs, or numerical instability), the kernel would
raise an exception. In a web context, this produced 500 errors. In a
batch-processing context, it halted the entire pipeline.

The engineering review (C-01) flagged the initial "self-healing" approach
as "fail-quiet-to-death" — returning conservative fallback values without
visible indication that the result was healed rather than computed. This
is dangerous in a life-safety system because a healed result looks
identical to a correct result.

## Decision

Use a **tiered fallback philosophy** with mandatory safety classification:

### Tier 1 — Exception Catch + Safe Fallback (Default)

When a computation raises `PhysicsGuardError`, `ValueError`, or any
unexpected exception:
1. The exception is caught by `_healing_wrapper()`
2. A conservative fallback value is returned (e.g., `0 V` voltage drop,
   `72 Ah` battery capacity, `9.1 m` smoke spacing)
3. The result is tagged with `safety_tier="FALLBACK_USED"` and
   `requires_fpe_review=True`
4. The exception is logged to the HMAC-signed audit trail

### Tier 2 — Fail-Loud Mode (Opt-In)

Set `QOMN_FAIL_LOUD=1` to raise `QOMNCalculationError` instead of
returning a fallback. This wraps the original exception with the
intended fallback value for debugging. Use for:
- Safety-critical deployments where no computation may be silently healed
- Integration tests that must verify every calculation succeeds
- Debugging healing behavior

### Tier 3 — Circuit Breaker (Threshold)

Each failed computation accumulates toward a circuit-breaker threshold.
When the threshold is exceeded, the kernel enters a degraded mode and
refuses further calculations until manually reset. This prevents
cascading failures from producing an unbounded number of healed results.

### Safety Principle

**"Fail-safe with sentinel values that force manual investigation"** —
not "fail-loud with exceptions" and not "fail-quiet with silent healing."

Every healed result is:
- Tagged `safety_tier=FALLBACK_USED` (never `PROOF_VERIFIED`)
- Flagged `requires_fpe_review=True`
- Logged to the audit trail with the original exception message

This ensures healed results are **always** routed through FPE review
before being accepted as design output.

## Alternatives Considered

### Fail-loud only (no healing)
- Pros: Zero risk of silent incorrect results
- Cons: 500 errors in production; batch pipelines halt on first failure;
  16 existing tests depend on healing behavior
- Rejected: Too disruptive to operational reliability; the web UI must
  remain functional even when individual calculations fail

### Silent healing with logging
- Pros: Maximum uptime; users see results immediately
- Cons: Exactly the "fail-quiet-to-death" pattern the engineering review
  flagged — healed results are indistinguishable from correct results
- Rejected: Unacceptable in a life-safety system

### Return `None` / error sentinel
- Pros: Callers must explicitly handle the failure case
- Cons: Pushes error-handling burden to every caller; risk of `None`
  propagation causing downstream `TypeError`; still requires FPE review
- Rejected: The fallback-with-metadata approach is more informative and
  less error-prone for callers

## Consequences

- All 16 self-healing integration tests (`test_v214_self_healing_integration.py`)
  must continue to pass. The default behavior (Tier 1 healing) is preserved.
- The `SelfHealingQOMNKernel` is the module-level default kernel. Callers
  that need fail-loud semantics must set `QOMN_FAIL_LOUD=1` or instantiate
  `QOMNKernel` directly.
- Every healed computation triggers an audit-log entry. High failure rates
  will produce audit-log volume — this is intentional (visibility into
  healing frequency).
- The circuit-breaker threshold is currently hard-coded. A future PR should
  make it configurable via environment variable or API setting.
- FPE review is mandatory for any healed result that influences a design
  decision. The `requires_fpe_review=True` flag enables downstream systems
  to enforce this.
