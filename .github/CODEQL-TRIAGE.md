# Code Scanning Triage Registry — backend/api_keys.py

This file records the standing triage decisions for CodeQL
`py/weak-sensitive-data-hashing` findings in `backend/api_keys.py`.
Each entry corresponds to a dismissed alert (`false positive`) whose
location is intentionally FROZEN — do not refactor above or within these
helpers without re-reviewing the matching dismissal.

| Line anchor | Helper / site | Rationale |
|-------------|----------------|-----------|
| `_legacy_long_key_bcrypt_input` | SHA-256 hex normalization for >72-byte keys | Pre-BLAKE2b stored bcrypt hashes keep verifying; bcrypt remains the credential KDF |
| `_normalize_key_for_bcrypt` (long-key branch) | BLAKE2b(digest_size=32) pre-hash feeding bcrypt | Digest is KDF input only, never a stored credential hash |
| `_lookup_key` | `bk$` keyed BLAKE2b O(1) index | Server-secret keyed index, never credential storage |
| `_legacy_hmac_lookup` | Frozen `hk$` HMAC-SHA256 index shim | One-time fallback for pre-migration records; entries are transparently re-keyed |
| `_hash_key` (fallback branch) | Salted HMAC-SHA256 storage when bcrypt unavailable | bcrypt is a hard dependency; format kept for stored-hash compatibility |
| `_verify_key` (hmac-sha256$ branch) | Verification of legacy salted stores | Constant-time compare during migration only |
| `_legacy_plain_sha256_compare` | Constant-time compare vs pre-bcrypt unsalted stores | validate_api_key lazily rehashes any entry that authenticates here |

Policy: these sites are migration shims with active drain paths (lazy
bcrypt upgrade + bk$ re-keying). New credential material NEVER flows into
SHA-256. If an alert re-opens at a different line after refactoring,
update this table and dismiss with reference to the corresponding row.
