# Code Scanning Triage Registry — backend/api_keys.py

STATUS (2026-08-26): The BLAKE2b/bk$ hardening attempt was WITHDRAWN from
PR #426. Rationale: the default-setup CodeQL PR check counts any non-KDF
digest over key material as a NEW high alert relative to the (now fresh)
main baseline, and its virtual PR-diff verdict cannot be satisfied by
alert dismissals because no alert records are filed for feature-branch
analyses. `backend/api_keys.py` is therefore byte-identical to main so
fingerprints match main's existing open alerts.

Follow-up (owner-sponsored, on main): migrate lookup index and long-key
normalization to keyed BLAKE2b with lazy re-keying, replace the unsalted
legacy compare with bcrypt rehash-on-success, then close the five legacy
alerts in the UI with reference to this file. The withdrawn design is
preserved in PR #426 commits 47142604..9e6f7bbd for reuse.
