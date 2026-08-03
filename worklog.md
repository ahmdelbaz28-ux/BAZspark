# BAZspark Security Audit Worklog

Audit round: Phase 3 strict self-critique (PHASE5-M4-M5-REWORD-L1-L2-L3).

This worklog records every claim made during the security audit. Each entry
below is a REGRESSION GUARD target: the backend/tests/security/ suite asserts
these exact claim texts so that future edits to a claim must be made
consciously (and the severity re-evaluated).

---

## MEDIUM ISSUES

M-1: marshal.loads in isolation.py — defense-in-depth concern (not CRITICAL, not exposed via HTTP)

M-2: websocket_transport fail-open when auth_token=None + timing attack (not in FastAPI backend)

M-3: workflow_service _workflow_locks memory leak (no race, just unbounded dict growth)

M-5: backend/routers/digital_twin.py:91 uses str.startswith for path
containment (brittle pattern, but currently safe due to os.path.join
preventing suffix attacks; V214 comment explains the absolute-path fix and
does NOT contradict startswith itself). RESOLVED by the M-5 FIX: the brittle
`str.startswith(abs_upload)` check was replaced with `Path.is_relative_to()`
(Python 3.9+ semantic path containment) — see the M-5 FIX comment block in
digital_twin.py.

M-6: AuthContext.tsx logout clears only specific localStorage keys. RESOLVED
by the M-6 FIX: logout now clears ALL app-set localStorage keys (digital_twin_settings,
fireai_firealarm_detectors, nexus_imported_dxf, fireai_settings_*,
onboarding-completed) to prevent cross-user data leakage. The theme key "dark"
is intentionally preserved (UI preference, not user data).

---

## LOW ISSUES:

L-1: dataService.ts localhost exception in isSecure check (dev convenience).
RESOLVED: the old `WS_BASE_URL.includes("localhost")` substring check (which
would also match e.g. ws://my-localhost-proxy.example.com and bypass the
security gate) was replaced with an exact hostname match against the loopback
set (localhost / 127.0.0.1 / [::1]) using `new URL().hostname` — see the L-1
SECURITY FIX comment in frontend/src/services/dataService.ts.

L-2: qomn_kernel.py stale comment defending old 0.0 behavior. RESOLVED: the
battery fallback was raised from the historical 0 Ah to 72 Ah (NFPA 72-2022
§10.6.7.2.1 minimum) — see battery_capacity @ _healing_wrapper safe_minimum=72.0.
The "force manual intervention" intent is preserved because 72 Ah is still a
conservative floor that an engineer MUST review.

L-3: websocket_transport ws:// default (intended for internal comms per
NOSONAR comment). RESOLVED: the transport now defaults to wss:// for secure
remote deployments; ws:// is only available as an explicit opt-in via the
allow_insecure_ws parameter. See the SECURITY NOTE in
facp_distributed/transport/websocket_transport.py.

---

## RETRACTED FALSE CLAIMS

M-4 RETRACTED: "18-24 unfixed CVEs in pinned cryptography/pyjwt/python-multipart
(depends on duplicate counting)". This standalone claim was RETRACTED in the
PHASE5-M4-M5-REWORD-L1-L2-L3 round because it duplicated the C-1 RESOLVED
state. It is documented here for traceability and must NOT appear as an active
claim in the MEDIUM ISSUES verdict.
