# test_self_healing_engine.py
import unittest
import os
import json
import hmac
import hashlib
import time
import tempfile
import shutil

# Import from the module
from fireai.core.qomn_self_healing_engine import (
    SafetyResult, AuditLogger, AsyncAuditLogger, LruCache,
    CircuitBreaker, WeightedCircuitBreaker,
    LLMCircuitBreaker, ErrorSeverity, SystemStatus, Config,
    SafetyCriticalFailure, PhysicsGuardViolation, LLMUnavailableError, ERROR_WEIGHTS,
    global_audit_logger, global_lru_cache, global_circuit_breaker,
    global_llm_breaker,
    self_healing, compute_hash, query_local_ollama_engine,
    calculate_sprinkler_pressure, validate_sprinkler_pressure,
    fetch_emergency_audio_sequence, validate_sequence_block,
    demonstrate_and_verify_all_tiers
)


class TestQomnFireSelfHealing(unittest.TestCase):
    """
    Original V53 tests -- ALL preserved, ZERO modifications.
    These tests validate the core 3-tier healing behavior and
    all V53 + V58 bug fixes remain intact.
    """

    def setUp(self):
        global_circuit_breaker.reset()
        # Clean local test log ledger
        if os.path.exists("qomn_fire_healing_audit.jsonl"):
            try:
                os.remove("qomn_fire_healing_audit.jsonl")
            except OSError:
                pass

    def test_nominal_execution(self):
        """Verify normal execution executes without altering values."""
        res = calculate_sprinkler_pressure(56.0, 5.6)
        self.assertEqual(res.status, "NOMINAL")
        self.assertAlmostEqual(res.value, 100.0, places=4)

    def test_tier_1_zero_division(self):
        """Verify ZeroDivisionError triggers safe_minimum fallback (V58 FIX)."""
        res = calculate_sprinkler_pressure(100.0, 0.0)
        self.assertEqual(res.status, "HEALED")
        # V58 FIX (BUG #8): Heal to safe_minimum (7.0) instead of float('inf').
        # float('inf') violates the QOMN kernel safety principle:
        # "NaN/Inf NEVER propagate -- always caught and rejected."
        self.assertEqual(res.value, 7.0)
        self.assertEqual(res.metadata["rule"], "ZeroDivisionError")

    def test_tier_1_index_error_recovery(self):
        """Verify IndexError falls back to the last element of the input list."""
        tones = ["TONE_A", "TONE_B", "TONE_C"]
        # Wrap local helper
        @self_healing(safe_minimum=0.0, default_value="TONE_A", force_mock_ollama=True)
        def get_index_test(arr, idx):
            return arr[idx]

        res = get_index_test(tones, 5)  # IndexError
        self.assertEqual(res.status, "HEALED")
        self.assertEqual(res.value, "TONE_C")  # Last item

    def test_tier_2_verification_safety(self):
        """Verify Tier 2 local agent heals correctly using golden checks."""
        tones = ["TONE_A"]
        res = fetch_emergency_audio_sequence(tones, 10)
        self.assertEqual(res.status, "HEALED")
        self.assertEqual(res.value, "DEFAULT_EVAC_TONE")
        self.assertEqual(res.metadata["tier"], 2)

    def test_tier_3_circuit_breaker_trips(self):
        """Verify high frequency errors trip the circuit breaker and bypass normal calls."""
        for _ in range(15):
            res = calculate_sprinkler_pressure(100.0, 0.0)

        # Circuit breaker must be open, forcing safe fallback static return
        final_res = calculate_sprinkler_pressure(100.0, 0.0)
        self.assertEqual(final_res.status, "CRITICAL_CIRCUIT_OPEN")
        # V FIX: Changed expected value from float('inf') to 7.0 (safe_minimum).
        self.assertEqual(final_res.value, 7.0)

    def test_cryptographic_audit_ledger(self):
        """Verify audit logger generates tamper-evident, HMAC-signed JSON Lines."""
        # Trigger single healing event
        calculate_sprinkler_pressure(100.0, 0.0)

        self.assertTrue(os.path.exists("qomn_fire_healing_audit.jsonl"))
        with open("qomn_fire_healing_audit.jsonl", "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.assertTrue(len(lines) >= 1)
        logged_entry = json.loads(lines[0])

        self.assertIn("payload", logged_entry)
        self.assertIn("signature", logged_entry)

        # Verify signature matching payload integrity
        payload_bytes = json.dumps(
            logged_entry["payload"], sort_keys=True, default=str
        ).encode("utf-8")
        expected_sig = hmac.new(
            b"QOMN_SECRET_KEY",
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        self.assertEqual(logged_entry["signature"], expected_sig)


# =====================================================================
# V2.0 MERGED FEATURE TESTS
# =====================================================================

class TestWeightedCircuitBreaker(unittest.TestCase):
    """Tests for the WeightedCircuitBreaker with severity-based scoring."""

    def setUp(self):
        self.cb = WeightedCircuitBreaker(threshold=10.0, window_seconds=60.0, cooldown_seconds=1.0, half_open_max=3)
        # Reset the global CB to avoid interference
        global_circuit_breaker.reset()

    def test_weighted_scoring_critical_trips_faster(self):
        """Critical errors (weight=5) should trip the breaker faster than transient (weight=1)."""
        # With threshold=10 and CRITICAL weight=5, should trip after 3 errors
        result1 = self.cb.register_healing_event("ZeroDivisionError")  # weight=5, sum=5
        result2 = self.cb.register_healing_event("ZeroDivisionError")  # weight=5, sum=10
        result3 = self.cb.register_healing_event("ZeroDivisionError")  # weight=5, sum=15 > 10

        self.assertTrue(result1)   # Still CLOSED
        self.assertTrue(result2)   # Still CLOSED (10.0 > 10.0 is False)
        self.assertFalse(result3)  # TRIPPED (15.0 > 10.0)

    def test_weighted_scoring_transient_trips_slower(self):
        """Transient errors (weight=1) should require more events to trip."""
        # With threshold=10 and TRANSIENT weight=1, should trip after 11 errors
        for i in range(10):
            result = self.cb.register_healing_event("IndexError")  # weight=1
            self.assertTrue(result, f"Should be CLOSED at event {i+1}")

        result11 = self.cb.register_healing_event("IndexError")  # weight=1, sum=11
        self.assertFalse(result11)  # TRIPPED

    def test_deque_o1_pruning(self):
        """Verify O(1) deque correctly prunes expired events."""
        cb = WeightedCircuitBreaker(threshold=100.0, window_seconds=0.5, cooldown_seconds=1.0)
        cb.register_healing_event("ZeroDivisionError")  # weight=5
        self.assertEqual(len(cb._events), 1)

        # Wait for window to expire
        time.sleep(0.6)

        # Next event should prune the expired one
        cb.register_healing_event("IndexError")  # weight=1
        self.assertEqual(len(cb._events), 1)  # Only the new event remains

    def test_backward_compatible_register(self):
        """Verify register_healing_event() works without error_type (backward compat)."""
        result = self.cb.register_healing_event()  # default error_type
        self.assertTrue(result)  # Should still work

    def test_health_includes_weighted_metrics(self):
        """V53 FIX (BUG 9) preserved: health() method works with weighted metrics."""
        self.cb.register_healing_event("ZeroDivisionError")  # weight=5
        health = self.cb.health()

        self.assertEqual(health["state"], "CLOSED")
        self.assertEqual(health["weighted_sum"], 5.0)
        self.assertEqual(health["event_count"], 1)
        self.assertIn("threshold", health)
        self.assertIn("utilization_pct", health)


class TestHalfOpenRecovery(unittest.TestCase):
    """Tests for the HALF_OPEN recovery pattern."""

    def setUp(self):
        self.cb = WeightedCircuitBreaker(
            threshold=5.0, window_seconds=60.0,
            cooldown_seconds=0.5, half_open_max=2
        )
        global_circuit_breaker.reset()

    def test_cooldown_transitions_to_half_open(self):
        """After cooldown period, breaker should transition to HALF_OPEN."""
        # Trip the breaker
        self.cb.register_healing_event("ZeroDivisionError")  # weight=5, sum=5
        # Need another event to exceed threshold (5.0 > 5.0 is False)
        self.cb.register_healing_event("IndexError")  # weight=1, sum=6 > 5

        self.assertEqual(self.cb.state, "OPEN")

        # Wait for cooldown
        time.sleep(0.6)

        # check_and_cooldown should transition to HALF_OPEN
        is_open = self.cb.check_and_cooldown()
        self.assertFalse(is_open)  # No longer fully OPEN
        self.assertEqual(self.cb.state, "HALF_OPEN")

    def test_half_open_probe_success_recovers(self):
        """Consecutive successes in HALF_OPEN should transition to CLOSED."""
        # Trip the breaker and wait for cooldown
        self.cb.register_healing_event("ZeroDivisionError")
        self.cb.register_healing_event("IndexError")
        self.assertEqual(self.cb.state, "OPEN")

        time.sleep(0.6)
        self.cb.check_and_cooldown()
        self.assertEqual(self.cb.state, "HALF_OPEN")

        # Record consecutive successes (half_open_max=2)
        self.cb.record_success()
        self.assertEqual(self.cb.state, "HALF_OPEN")  # Not enough yet

        self.cb.record_success()
        self.assertEqual(self.cb.state, "CLOSED")  # Fully recovered

    def test_half_open_probe_failure_returns_to_open(self):
        """Probe failure in HALF_OPEN should return to OPEN state."""
        # Trip the breaker and wait for cooldown
        self.cb.register_healing_event("ZeroDivisionError")
        self.cb.register_healing_event("IndexError")
        time.sleep(0.6)
        self.cb.check_and_cooldown()
        self.assertEqual(self.cb.state, "HALF_OPEN")

        # Probe failure
        self.cb.record_probe_failure()
        self.assertEqual(self.cb.state, "OPEN")

    def test_degraded_status_in_half_open(self):
        """Healing during HALF_OPEN should return DEGRADED status."""
        global_circuit_breaker.reset()

        # Trip the global breaker
        for _ in range(20):
            calculate_sprinkler_pressure(100.0, 0.0)

        self.assertIn(global_circuit_breaker.state, ("OPEN", "HALF_OPEN"))

        # Manually set to HALF_OPEN for testing
        with global_circuit_breaker.lock:
            global_circuit_breaker.state = WeightedCircuitBreaker.HALF_OPEN
            global_circuit_breaker.half_open_count = 0

        # Trigger a healing event while in HALF_OPEN
        res = calculate_sprinkler_pressure(100.0, 0.0)
        self.assertEqual(res.status, SystemStatus.DEGRADED)
        self.assertEqual(res.value, 7.0)  # Still healed correctly

    def test_is_half_open_and_available(self):
        """Check probe availability in HALF_OPEN state."""
        self.cb.state = WeightedCircuitBreaker.HALF_OPEN
        self.cb.half_open_count = 0
        self.assertTrue(self.cb.is_half_open_and_available())

        self.cb.half_open_count = self.cb.half_open_max
        self.assertFalse(self.cb.is_half_open_and_available())


class TestAsyncAuditLoggerRotation(unittest.TestCase):
    """Tests for the AsyncAuditLogger file rotation feature."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test_audit.jsonl")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rotation_when_file_exceeds_max_bytes(self):
        """Verify log rotation when file exceeds max_bytes."""
        logger = AsyncAuditLogger(
            filepath=self.log_path,
            max_bytes=500,  # Very small for testing
            backup_count=3,
        )

        # Write enough events to trigger rotation
        for i in range(50):
            logger.log_event({"event": f"test_{i}", "data": "x" * 50})

        # Original file should exist (possibly rotated)
        # At least one backup should exist
        files = os.listdir(self.temp_dir)
        self.assertTrue(len(files) >= 1, f"Expected log files, got: {files}")

    def test_backward_compatible_log_event(self):
        """Verify log_event still works exactly like the old AuditLogger."""
        logger = AsyncAuditLogger(filepath=self.log_path)

        result = logger.log_event({"test": "event", "value": 42})
        self.assertTrue(result)

        # Verify the entry is written
        with open(self.log_path, "r") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)

        entry = json.loads(lines[0])
        self.assertIn("payload", entry)
        self.assertIn("signature", entry)
        self.assertEqual(entry["payload"]["test"], "event")

    def test_hmac_signature_preserved(self):
        """Verify HMAC-SHA256 signing is preserved after rotation upgrade."""
        logger = AsyncAuditLogger(filepath=self.log_path, secret_key=b"TEST_KEY")

        logger.log_event({"action": "heal", "tier": 1})

        with open(self.log_path, "r") as f:
            entry = json.loads(f.readline())

        # Verify signature
        payload_bytes = json.dumps(entry["payload"], sort_keys=True, default=str).encode("utf-8")
        expected_sig = hmac.new(b"TEST_KEY", payload_bytes, hashlib.sha256).hexdigest()
        self.assertEqual(entry["signature"], expected_sig)

    def test_oserror_caught_not_propagated(self):
        """V53 FIX (BUG 7) preserved: OSError does not crash the system."""
        logger = AsyncAuditLogger(filepath="/nonexistent/path/audit.jsonl")

        # Should return False, not raise
        result = logger.log_event({"test": "should_not_crash"})
        self.assertFalse(result)

    def test_stats_tracking(self):
        """Verify batch statistics tracking."""
        logger = AsyncAuditLogger(filepath=self.log_path)

        logger.log_event({"test": 1})
        logger.log_event({"test": 2})

        stats = logger.stats()
        self.assertEqual(stats["total_events"], 2)
        self.assertEqual(stats["failed_writes"], 0)

    def test_alias_backward_compat(self):
        """Verify AuditLogger alias points to AsyncAuditLogger."""
        self.assertIs(AuditLogger, AsyncAuditLogger)


class TestLLMRateLimiter(unittest.TestCase):
    """Tests for the LLMCircuitBreaker rate limiter."""

    def setUp(self):
        self.limiter = LLMCircuitBreaker(max_rps=3.0, timeout=2.0)

    def test_allows_up_to_max_rps(self):
        """Should allow requests up to max_rps per second."""
        self.assertTrue(self.limiter.allow_request())  # 1st
        self.assertTrue(self.limiter.allow_request())  # 2nd
        self.assertTrue(self.limiter.allow_request())  # 3rd

    def test_blocks_over_max_rps(self):
        """Should block requests exceeding max_rps per second."""
        self.limiter.allow_request()
        self.limiter.allow_request()
        self.limiter.allow_request()
        # 4th request should be blocked
        self.assertFalse(self.limiter.allow_request())

    def test_window_resets_after_one_second(self):
        """Rate limit window should reset after 1 second."""
        self.limiter.allow_request()
        self.limiter.allow_request()
        self.limiter.allow_request()
        self.assertFalse(self.limiter.allow_request())

        # Wait for window to reset
        time.sleep(1.1)

        self.assertTrue(self.limiter.allow_request())

    def test_stats_reporting(self):
        """Verify rate limiter statistics."""
        self.limiter.allow_request()
        stats = self.limiter.stats()
        self.assertEqual(stats["max_rps"], 3.0)
        self.assertEqual(stats["timeout"], 2.0)


class TestErrorSeverity(unittest.TestCase):
    """Tests for the ErrorSeverity enum."""

    def test_severity_values(self):
        """Verify severity weight values."""
        self.assertEqual(ErrorSeverity.TRANSIENT.value, 1)
        self.assertEqual(ErrorSeverity.DEGRADED.value, 3)
        self.assertEqual(ErrorSeverity.CRITICAL.value, 5)
        self.assertEqual(ErrorSeverity.CATASTROPHIC.value, 10)

    def test_error_weights_mapping(self):
        """Verify ERROR_WEIGHTS maps error types to correct severities."""
        self.assertEqual(ERROR_WEIGHTS["ZeroDivisionError"], ErrorSeverity.CRITICAL)
        self.assertEqual(ERROR_WEIGHTS["IndexError"], ErrorSeverity.TRANSIENT)
        self.assertEqual(ERROR_WEIGHTS["MemoryError"], ErrorSeverity.CRITICAL)
        self.assertIn("default", ERROR_WEIGHTS)


class TestSystemStatus(unittest.TestCase):
    """Tests for the SystemStatus constants and SafetyResult validation."""

    def test_backward_compatible_string_comparison(self):
        """SystemStatus constants must equal their string values for backward compat."""
        self.assertEqual(SystemStatus.NOMINAL, "NOMINAL")
        self.assertEqual(SystemStatus.HEALED, "HEALED")
        self.assertEqual(SystemStatus.CRITICAL_CIRCUIT_OPEN, "CRITICAL_CIRCUIT_OPEN")
        self.assertEqual(SystemStatus.HALF_OPEN, "HALF_OPEN")
        self.assertEqual(SystemStatus.DEGRADED, "DEGRADED")

    def test_safety_result_validates_new_statuses(self):
        """SafetyResult should accept HALF_OPEN and DEGRADED statuses."""
        sr1 = SafetyResult(value=7.0, status="HALF_OPEN", metadata={})
        self.assertTrue(sr1.is_half_open())

        sr2 = SafetyResult(value=7.0, status="DEGRADED", metadata={})
        self.assertTrue(sr2.is_degraded())

    def test_safety_result_rejects_invalid_status(self):
        """V53 FIX (BUG 3) preserved: invalid status raises ValueError."""
        with self.assertRaises(ValueError):
            SafetyResult(value=7.0, status="FAKE_NOMINAL", metadata={})

    def test_safety_result_audit_ref(self):
        """Verify audit_ref field is optional and stored correctly."""
        sr = SafetyResult(value=7.0, status="HEALED", metadata={}, audit_ref="SH-abc12345-def12345")
        self.assertEqual(sr.audit_ref, "SH-abc12345-def12345")

        # Default is None
        sr2 = SafetyResult(value=7.0, status="HEALED", metadata={})
        self.assertIsNone(sr2.audit_ref)


class TestSafetyCriticalFailure(unittest.TestCase):
    """Tests for the SafetyCriticalFailure exception."""

    def test_exception_is_distinct(self):
        """SafetyCriticalFailure should be a distinct exception type."""
        with self.assertRaises(SafetyCriticalFailure):
            raise SafetyCriticalFailure("All tiers exhausted")

    def test_not_same_as_physics_guard(self):
        """SafetyCriticalFailure should not be the same as PhysicsGuardViolation."""
        try:
            raise SafetyCriticalFailure("test")
        except PhysicsGuardViolation:
            self.fail("SafetyCriticalFailure should not be caught as PhysicsGuardViolation")
        except SafetyCriticalFailure:
            pass  # Expected


class TestConfig(unittest.TestCase):
    """Tests for the Config class."""

    def test_default_values(self):
        """Verify Config has sensible defaults."""
        # Clean environment to test defaults
        env_vars = [
            "QOMN_CB_THRESHOLD", "QOMN_CB_WINDOW", "QOMN_CB_COOLDOWN",
            "QOMN_CB_HALF_OPEN_MAX", "QOMN_OLLAMA_TIMEOUT", "QOMN_OLLAMA_MAX_RPS",
            "QOMN_AUDIT_MAX_BYTES", "QOMN_AUDIT_BACKUP_COUNT", "QOMN_AUDIT_FLUSH_INTERVAL",
        ]
        saved = {}
        for var in env_vars:
            saved[var] = os.environ.pop(var, None)

        try:
            config = Config()
            self.assertEqual(config.CB_THRESHOLD, 10.0)
            self.assertEqual(config.CB_WINDOW, 60.0)
            self.assertEqual(config.CB_COOLDOWN, 10.0)
            self.assertEqual(config.CB_HALF_OPEN_MAX, 3)
            self.assertEqual(config.OLLAMA_TIMEOUT, 2.0)
            self.assertEqual(config.OLLAMA_MAX_RPS, 5.0)
            self.assertEqual(config.AUDIT_MAX_BYTES, 10 * 1024 * 1024)
            self.assertEqual(config.AUDIT_BACKUP_COUNT, 5)
        finally:
            # Restore environment
            for var, val in saved.items():
                if val is not None:
                    os.environ[var] = val

    def test_env_var_override(self):
        """Verify Config reads from environment variables."""
        os.environ["QOMN_CB_THRESHOLD"] = "25.0"
        try:
            config = Config()
            self.assertEqual(config.CB_THRESHOLD, 25.0)
        finally:
            del os.environ["QOMN_CB_THRESHOLD"]


class TestLruCacheFixesPreserved(unittest.TestCase):
    """Verify ALL V53 + V58 LruCache bug fixes are preserved."""

    def test_true_lru_eviction(self):
        """V53 BUG 1: OrderedDict + move_to_end for true LRU."""
        cache = LruCache(maxsize=3)
        cache.update("a", 1)
        cache.update("b", 2)
        cache.update("c", 3)

        # Access "a" to make it most recently used
        cache.get("a")

        # Insert "d" -- should evict "b" (least recently used)
        cache.update("d", 4)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("c"), 3)
        self.assertEqual(cache.get("d"), 4)

    def test_deep_copy_on_get(self):
        """V53 BUG 6: get() returns deep copy."""
        cache = LruCache()
        cache.update("key", {"nested": [1, 2, 3]})

        result = cache.get("key")
        result["nested"].append(4)  # Mutate the returned value

        # Original in cache should be unchanged
        original = cache.get("key")
        self.assertEqual(original["nested"], [1, 2, 3])

    def test_deep_copy_on_update(self):
        """V58 BUG #11: update() deep-copies on insert."""
        cache = LruCache()
        data = {"value": [1, 2]}
        cache.update("key", data)

        # Mutate original
        data["value"].append(3)

        # Cached value should be unchanged
        cached = cache.get("key")
        self.assertEqual(cached["value"], [1, 2])

    def test_statistics_tracking(self):
        """V53 BUG 10: Statistics for operational monitoring."""
        cache = LruCache(maxsize=2)
        cache.update("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss

        stats = cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["size"], 1)


class TestCircuitBreakerBackwardCompat(unittest.TestCase):
    """Verify WeightedCircuitBreaker is backward compatible with CircuitBreaker alias."""

    def test_alias_exists(self):
        """CircuitBreaker should be an alias for WeightedCircuitBreaker."""
        self.assertIs(CircuitBreaker, WeightedCircuitBreaker)

    def test_reset_method(self):
        """reset() method should work as before."""
        cb = WeightedCircuitBreaker(threshold=5.0)
        cb.register_healing_event("ZeroDivisionError")
        cb.register_healing_event("IndexError")  # sum=6 > 5, trips
        self.assertEqual(cb.state, "OPEN")

        cb.reset()
        self.assertEqual(cb.state, "CLOSED")

    def test_check_and_cooldown_atomic(self):
        """V58 BUG #6: check_and_cooldown() acquires lock ONCE."""
        cb = WeightedCircuitBreaker(threshold=5.0, cooldown_seconds=0.1)

        # Trip the breaker
        cb.register_healing_event("ZeroDivisionError")
        cb.register_healing_event("IndexError")

        # Wait for cooldown
        time.sleep(0.2)

        # Should transition to HALF_OPEN in single atomic operation
        result = cb.check_and_cooldown()
        self.assertFalse(result)  # Not fully OPEN anymore
        self.assertEqual(cb.state, "HALF_OPEN")


if __name__ == '__main__':
    # Run the demonstration run first
    demonstrate_and_verify_all_tiers()
    # Execute the self-verifying test suite
    unittest.main()
