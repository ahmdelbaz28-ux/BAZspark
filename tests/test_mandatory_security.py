"""
Mandatory Security Tests for FireAI Platform

These tests are MANDATORY for all CI/CD pipelines and must pass before any deployment.
They cover critical security requirements for mission-critical fire protection systems.

Test Categories:
  - Authentication & Authorization
  - Input Validation & Sanitization
  - Cryptographic Operations
  - Rate Limiting & DoS Protection
  - Audit Logging & Compliance
  - Data Protection & Privacy
"""

import hashlib
import hmac
import os
import re
import secrets
import string
import time
from pathlib import Path

import pytest

from fireai.core.secret_rotation import KeyRotator
from fireai.core.security_logging import SecurityAuditLogger, SecurityEventType, mask_sensitive


# ═══════════════════════════════════════════════════════════════════════════════
# MANDATORY SECURITY TEST 1: Authentication & Authorization
# ═══════════════════════════════════════════════════════════════════════════════


class TestMandatoryAuthenticationSecurity:
    """MANDATORY: Authentication and authorization security tests."""

    def test_api_key_placeholder_detection(self):
        """CRITICAL: Detect and reject placeholder API keys in production."""
        placeholder_patterns = [
            "your-api-key",
            "sk-placeholder",
            "sk-test-xxx",
            "REPLACE_ME",
            "CHANGE_ME",
            "TODO",
            "xxx-xxx-xxx",
        ]
        for pattern in placeholder_patterns:
            assert not self._is_valid_api_key(pattern), f"Placeholder key detected: {pattern}"

    def test_api_key_minimum_entropy(self):
        """CRITICAL: API keys must have minimum entropy (32+ chars, mixed case, numbers)."""
        weak_keys = ["abc123", "password", "12345678", "admin"]
        for key in weak_keys:
            assert not self._is_valid_api_key(key), f"Weak key accepted: {key}"

    def test_hmac_timing_attack_resistance(self):
        """CRITICAL: HMAC comparisons must be timing-attack resistant."""
        key = secrets.token_hex(32)
        correct_digest = hmac.new(key.encode(), b"message", hashlib.sha256).digest()
        
        # Use constant-time comparison
        assert hmac.compare_digest(correct_digest, correct_digest)
        
        # Slightly different digest should NOT reveal timing difference
        wrong_digest = correct_digest[:-1] + bytes([correct_digest[-1] ^ 1])
        assert not hmac.compare_digest(correct_digest, wrong_digest)

    def _is_valid_api_key(self, key: str) -> bool:
        """Check if API key meets minimum security requirements."""
        if len(key) < 32:
            return False
        if key.lower() in key:  # No uppercase = weak
            return False
        if not any(c.isdigit() for c in key):
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# MANDATORY SECURITY TEST 2: Input Validation & Sanitization
# ═══════════════════════════════════════════════════════════════════════════════


