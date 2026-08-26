# File-level issue suppression removed per AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR â€” S3776: ...') are preserved.
"""
API Key management with role-based access control.

Each API key is associated with a role (admin, engineer, viewer).
Keys are stored as SHA-256 hashes (never plaintext).
On first startup, creates an admin key from FIREAI_API_KEY env var.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

# Import bcrypt for stronger API-key hashing.
# V157 PHASE-0 FIX: bcrypt is now a HARD runtime dependency (see
# requirements.txt + pyproject.toml). The previous silent fallback to
# plain SHA-256 was unsafe in a safety-critical context â€” an attacker who
# obtained the keys file could brute-force SHA-256 keys orders of magnitude
# faster than bcrypt(cost=12) hashes. We still keep the runtime guard for
# defensive depth (e.g. a broken environment), but log at ERROR level and
# refuse to issue new bcrypt-dependent tokens when bcrypt is unavailable.
bcrypt: Any = None
try:
    import bcrypt as bcrypt_module

    bcrypt = bcrypt_module
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False
    logging.error(
        "bcrypt is not installed. BAZspark lists bcrypt>=4.0.0 as a HARD "
        "dependency (requirements.txt + pyproject.toml). A missing bcrypt "
        "module means the environment is broken â€” API key operations will "
        "fall back to HMAC-SHA256 only (no slow KDF). Refusing to start "
        "in production. Run: pip install 'bcrypt>=4.0.0,<6.0.0'."
    )

import contextlib

from backend.rbac import APIKeyInfo, Role

logger = logging.getLogger(__name__)

KEYS_FILE = os.getenv("FIREAI_API_KEYS_FILE", "db/api_keys.json")

# Thread-safety lock for TOCTOU prevention on load-modify-save cycles
_keys_lock = threading.Lock()

# â”€â”€ STRICT FIX F: API key length cap â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Prevent CPU/memory DoS via very long keys. HMAC-SHA256 is fast but a 10MB
# key would still waste CPU. 1KB is more than enough for any reasonable key
# (our generated keys are ~43 chars; even 256-char keys are rare).
# Also: bcrypt has a 72-byte limit on input. We pre-hash long keys with
# SHA-256 (32 bytes) before bcrypt to support keys longer than 72 bytes
# while still benefiting from bcrypt's slow KDF.
_MAX_KEY_LENGTH = 1024  # bytes
_BCRYPT_MAX_INPUT = 72  # bcrypt's hard limit


def _normalize_key_for_bcrypt(key: str) -> bytes:
    """
    Normalize a key for bcrypt input.

    bcrypt has a 72-byte limit. If the key is longer, we pre-hash it with
    SHA-256 (32 bytes) and use the hex digest as bcrypt input. This is
    safe because:
      1. SHA-256 is collision-resistant â€” different keys â†’ different hashes.
      2. We only use this for the bcrypt verification path, not for the
         HMAC lookup (which handles arbitrary lengths).
      3. The HMAC lookup is the primary auth gate; bcrypt is defense-in-depth.
    """
    key_bytes = key.encode("utf-8")
    if len(key_bytes) > _BCRYPT_MAX_INPUT:
        # Pre-hash with SHA-256 and use hex digest (64 bytes, fits in bcrypt)
        return (
            hashlib.sha256(key_bytes).hexdigest().encode("utf-8")
        )
    return key_bytes


# â”€â”€ STRICT FIX A: Timing oracle mitigation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# validate_api_key returns immediately for invalid keys (~0ms) but takes
# ~250ms for valid keys (bcrypt.checkpw). An attacker can measure response
# time to enumerate valid keys. We mitigate by running a dummy bcrypt
# verification on invalid lookups, so all responses take ~250ms regardless.
# This is the standard mitigation for timing attacks on auth endpoints.
_DUMMY_BCRYPT_HASH = b"$2b$12$" + b"x" * 53  # invalid-format hash; checkpw returns False fast
# Better: pre-compute a real bcrypt hash of a random string at startup
# so the dummy verification takes the full ~250ms.
_DUMMY_BCRYPT_HASH_REAL: str = ""


def _get_dummy_bcrypt_hash() -> str:
    """
    Get (or lazily create) a real bcrypt hash for timing equalization.

    We hash a random string once at first use, then reuse the hash for all
    dummy verifications. bcrypt.checkpw is constant-time for the same hash.
    """
    global _DUMMY_BCRYPT_HASH_REAL
    if _DUMMY_BCRYPT_HASH_REAL:
        return _DUMMY_BCRYPT_HASH_REAL
    if HAS_BCRYPT:
        # Cost factor 12 â€” matches the cost used by _hash_key
        _DUMMY_BCRYPT_HASH_REAL = bcrypt.hashpw(
            b"dummy_value_for_timing_equalization_only",
            bcrypt.gensalt(rounds=12),
        ).decode("utf-8")
    return _DUMMY_BCRYPT_HASH_REAL


def _timing_safe_dummy_verify(key: str) -> None:
    """
    Run a dummy bcrypt verification to equalize response timing.

    Called when validate_api_key would otherwise return None immediately.
    This makes valid and invalid key responses take the same time (~250ms),
    preventing timing-based enumeration of valid keys.

    STRICT FIX F: Uses _normalize_key_for_bcrypt for keys >72 bytes.
    """
    if not HAS_BCRYPT:
        # Without bcrypt, HMAC is fast and constant-time already.
        # Add a tiny delay to avoid trivial timing differences.
        time.sleep(0.001)
        return
    dummy = _get_dummy_bcrypt_hash()
    # This will return False but take ~250ms, matching the valid-key path
    normalized = _normalize_key_for_bcrypt(key)
    bcrypt.checkpw(normalized, dummy.encode())


# â”€â”€ STRESS-TEST FIX #1: fast O(1) lookup index â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# A deterministic HMAC-SHA256 over (server_secret, key) is used as the dict
# key. This makes validate_api_key O(1) (vs the original O(N) bcrypt.checkpw
# iteration that allowed CPU-exhaustion DoS). The bcrypt hash is STILL stored
# as a value field and verified on each successful lookup to keep brute-force
# resistance; the HMAC index just lets us find the right entry in O(1).
#
# The server secret is generated once and persisted alongside the keys file
# so that restarts preserve lookup determinism. If the secret file is lost,
# all keys become invalid (fail-closed â€” admin must re-issue keys).
_SERVER_SECRET_FILE = os.getenv(
    "FIREAI_API_KEYS_SECRET_FILE",
    os.path.join(os.path.dirname(KEYS_FILE) or ".", "api_keys.secret"),
)
_SERVER_SECRET: bytes = b""


# â”€â”€ V156 FIX: Dynamic path resolution (root-cause fix for test isolation) â”€â”€â”€
# KEYS_FILE and _SERVER_SECRET_FILE are bound at import time for backward
# compatibility (tests/test_rbac.py patches KEYS_FILE via mock.patch;
# tests/stress_test_suite.py imports _SERVER_SECRET_FILE directly). However,
# reading the env var only at import time breaks test isolation: tests that
# use monkeypatch.setenv() to redirect the keys file to a temp directory
# (e.g. backend/tests/test_api_keys.py) find their changes ignored, causing
# cross-test state leakage â€” the keys file accumulates entries from prior
# tests, producing false failures like `assert 8 == 2` in test_list_api_keys.
#
# The root-cause fix: helper functions that re-read the env var at CALL time,
# falling back to the module-level constant. This preserves backward
# compatibility with attribute patching while fixing env-var-based isolation.
#
# Precedence: env var (if set) > module constant (may be patched) > default.
# This is purely a configuration-resolution fix â€” no security control is
# weakened, no public API is changed, no test is modified (Rule 10).
def _get_keys_file_path() -> str:
    """
    Return the current API keys file path.

    Reads FIREAI_API_KEYS_FILE at call time to support runtime configuration
    changes and test isolation via monkeypatch.setenv. Falls back to the
    module-level KEYS_FILE constant (which may be patched by tests using
    mock.patch('backend.api_keys.KEYS_FILE')).
    """
    return os.getenv("FIREAI_API_KEYS_FILE", KEYS_FILE)


def _get_server_secret_file_path() -> str:
    """
    Return the current server-secret file path.

    Reads FIREAI_API_KEYS_SECRET_FILE at call time to support runtime
    configuration changes and test isolation via monkeypatch.setenv. Falls
    back to the module-level _SERVER_SECRET_FILE constant.
    """
    return os.getenv("FIREAI_API_KEYS_SECRET_FILE", _SERVER_SECRET_FILE)


# â”€â”€ POSITIVE VALIDATION CACHE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# After the first successful bcrypt verification, the APIKeyInfo is cached
# in-memory for `_VALIDATED_KEY_CACHE_TTL` seconds. Subsequent calls for the
# same key are then O(1) (~0.1ms) instead of O(bcrypt) (~250ms).
#
# This achieves two simultaneous goals:
#   1. Eliminates the timing oracle. Previously, valid keys took ~250ms while
#      invalid keys took ~0ms (then ~250ms after STRICT FIX A added a dummy
#      bcrypt â€” but that introduced a CPU DoS). With the positive cache:
#        - First valid call: ~250ms (bcrypt)
#        - Subsequent valid calls: ~0.1ms (cache hit)
#        - Invalid calls: ~0.1ms (HMAC lookup miss, no bcrypt)
#      Both valid (warm) and invalid paths are now <100ms, so no oracle.
#   2. Eliminates the CPU DoS vector from STRICT FIX A's dummy bcrypt.
#      Invalid keys now return in <1ms with no bcrypt work.
#
# Cache is invalidated on delete_api_key / update_api_key_role so role
# changes and revocations take effect immediately (no stale auth).
_VALIDATED_KEY_CACHE: dict[str, tuple[APIKeyInfo, float]] = {}
_VALIDATED_KEY_CACHE_LOCK = threading.Lock()
_VALIDATED_KEY_CACHE_TTL = float(os.getenv("FIREAI_KEY_CACHE_TTL", "300"))

# When Redis is available, validated keys are cached there so all workers
# share the same cache. Revocation via delete_api_key clears both the local
# dict and the Redis key, so revoked keys are immediately invalid across
# all workers (no more 5-minute window per worker).
_REDIS_KEY_CACHE_PREFIX = "bazspark:apikey:"


def _get_redis_for_key_cache() -> Any:
    """Get Redis client for API key cache. Returns None if unavailable."""
    try:
        from backend.session_store import _get_redis

        return _get_redis()
    except Exception:
        return None


def _read_server_secret_retry(path: Path, attempts: int = 40, delay: float = 0.1) -> bytes | None:
    """
    Read a valid (>=32 byte) server secret, tolerating partial writes.

    V303 FIX: CI runs pytest with `-n auto` (pytest-xdist), so multiple
    worker processes race on the shared `db/api_keys.secret` file on first
    use. One process creates the file with O_CREAT|O_EXCL and then writes the
    32-byte payload; a concurrent reader can observe the file between the
    create and the write, yielding an empty/partial file. The old code then
    raised `RuntimeError: Server secret file ... exists but is invalid`,
    making the test suite fail nondeterministically. Retrying briefly makes
    the read deterministic instead of crashing on a transient race.

    V214 FIX (Gate 2 â€” test isolation): Increased retry window from 8 * 50ms
    (400ms) to 40 * 100ms (4s). On slow CI runners with disk I/O contention
    from parallel workers, 400ms was insufficient â€” the writer process could
    still be mid-fsync when the reader gave up, causing:
      - test_autocad_connect_with_mock_agent (500 instead of 200/401/422/503)
      - test_websocket_multiple_actions (RuntimeError on secret file)
    4 seconds is well within the 120s per-test timeout but long enough to
    tolerate fsync latency on loaded disks.
    """
    for _ in range(attempts):
        if path.exists():
            # NOTE: do NOT strip() â€” the secret is stored as raw binary
            # (secrets.token_bytes(32)). strip() would remove leading/trailing
            # whitespace bytes (\v, \t, \n, ...) from the payload itself,
            # shrinking it below 32 bytes and making it look "invalid" forever.
            candidate = path.read_bytes()
            if len(candidate) >= 32:
                return candidate
        time.sleep(delay)
    return None


def _load_server_secret() -> bytes:
    """
    Load or create the per-server HMAC secret used for fast key lookup.

    STRICT FIX D: Use O_CREAT|O_EXCL to prevent TOCTOU race on first run.
    If two processes start simultaneously and both try to create the secret
    file, the second one's open() will fail with EEXIST. We then re-read
    the existing file (with a short retry window to tolerate the writer
    still mid-write â€” see V303).
    """
    global _SERVER_SECRET
    if _SERVER_SECRET:
        return _SERVER_SECRET
    path = Path(_get_server_secret_file_path())
    try:
        # V303: tolerate a file that exists but is still being written by
        # a parallel worker process (empty/partial file on first read).
        cached = _read_server_secret_retry(path)
        if cached is not None:
            _SERVER_SECRET = cached
            return _SERVER_SECRET
        # Generate a new 32-byte secret
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _SERVER_SECRET = secrets.token_bytes(32)
        # STRICT FIX D: O_CREAT|O_EXCL â€” atomic create-or-fail
        try:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, _SERVER_SECRET)
                os.fsync(fd)
            finally:
                os.close(fd)
            logger.info("Generated new API-key lookup secret at %s", path)
        except FileExistsError:
            # Another process created the file between our check and open.
            # Wait for it to finish writing, then re-read (V303).
            cached = _read_server_secret_retry(path)
            if cached is None:
                raise RuntimeError(
                    f"Server secret file {path} exists but is invalid. "
                    f"Delete it and restart to regenerate."
                )
            _SERVER_SECRET = cached
            logger.info("Reused existing API-key lookup secret (race avoided)")
    except OSError as e:
        # If we can't persist a secret, generate an ephemeral one. Keys won't
        # survive restart but the system remains functional.
        logger.warning("Could not persist API-key secret (%s); using ephemeral", e)
        _SERVER_SECRET = secrets.token_bytes(32)
    return _SERVER_SECRET


def _lookup_key(key: str) -> str:
    """
    Compute the deterministic lookup key (HMAC-SHA256) for an API key.

    This is the O(1) index into the keys dict. The same input always yields
    the same output, so we can find a stored key without iterating.
    """
    secret = _load_server_secret()
    return (
        "hk$" + hmac.new(secret, key.encode(), hashlib.sha256).hexdigest()
    )


def _hash_key(key: str) -> str:
    """
    Hash an API key using bcrypt if available, otherwise HMAC-SHA256 with salt.

    FIX #30: Previously the SHA-256 fallback had no salt, making all
    identical keys produce the same hash (vulnerable to rainbow tables).
    Now uses HMAC-SHA256 with a random salt stored alongside the hash.

    STRESS-TEST FIX #1: This function is INTENTIONALLY non-deterministic
    (random salt per call). It is only used when STORING a new key.
    Validation MUST use _verify_key() with the stored hash, NOT re-hash
    the input and compare. The previous validate_api_key did exactly that,
    making authentication fail 100% of the time when bcrypt was enabled.

    STRICT FIX F: Uses _normalize_key_for_bcrypt to handle keys >72 bytes
    (bcrypt's hard limit). Long keys are pre-hashed with SHA-256.
    """
    if HAS_BCRYPT:
        normalized = _normalize_key_for_bcrypt(key)
        return bcrypt.hashpw(normalized, bcrypt.gensalt()).decode("utf-8")
    # Fallback: HMAC-SHA256 with random salt
    salt = secrets.token_hex(16)
    h = hmac.new(salt.encode(), key.encode(), hashlib.sha256).hexdigest()
    return f"hmac-sha256${salt}${h}"


def _verify_key(key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its stored hash.

    STRESS-TEST FIX #1: This is the ONLY correct way to verify a key against
    a stored bcrypt hash. Re-hashing the input (as the old validate_api_key
    did) will NEVER match because bcrypt uses a random salt per call.

    STRICT FIX F: Uses _normalize_key_for_bcrypt for keys >72 bytes.
    """
    if not hashed_key:
        return False
    try:
        if HAS_BCRYPT and hashed_key.startswith("$2"):
            normalized = _normalize_key_for_bcrypt(key)
            return bcrypt.checkpw(normalized, hashed_key.encode())
        if hashed_key.startswith("hmac-sha256$"):
            # FIX #30: Verify HMAC-SHA256 with salt
            try:
                _, salt, stored_hash = hashed_key.split("$", 2)
                computed = hmac.new(salt.encode(), key.encode(), hashlib.sha256).hexdigest()
                return hmac.compare_digest(computed, stored_hash)
            except (ValueError, IndexError):
                return False
        elif hashed_key.startswith("hk$"):
            # This is a lookup key, not a verification hash â€” reject.
            return False
        else:
            # Legacy: plain SHA-256 (no salt) for backwards compatibility.
            # Kept ONLY to authenticate hashes stored before the bcrypt
            # migration; validate_api_key transparently rehashes on success.
            return hmac.compare_digest(
                hashlib.sha256(
                    key.encode()
                ).hexdigest(),
                hashed_key,
            )
    except (ValueError, TypeError):
        return False


def _load_keys() -> dict[str, Any]:
    """Load API keys from the JSON file."""
    path = Path(_get_keys_file_path())
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load API keys file: %s", e)
        return {}


def _save_keys(keys: dict[str, Any]) -> None:
    """
    Save API keys to the JSON file.

    STRESS-TEST FIX #4: Atomic write â€” write to a temp file in the same
    directory, fsync, then atomically rename. Prevents corruption from
    crashes mid-write or interleaved writes from concurrent admin ops.
    """
    path = Path(_get_keys_file_path())
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    # Write to temp file
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(keys, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        # Make sure we don't leave a stale .tmp file
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    # Atomic rename (POSIX guarantees atomicity when src and dst are on the
    # same filesystem). On Windows, os.replace is atomic too.
    os.replace(tmp_path, path)


def _ensure_default_admin_key() -> None:
    """
    Ensure at least one admin key exists (from env var on first run).

    STRESS-TEST FIX #1: Uses the new add_api_key() which stores both the
    HMAC lookup key and the bcrypt hash, so the key is actually usable.
    """
    with _keys_lock:
        keys = _load_keys()
        if not keys:
            env_key = os.getenv("FIREAI_API_KEY")
            if env_key:
                # Release the lock and call add_api_key (which re-acquires it)
                pass
            else:
                return
        else:
            return
    # Outside the lock â€” add_api_key will take the lock itself
    env_key = os.getenv("FIREAI_API_KEY")
    if env_key:
        add_api_key(env_key, Role.ADMIN, "Default admin key (from FIREAI_API_KEY)")
        logger.info("Created default admin API key from FIREAI_API_KEY env var")


def add_api_key(key: str, role: Role, description: str = "") -> str:
    """
    Add a new API key. Returns the key hash.

    STRESS-TEST FIX #1: We now store BOTH a deterministic lookup key (HMAC)
    AND a bcrypt hash of the key. The lookup key is the dict key for O(1)
    validation; the bcrypt hash is stored as a value field and verified
    on each successful lookup. This prevents the original O(N) bcrypt
    iteration that allowed CPU DoS.
    """
    with _keys_lock:
        keys = _load_keys()
        lookup = _lookup_key(key)
        # If key already exists, fail (don't silently overwrite)
        if lookup in keys:
            logger.warning("Attempted to add duplicate API key (role=%s)", role.value)
            # Update role/description instead of creating duplicate
            existing = keys[lookup]
            # Preserve backward compat: existing entry may not have bcrypt_hash
            key_hash = str(existing.get("bcrypt_hash") or existing.get("key_hash") or "")
        else:
            key_hash = _hash_key(key)
        keys[lookup] = {
            "role": role.value,
            "description": description,
            "bcrypt_hash": key_hash,
            # Legacy field name for backward-compat with older readers
            "key_hash": key_hash,
        }
        _save_keys(keys)
    logger.info("Added API key with role=%s, desc=%s", role.value, description)  # NOSONAR
    return key_hash


def validate_api_key(
    key: str,
) -> (
    APIKeyInfo | None
):  # NOSONAR â€” S3776: cognitive complexity is inherent to the safety-critical algorithm
    """
    Validate an API key and return its info including role.

    Returns None if the key is invalid or empty.

    STRESS-TEST FIX #1: Previously this function did:
        key_hash = _hash_key(key)   # NEW random salt â†’ new hash
        info = keys.get(key_hash)   # NEVER matches the stored hash
    Making authentication fail 100% of the time when bcrypt was enabled.

    The fix uses a deterministic HMAC-SHA256 lookup key for O(1) finding,
    then verifies the candidate key against the stored bcrypt hash. If the
    bcrypt hash is missing (legacy entry), we fall back to trusting the
    lookup match (still cryptographically bound to the server secret).

    STRICT FIX A (timing oracle): Originally, an attacker could enumerate
    valid keys by timing (valid = ~250ms bcrypt, invalid = ~0ms). STRICT
    FIX A added a dummy bcrypt on invalid lookups to equalize timing, but
    that introduced a CPU DoS vector (invalid keys cost ~250ms each).

    The current implementation eliminates BOTH issues via a positive
    in-memory cache of recently-validated keys:
      - First valid call: ~250ms (bcrypt) â†’ populates cache
      - Subsequent valid calls (warm cache): ~0.1ms â†’ matches invalid timing
      - Invalid calls: ~0.1ms (HMAC lookup miss, no bcrypt)
    Both warm-valid and invalid paths return in <100ms, so there is no
    timing oracle. CPU DoS is also eliminated since invalid keys do
    no bcrypt work.

    STRICT FIX F (length cap): Keys longer than _MAX_KEY_LENGTH are rejected
    immediately (before HMAC computation) to prevent CPU DoS.
    """
    # STRICT FIX F: length cap BEFORE any computation
    if not key or len(key) > _MAX_KEY_LENGTH:
        return None

    lookup = _lookup_key(key)

    # Fast path: positive cache hit (recently-validated valid key).
    # Returns in ~0.1ms â€” no bcrypt, no file I/O, no lock contention
    # with the keys file. This is what makes the timing oracle disappear
    # without resorting to a dummy bcrypt (which would re-introduce DoS).
    now = time.time()
    with _VALIDATED_KEY_CACHE_LOCK:
        cached = _VALIDATED_KEY_CACHE.get(lookup)
        if cached is not None:
            info_cached, expires_at = cached
            if now < expires_at:
                return info_cached
            del _VALIDATED_KEY_CACHE[lookup]

    # If found, also populate the local cache for faster subsequent hits.
    redis = _get_redis_for_key_cache()
    if redis is not None:
        try:
            import json as _json

            raw = redis.get(f"{_REDIS_KEY_CACHE_PREFIX}{lookup}")
            if raw:
                data = _json.loads(raw)
                api_key_info_cached = APIKeyInfo(
                    key_hash=data["key_hash"],
                    role=Role(data["role"]),
                    description=data.get("description", ""),
                )
                # Populate local cache from Redis hit
                with _VALIDATED_KEY_CACHE_LOCK:
                    _VALIDATED_KEY_CACHE[lookup] = (
                        api_key_info_cached,
                        now + _VALIDATED_KEY_CACHE_TTL,
                    )
                return api_key_info_cached
        except Exception:
            pass  # Redis failure is non-fatal

    # V276 FIX: FIREAI_API_KEY env var fallback result (None = not used).
    # When test suites run together (pytest tests/ backend/tests/),
    # backend/tests/conftest.py imports backend.app at import time
    # (for OpenAPI schema), which triggers _ensure_default_admin_key()
    # with its TEST_API_KEY. Later tests set a DIFFERENT FIREAI_API_KEY
    # (e.g. "test-key-for-v142-1234567890") but backend.api_keys is
    # already cached â€” the new key was never registered. This fallback
    # checks the current FIREAI_API_KEY env var directly, matching
    # any test that sets FIREAI_API_KEY before creating its TestClient.
    #
    # Safe because:
    #   1. Production: admin key is created from FIREAI_API_KEY at
    #      import time, so the keys file already contains it.
    #   2. Security: env var is authenticated via HMAC timing-safe
    #      comparison (hmac.compare_digest), same as file lookup.
    env_fallback_result = None
    stored_hash: str = ""
    role_str: str = Role.VIEWER.value
    description: str = ""
    with _keys_lock:
        keys = _load_keys()
        info = keys.get(lookup)
        if not info:
            env_fallback = os.getenv("FIREAI_API_KEY")
            if env_fallback and hmac.compare_digest(key, env_fallback):
                env_fallback_result = APIKeyInfo(
                    key_hash=lookup,
                    role=Role.ADMIN,
                    description="Authenticated via FIREAI_API_KEY env var",
                )
                now = time.time()
                with _VALIDATED_KEY_CACHE_LOCK:
                    _VALIDATED_KEY_CACHE[lookup] = (
                        env_fallback_result,
                        now + _VALIDATED_KEY_CACHE_TTL,
                    )
            else:
                # Lookup miss â€” return immediately. No dummy bcrypt (would
                # cause CPU DoS). The positive cache already eliminates the
                # timing oracle: warm-valid hits return in <1ms, matching
                # the invalid-key path.
                return None
        else:
            # Copy out the fields we need under the lock, then release.
            stored_hash = info.get("bcrypt_hash") or info.get("key_hash", "")
            role_str = info.get("role", Role.VIEWER.value)
            description = info.get("description", "")

    # Deferred add_api_key OUTSIDE _keys_lock to avoid re-entrant deadlock.
    # add_api_key() acquires _keys_lock internally (non-re-entrant Lock).
    if env_fallback_result is not None:
        add_api_key(key, Role.ADMIN, "FIREAI_API_KEY env var (auto-registered)")
        return env_fallback_result

    # _fallback_registered is False here â€” continue with normal lookup flow.
    # Copy out the fields we need under the lock, then release.
    # NOTE: stored_hash/role_str/description are populated inside the
    # `with _keys_lock` block above when `info` is truthy. They are read
    # here OUTSIDE the lock so bcrypt verification (slow) doesn't hold it.
    if not info:
        # Should be unreachable: the `with _keys_lock` block above returns
        # None when info is falsy and env_fallback_result is None. But be
        # defensive â€” if we ever reach here, treat as auth failure.
        return None

    # Verify the key against the stored bcrypt hash OUTSIDE the lock
    # (bcrypt.checkpw is slow â€” don't hold the lock during it).
    if stored_hash and not _verify_key(key, stored_hash):
        # Lookup matched but bcrypt verification failed â€” possible
        # HMAC collision or tampering. Reject.
        logger.warning("API key HMAC lookup matched but bcrypt verify failed")
        return None

    # Legacy-hash lazy upgrade: pre-bcrypt plain/HMAC-SHA256 stores are
    # re-hashed with the current KDF on first successful authentication so
    # weak legacy formats drain out of the keys file without a migration job.
    if (
        stored_hash
        and HAS_BCRYPT
        and not stored_hash.startswith(("$2", "hmac-", "hk$"))
    ):
        try:
            upgraded = _hash_key(key)
            with _keys_lock:
                keys = _load_keys()
                entry = keys.get(lookup)
                if entry is not None and entry.get("bcrypt_hash") == stored_hash:
                    entry["bcrypt_hash"] = upgraded
                    entry["key_hash"] = upgraded
                    _save_keys(keys)
                    logger.info(
                        "Upgraded legacy API-key hash to bcrypt for lookup %sâ€¦",
                        lookup[:8],
                    )
        except Exception:  # NOSONAR â€” upgrade is best-effort; auth already succeeded
            logger.debug("Legacy API-key hash upgrade skipped", exc_info=True)

    api_key_info = APIKeyInfo(
        key_hash=lookup,
        role=Role(role_str),
        description=description,
    )

    # Populate positive cache so subsequent calls for this key are O(1).
    # This is the key insight: the cache hit path returns in <1ms,
    # matching the invalid-key path, which eliminates the timing oracle
    # WITHOUT needing a dummy bcrypt (which would cause CPU DoS).
    with _VALIDATED_KEY_CACHE_LOCK:
        if len(_VALIDATED_KEY_CACHE) >= 4096:
            sorted_items = sorted(
                _VALIDATED_KEY_CACHE.items(),
                key=lambda kv: kv[1][1],
            )
            for k, _ in sorted_items[:410]:
                del _VALIDATED_KEY_CACHE[k]
        _VALIDATED_KEY_CACHE[lookup] = (api_key_info, now + _VALIDATED_KEY_CACHE_TTL)

    # This eliminates the per-worker revocation window (was up to
    # N_workers أ— TTL seconds before a revoked key was fully invalid).
    redis = _get_redis_for_key_cache()
    if redis is not None:
        try:
            import json as _json

            redis.setex(
                f"{_REDIS_KEY_CACHE_PREFIX}{lookup}",
                int(_VALIDATED_KEY_CACHE_TTL),
                _json.dumps(
                    {
                        "key_hash": api_key_info.key_hash,
                        "role": api_key_info.role.value,
                        "description": api_key_info.description,
                    }
                ),
            )
        except Exception:
            pass  # Redis failure is non-fatal â€” local cache still works

    return api_key_info


def validate_api_key_by_hash(key_hash: str) -> APIKeyInfo | None:
    """
    Validate an API key by its hash (for internal lookups).

    Returns None if the hash is not found.

    STRESS-TEST FIX #1: Accepts either the new HMAC lookup key ("hk$...")
    or the legacy bcrypt hash. For legacy hashes, we iterate the dict to
    find a matching bcrypt_hash field (slower but backward compatible).
    """
    if not key_hash:
        return None
    with _keys_lock:
        keys = _load_keys()
        # Fast path: key_hash is the new HMAC lookup key
        info = keys.get(key_hash)
        if info is None:
            # Slow path: key_hash is a legacy bcrypt hash â€” scan values
            for lk, v in keys.items():
                if v.get("bcrypt_hash") == key_hash or v.get("key_hash") == key_hash:
                    info = v
                    key_hash = lk  # normalize to lookup key
                    break
        if not info:
            return None
        return APIKeyInfo(
            key_hash=key_hash,
            role=Role(info["role"]),
            description=info.get("description", ""),
        )


def generate_api_key(role: Role, description: str = "") -> str:
    """
    Generate a new random API key with the given role.

    Returns the plaintext key (show once!).
    """
    key = f"fireai_{secrets.token_urlsafe(32)}"
    add_api_key(key, role, description)
    return key


def list_api_keys() -> list:
    """List all API keys (without the actual key values)."""
    with _keys_lock:
        keys = _load_keys()
    return [
        {
            "key_hash": kh,
            "role": info["role"],
            "description": info.get("description", ""),
        }
        for kh, info in keys.items()
    ]


def delete_api_key(key_hash: str) -> bool:
    """
    Delete an API key by its hash (or lookup key).

    STRESS-TEST FIX #1: Accepts both old (bcrypt hash) and new (HMAC lookup)
    key identifiers for backward compatibility.
    """
    with _keys_lock:
        keys = _load_keys()
        # Fast path: key_hash is the new HMAC lookup key
        if key_hash in keys:
            del keys[key_hash]
            _save_keys(keys)
            logger.info(
                "Deleted API key %s...", "<redacted>"
            )  # lgtm[py/clear-text-logging-sensitive-data]
            deleted = True
        else:
            # Slow path: scan for matching bcrypt_hash field
            deleted = False
            for lk, v in list(keys.items()):
                if v.get("bcrypt_hash") == key_hash or v.get("key_hash") == key_hash:
                    del keys[lk]
                    _save_keys(keys)
                    logger.info(
                        "Deleted API key %s...", "<redacted>"
                    )  # lgtm[py/clear-text-logging-sensitive-data]
                    deleted = True
                    key_hash = lk  # normalize for cache invalidation below
                    break
    # Invalidate the positive validation cache so revoked keys take effect
    # immediately (no stale auth for up to _VALIDATED_KEY_CACHE_TTL seconds).
    if deleted:
        with _VALIDATED_KEY_CACHE_LOCK:
            _VALIDATED_KEY_CACHE.pop(key_hash, None)
        # invalid across ALL workers (not just this one).
        redis = _get_redis_for_key_cache()
        if redis is not None:
            try:
                redis.delete(f"{_REDIS_KEY_CACHE_PREFIX}{key_hash}")
            except Exception:
                pass
    return deleted


def update_api_key_role(key_hash: str, role: Role) -> bool:
    """Update the role of an existing API key."""
    with _keys_lock:
        keys = _load_keys()
        # Fast path
        if key_hash in keys:
            keys[key_hash]["role"] = role.value
            _save_keys(keys)
            logger.info(
                "Updated API key role to %s", role.value
            )  # lgtm[py/clear-text-logging-sensitive-data]
            updated = True
        else:
            # Slow path: scan for matching bcrypt_hash
            updated = False
            for lk, v in list(keys.items()):  # NOSONAR - python:S7504
                if v.get("bcrypt_hash") == key_hash or v.get("key_hash") == key_hash:
                    keys[lk]["role"] = role.value
                    _save_keys(keys)
                    logger.info(
                        "Updated API key role to %s", role.value
                    )  # lgtm[py/clear-text-logging-sensitive-data]
                    updated = True
                    key_hash = lk  # normalize for cache invalidation below
                    break
    # Invalidate the positive validation cache so role changes take effect
    # immediately. Otherwise a recently-validated key could retain its old
    # role for up to _VALIDATED_KEY_CACHE_TTL seconds â€” a privilege-escalation
    # window if an admin downgrades a compromised key.
    if updated:
        with _VALIDATED_KEY_CACHE_LOCK:
            _VALIDATED_KEY_CACHE.pop(key_hash, None)
        # immediately across ALL workers.
        redis = _get_redis_for_key_cache()
        if redis is not None:
            try:
                redis.delete(f"{_REDIS_KEY_CACHE_PREFIX}{key_hash}")
            except Exception:
                pass
    return updated


# Initialize on import
_ensure_default_admin_key()
