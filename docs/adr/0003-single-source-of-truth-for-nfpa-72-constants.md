# 0003 — Single Source of Truth for NFPA 72 Constants

## Status
Accepted

## Date
2026-07-27

## Context

Fire alarm engineering calculations must cite exact values from published
standards (NFPA 72-2022, NEC 2023). Prior to this decision, NFPA 72
constants were duplicated across five locations:

1. `fireai/constants/nfpa72.py`
2. `fireai/core/nfpa72_models.py` (inline literals)
3. `qomn_fire/core/constants.py` (independent copy)
4. `frontend/src/engine/` (TypeScript mirrors)
5. Ad-hoc values in test fixtures

Divergence was discovered during the C-03 audit: the voltage-drop
constant `4.263 Ω/km` was a phantom value that did not exist in NEC
Table 8 at any temperature. The first "fix" used `8.286 Ω/km` — the
solid-conductor value mislabeled as stranded. The correct stranded
value is `8.470 Ω/km`.

This pattern — silent constant drift causing incorrect engineering
results — is unacceptable in a safety-critical system.

## Decision

Establish `fireai/constants/nfpa72.py` as the **single canonical source**
for all NFPA 72-2022 constants. Every module — including `qomn_fire/`,
`qomn_conduit/`, `facp_system/`, and the frontend engine — must import
from this file. No other module may define duplicate constants.

The same pattern applies to `fireai/constants/nec.py` for NEC Chapter 9
Table 8 values.

### Enforcement Mechanisms

1. **CI regulatory-data-guard** — The `.github/workflows/regulatory-data-guard.yml`
   workflow fails the PR (exit 1) when attestation is missing for any change
   to files under `fireai/constants/`, `fireai/core/nfpa72_*.py`, or related
   paths.

2. **`ENGINEERING_BASIS.md`** — A consolidated reference file that maps every
   constant to its NFPA/NEC section citation. Any code change to a listed
   value MUST update this file.

3. **Audit trail** — Constants are part of the safety-critical audit scope.
   Changes require PE sign-off or verbatim standard citation in the commit
   message.

## Alternatives Considered

### Distributed constants with CI drift detection
- Pros: Each module is self-contained; no cross-module imports
- Cons: Divergence is detected only after it happens; requires complex
  diffing logic; silent drift is the exact problem we're solving
- Rejected: Reactive detection is insufficient for safety-critical values

### Frontend constants generated from backend at build time
- Pros: True SSoT; zero manual sync
- Cons: Requires a code-generation step; couples frontend build to backend
  runtime; adds complexity to the Vite build pipeline
- Rejected: Over-engineered for the current team size; can be revisited if
  drift becomes a recurring problem despite the SSoT rule

### Keep as-is with periodic manual audit
- Pros: Zero implementation cost
- Cons: This is exactly what failed — the C-03 and C-09 audits found
  phantom values and misapplied formulas that had been in production
- Rejected: Manual audits catch problems after they ship; SSoT prevents
  them from being introduced

## Consequences

- All engineers and agents must import constants from `fireai/constants/`.
  Duplicating a constant in any other file is a code-review blocker.
- The `ENGINEERING_BASIS.md` file must be kept in sync with
  `fireai/constants/nfpa72.py`. The regulatory-data-guard CI enforces this.
- The `qomn_fire/` standalone engine depends on `fireai/constants/` for
  its constants, coupling it to the main library. This is acceptable because
  `qomn_fire/` was always intended to share the canonical constants.
- New constants require a PE-reviewed citation before merge. The commit
  message must include the verbatim NFPA/NEC section reference.
- The frontend engine still maintains its own TypeScript constants, but
  these must mirror the Python SSoT. A future PR could add a
  Python-to-TypeScript code-generation step.