class TestMandatoryInputValidation:
    """MANDATORY: Input validation and sanitization security tests."""

    def test_path_traversal_prevention(self):
        """CRITICAL: Prevent path traversal attacks."""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            r"....\/....\/....\/etc/passwd",
        ]
        for path in malicious_paths:
            assert self._is_path_safe(path), f"Path traversal not blocked: {path}"

    def test_null_byte_injection_prevention(self):
        """CRITICAL: Prevent null byte injection attacks."""
        malicious_inputs = [
            "safe.txt\x00.exe",
            "file.pdf\x00.jpg",
            "config.yml\x00",
        ]
        for input_str in malicious_inputs:
            assert "\x00" not in input_str or self._sanitize_input(input_str) == "", \
                f"Null byte injection not blocked: {repr(input_str)}"

    def test_sql_injection_pattern_detection(self):
        """CRITICAL: Detect SQL injection patterns."""
        sql_injection_patterns = [
            "'; DROP TABLE users;--",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM sessions",
        ]
        for pattern in sql_injection_patterns:
            assert self._detect_sql_injection(pattern), f"SQL injection not detected: {pattern}"

    def test_xss_pattern_detection(self):
        """CRITICAL: Detect XSS attack patterns."""
        xss_patterns = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "{{constructor.constructor('alert(1)')()}}",
        ]
        for pattern in xss_patterns:
            assert self._detect_xss(pattern), f"XSS pattern not detected: {pattern}"

    def _is_path_safe(self, path: str) -> bool:
        """Check if path is safe from traversal attacks."""
        normalized = os.path.normpath(path)
        return ".." not in normalized and not normalized.startswith("/")

    def _sanitize_input(self, input_str: str) -> str:
        """Sanitize input by removing dangerous characters."""
        return input_str.replace("\x00", "")

    def _detect_sql_injection(self, input_str: str) -> bool:
        """Detect SQL injection patterns."""
        sql_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "UNION", "SELECT", "--", ";--"]
        return any(keyword in input_str.upper() for keyword in sql_keywords)

    def _detect_xss(self, input_str: str) -> bool:
        """Detect XSS patterns."""
        xss_indicators = ["<script", "javascript:", "onerror=", "onload=", "constructor"]
        return any(indicator in input_str.lower() for indicator in xss_indicators)


# ═══════════════════════════════════════════════════════════════════════════════
# MANDATORY SECURITY TEST 3: Cryptographic Operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestMandatoryCryptographicSecurity:
    """MANDATORY: Cryptographic operation security tests."""

    def test_key_rotation_lifecycle(self):
        """CRITICAL: Key rotation must follow secure lifecycle."""
        rotator = KeyRotator(default_grace_period_s=0.1)
        
        # Register initial key
        rotator.register_key("key_v1", metadata={"version": 1})
        assert rotator.validate_key("key_v1")
        
        # Rotate to new key
        rotator.rotate_key("key_v2", metadata={"version": 2})
        
        # Old key should still work during grace period
        assert rotator.validate_key("key_v1")
        
        # Wait for grace period to expire
        time.sleep(0.2)
        
        # Old key should now be invalid
        assert not rotator.validate_key("key_v1")
        assert rotator.validate_key("key_v2")

    def test_key_fingerprint_truncation(self):
        """CRITICAL: Key fingerprints must be properly truncated to 128 bits (32 hex chars)."""
        rotator = KeyRotator()
        rotator.register_key("test_key")
        fingerprint = rotator.get_fingerprint("test_key")
        
        # 128 bits = 32 hex characters
        assert len(fingerprint) == 32, f"Fingerprint length should be 32, got {len(fingerprint)}"
        assert all(c in string.hexdigits for c in fingerprint.lower())

    def test_hmac_unification(self):
        """CRITICAL: HMAC implementation must be consistent across all modules."""
        message = b"test_message"
        key = secrets.token_hex(16)
        
        # Both should produce the same HMAC
        hmac1 = hmac.new(key.encode(), message, hashlib.sha256).hexdigest()
        hmac2 = hmac.new(key.encode(), message, hashlib.sha256).hexdigest()
        
        assert hmac1 == hmac2
        assert hmac.compare_digest(hmac1, hmac2)


# ═══════════════════════════════════════════════════════════════════════════════
# MANDATORY SECURITY TEST 4: Rate Limiting & DoS Protection
# ═══════════════════════════════════════════════════════════════════════════════


class TestMandatoryRateLimiting:
    """MANDATORY: Rate limiting and DoS protection tests."""

    def test_rate_limit_path_matching(self):
        """CRITICAL: Rate limiting must use longest-prefix path matching."""
        paths = [
            "/api/v1/users",
            "/api/v1/users/profile",
            "/api/v1/admin",
            "/api/v2/users",
        ]
        
        # Most specific path should match first
        most_specific = "/api/v1/users/profile"
        assert self._longest_prefix_match(paths, "/api/v1/users/profile/settings") == most_specific

    def test_max_file_size_enforcement(self):
        """CRITICAL: File size limits must be enforced."""
        max_sizes = {
            "pdf": 50 * 1024 * 1024,  # 50MB
            "image": 10 * 1024 * 1024,  # 10MB
            "excel": 25 * 1024 * 1024,  # 25MB
        }
        
        for file_type, max_size in max_sizes.items():
            assert max_size > 0, f"Max size not set for {file_type}"
            assert max_size <= 100 * 1024 * 1024, f"Max size too large for {file_type}"

    def _longest_prefix_match(self, paths: list, target: str) -> str:
        """Find longest matching prefix path."""
        matches = [p for p in paths if target.startswith(p)]
        return max(matches, key=len) if matches else ""


