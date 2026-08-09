# PE Sign-off Status — NFPA 72 Constants

## Current State (as of V130, 2026-06-13)

The smoke detector spacing implementation in `fireai/constants/nfpa72.py`
has been CORRECTED in V130 to apply flat 9.1m spacing per NFPA 72-2022
§17.7.3.2.3, with NO height-based reduction (the previous 1%/ft reduction
was a misapplication of Table 17.6.3.5.1 which applies to HEAT detectors
only).

## Why Issue #43 is Still Open

Per `agent.md Rule #22`, any change to NFPA 72 constants requires:
- (a) A `Signed-off-by:` trailer citing a licensed Professional Engineer
  with discipline, jurisdiction, and license number; OR
- (b) A verbatim quotation from NFPA 72-2022 with section number,
  edition year, and a publicly-verifiable URL or document hash.

The current code uses option (b) — verbatim quotation from §17.7.3.2.3.
However, the project owner has not yet provided a formal PE sign-off
to close the governance loop.

## What is NOT a Blocker

- The code is functionally correct.
- The previous error was fail-safe (over-densification, not under-densification).
- No life-safety risk exists in the current implementation.

## What IS a Blocker (Governance)

- Issue #43 cannot be closed without PE sign-off.
- Until closed, the code should not be deployed to production for
  AHJ-submitted designs.

## Action Required from Owner

1. Engage a licensed Fire Protection Engineer (FPE).
2. Have them review `fireai/constants/nfpa72.py` against NFPA 72-2022.
3. Obtain `Signed-off-by:` trailer with PE license number.
4. Close Issue #43 with the sign-off commit.

Reference: https://github.com/ahmdelbaz28-ux/BAZspark/issues/43