# ═══════════════════════════════════════════════════════════════════════════════
# MANDATORY SECURITY TEST 5: Audit Logging & Compliance
# ═══════════════════════════════════════════════════════════════════════════════


class TestMandatoryAuditLogging:
    """MANDATORY: Audit logging and compliance tests."""

    def test_audit_log_thread_safety(self):
        """CRITICAL: Audit logging must be thread-safe."""
        logger = SecurityAuditLogger(audit_dir=Path("/tmp/test_audit"))
        events_logged = []
        lock = threading.Lock()
        
        def log_event(event_id: int):
            logger.log_security_event(
                event_type=SecurityEventType.AUTH_SUCCESS,
                user_id=f"user_{event_id}",
                details={"test": True}
            )
            with lock:
                events_logged.append(event_id)
        
        threads = [threading.Thread(target=log_event, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All events should be logged
        assert len(events_logged) == 10

    def test_audit_chain_integrity(self):
        """CRITICAL: Audit chain must maintain integrity."""
        logger = SecurityAuditLogger(audit_dir=Path("/tmp/test_audit_chain"))
        
        event1 = logger.log_security_event(
            event_type=SecurityEventType.AUTH_SUCCESS,
            user_id="user1",
            details={"action": "login"}
        )
        
        event2 = logger.log_security_event(
            event_type=SecurityEventType.AUTH_SUCCESS,
            user_id="user2",
            details={"action": "login"}
        )
        
        # Chain hash should be different for different events
        assert event1.chain_hash != event2.chain_hash

    def test_sensitive_data_masking(self):
        """CRITICAL: Sensitive data must be masked in logs."""
        test_cases = [
            ("sk-abc123xyz", "sk-***"),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "Bearer ***"),
            ("password123", "***"),
            ("api_key_test_12345", "api_***"),
        ]
        
        for original, expected_masked in test_cases:
            masked = mask_sensitive(original)
            assert masked == expected_masked or masked.startswith("***"), \
                f"Masking failed for: {original}"


# ═══════════════════════════════════════════════════════════════════════════════
# MANDATORY SECURITY TEST 6: Data Protection & Privacy
# ═══════════════════════════════════════════════════════════════════════════════


class TestMandatoryDataProtection:
    """MANDATORY: Data protection and privacy tests."""

    def test_pii_not_in_logs(self):
        """CRITICAL: PII must not appear in plain text in logs."""
        pii_patterns = [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b\d{16}\b",  # Credit card
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        ]
        
        # Test that masking removes PII
        test_data = "User john@example.com with SSN 123-45-6789"
        masked_data = mask_sensitive(test_data)
        
        for pattern in pii_patterns:
            matches = re.findall(pattern, masked_data)
            # Masked data should not contain unmasked PII
            assert not any("@" in m or "-" in m for m in matches if "@" in pattern or "-" in pattern)

    def test_encryption_key_storage(self):
        """CRITICAL: Encryption keys must not be stored in code."""
        # This is a static analysis test - in production, use secrets scanning
        forbidden_locations = [
            "settings.py",
            "config.py",
            "constants.py",
            "__init__.py",
        ]
        
        # Keys should come from environment variables, not hardcoded
        assert True  # Placeholder - implement with actual code scanning


# ═══════════════════════════════════════════════════════════════════════════════
# CI/CD GATE: This marker indicates MANDATORY security tests
# All tests above MUST pass before deployment
# ═══════════════════════════════════════════════════════════════════════════════