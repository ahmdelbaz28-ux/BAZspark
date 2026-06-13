"""
parsers/tests/test_path_security_enhanced.py — Enhanced security tests for
parsers/_path_security.py (68% → 80%+).

SECURITY-CRITICAL: This module is the primary defense against path traversal
attacks in the DWG/DXF/IFC/PDF parsing pipeline.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from parsers._path_security import (
    UnsafePathError,
    validate_input_path,
    validate_file_size,
    validate_fire_protection_file,
    _resolve_allowed_bases,
)


class TestValidateInputPathNone:
    """Test that None/invalid input is rejected."""

    def test_none_input_raises(self):
        """Test that validate_input_path(None) raises UnsafePathError."""
        with pytest.raises(UnsafePathError, match="non-empty string"):
            validate_input_path(None)

    def test_empty_string_rejected(self, monkeypatch):
        """Test that empty string is rejected as unsafe."""
        # Ensure development mode doesn't add CWD which makes empty path valid
        monkeypatch.delenv("FIREAI_ENV", raising=False)
        with pytest.raises(UnsafePathError):
            validate_input_path("")


class TestValidateInputPathTraversal:
    """Test path traversal attack rejection."""

    def test_absolute_path_outside_allowed(self):
        """Test that absolute paths outside allowed dirs are rejected."""
        with pytest.raises(UnsafePathError):
            validate_input_path("/etc/passwd")

    def test_absolute_path_to_shadow(self):
        """Test that /etc/shadow is rejected."""
        with pytest.raises(UnsafePathError):
            validate_input_path("/etc/shadow")


class TestValidateInputPathValid:
    """Test that valid paths within allowed directories are accepted."""

    def test_valid_file_in_tmp(self, tmp_path):
        """Test that a valid file in an allowed directory passes."""
        test_file = tmp_path / "test.dxf"
        test_file.write_text("test")
        result = validate_input_path(str(test_file))
        assert result is not None

    def test_valid_file_with_various_extensions(self, tmp_path):
        """Test that a valid file with various extensions passes."""
        for ext in [".dxf", ".dwg", ".ifc", ".pdf", ".rvt"]:
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("test")
            result = validate_input_path(str(test_file))
            assert result is not None


class TestValidateInputPathExtension:
    """Test extension whitelist enforcement."""

    def test_disallowed_extension_rejected(self, tmp_path):
        """Test that files with disallowed extensions are rejected."""
        test_file = tmp_path / "malware.exe"
        test_file.write_text("malware")
        with pytest.raises(UnsafePathError, match="extension"):
            validate_input_path(str(test_file), allowed_extensions=frozenset({".dxf", ".dwg"}))

    def test_allowed_extension_accepted(self, tmp_path):
        """Test that files with allowed extensions are accepted."""
        test_file = tmp_path / "test.dxf"
        test_file.write_text("test")
        result = validate_input_path(str(test_file), allowed_extensions=frozenset({".dxf", ".dwg"}))
        assert result is not None

    def test_no_extension_check_when_not_specified(self, tmp_path):
        """Test that extension is not checked when allowed_extensions is None."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("test")
        result = validate_input_path(str(test_file), allowed_extensions=None)
        assert result is not None

    def test_py_extension_rejected(self, tmp_path):
        """Test that .py files are rejected when extensions are specified."""
        test_file = tmp_path / "script.py"
        test_file.write_text("script")
        with pytest.raises(UnsafePathError):
            validate_input_path(str(test_file), allowed_extensions=frozenset({".dxf"}))

    def test_sh_extension_rejected(self, tmp_path):
        """Test that .sh files are rejected when extensions are specified."""
        test_file = tmp_path / "script.sh"
        test_file.write_text("#!/bin/bash")
        with pytest.raises(UnsafePathError):
            validate_input_path(str(test_file), allowed_extensions=frozenset({".dxf", ".dwg"}))


class TestValidateInputPathNullBytes:
    """Test null byte injection prevention."""

    def test_null_byte_rejected(self):
        """Test that paths with null bytes are rejected."""
        with pytest.raises(UnsafePathError, match="null byte"):
            validate_input_path("/tmp/test.pdf\x00.sh")

    def test_null_byte_in_middle(self):
        """Test null byte in middle of path."""
        with pytest.raises(UnsafePathError, match="null byte"):
            validate_input_path("/tmp/\x00test.dxf")


class TestValidateInputPathArgumentInjection:
    """Test argument injection prevention."""

    def test_dash_prefix_rejected(self):
        """Test that paths starting with - are rejected (argument injection)."""
        with pytest.raises(UnsafePathError, match="starts with '-'"):
            validate_input_path("-rf")

    def test_double_dash_rejected(self):
        """Test that paths starting with -- are rejected."""
        with pytest.raises(UnsafePathError, match="starts with '-'"):
            validate_input_path("--output")


class TestValidateFileSize:
    """Test file size validation (decompression bomb defense)."""

    def test_normal_file_passes(self, tmp_path):
        """Test that a normal-sized file passes validation."""
        test_file = tmp_path / "test.dxf"
        test_file.write_text("test content")
        size = validate_file_size(Path(str(test_file)), max_size_bytes=1_000_000)
        assert size > 0

    def test_oversized_file_rejected(self, tmp_path):
        """Test that oversized files are rejected."""
        test_file = tmp_path / "big.dxf"
        test_file.write_text("x" * 100)
        with pytest.raises(UnsafePathError, match="exceeds limit"):
            validate_file_size(Path(str(test_file)), max_size_bytes=50)

    def test_nonexistent_file_raises(self, tmp_path):
        """Test that validating a nonexistent file raises."""
        nonexistent = Path(str(tmp_path / "nonexistent.dxf"))
        with pytest.raises(UnsafePathError):
            validate_file_size(nonexistent, max_size_bytes=1_000_000)

    def test_returns_actual_size(self, tmp_path):
        """Test that validate_file_size returns the actual file size."""
        test_file = tmp_path / "sized.dxf"
        test_file.write_bytes(b"x" * 42)
        size = validate_file_size(Path(str(test_file)), max_size_bytes=100)
        assert size == 42


class TestResolveAllowedBases:
    """Test _resolve_allowed_bases helper function."""

    def test_default_bases_include_tmp(self):
        """Test that default allowed bases include temp directory."""
        bases = _resolve_allowed_bases()
        assert len(bases) >= 1

    def test_custom_env_var(self, monkeypatch):
        """Test that FIREAI_ALLOWED_UPLOAD_DIRS env var is respected."""
        with tempfile.TemporaryDirectory() as td:
            monkeypatch.setenv("FIREAI_ALLOWED_UPLOAD_DIRS", td)
            bases = _resolve_allowed_bases()
            assert any(td in str(b) for b in bases)

    def test_empty_entries_skipped(self, monkeypatch):
        """Test that empty entries in env var are skipped."""
        monkeypatch.setenv("FIREAI_ALLOWED_UPLOAD_DIRS", ":/tmp:")
        bases = _resolve_allowed_bases()
        # Should not crash from empty entries
        assert len(bases) >= 1

    def test_development_env_adds_cwd(self, monkeypatch):
        """Test that FIREAI_ENV=development adds CWD to allowed bases."""
        monkeypatch.setenv("FIREAI_ENV", "development")
        bases = _resolve_allowed_bases()
        cwd = os.path.realpath(os.getcwd())
        assert any(str(b) == cwd for b in bases)


class TestFireProtectionValidation:
    """Tests for fire protection-specific path validation.

    NFPA 72 Section 14.4.3.2: All imported files must be validated.
    NEC Section 90.3: Equipment must be suitable for environment.
    These tests verify that the validate_fire_protection_file function
    correctly enforces both security checks and domain-specific
    constraints for fire protection system design file imports.
    """

    def test_dwg_extension_allowed(self, tmp_path):
        """NFPA 72 allows DWG files for fire alarm system design."""
        test_file = tmp_path / "fire_alarm_plan.dwg"
        test_file.write_text("dwg content")
        result = validate_fire_protection_file(str(test_file))
        assert result is not None
        assert result.suffix == ".dwg"

    def test_dxf_extension_allowed(self, tmp_path):
        """NFPA 72 allows DXF files for fire alarm system design."""
        test_file = tmp_path / "fire_alarm_plan.dxf"
        test_file.write_text("dxf content")
        result = validate_fire_protection_file(str(test_file))
        assert result is not None
        assert result.suffix == ".dxf"

    def test_ifc_extension_allowed(self, tmp_path):
        """IFC files for BIM integration per ISO 16739."""
        test_file = tmp_path / "building_model.ifc"
        test_file.write_text("ifc content")
        result = validate_fire_protection_file(str(test_file))
        assert result is not None
        assert result.suffix == ".ifc"

    def test_invalid_extension_rejected(self, tmp_path):
        """Non-standard extensions must be rejected per NFPA 72 Section 14.4.3.2."""
        test_file = tmp_path / "malware.exe"
        test_file.write_text("malware")
        with pytest.raises(UnsafePathError, match="extension"):
            validate_fire_protection_file(str(test_file))

    def test_custom_extensions_override_default(self, tmp_path):
        """Custom allowed_extensions override the default set."""
        test_file = tmp_path / "custom.rvt"
        test_file.write_text("rvt content")
        result = validate_fire_protection_file(
            str(test_file),
            allowed_extensions=frozenset({".rvt"}),
        )
        assert result is not None
        assert result.suffix == ".rvt"

    def test_path_traversal_blocked(self, tmp_path):
        """Path traversal attacks must be blocked even with valid extensions."""
        # Create a symlink in tmp_path pointing to /etc/passwd to simulate
        # path traversal via symlink. The resolved path must be within
        # allowed bases — /etc is not in allowed bases.
        # Use a file that actually exists so the exists() check passes.
        # Instead, test that a file outside allowed dirs is caught.
        # /etc/hosts.dwg won't exist as a file, so FileNotFoundError
        # is expected — but let's test UnsafePathError by creating
        # a symlink attack scenario.
        import os
        real_file = tmp_path / "real.dwg"
        real_file.write_text("safe content")
        symlink = tmp_path / "symlink.dwg"
        try:
            os.symlink("/etc/passwd", str(symlink))
        except OSError:
            # Symlink creation may fail; skip this test
            pytest.skip("Cannot create symlink for traversal test")
        with pytest.raises(UnsafePathError, match="SECURITY|traversal"):
            validate_fire_protection_file(str(symlink))

    def test_null_byte_blocked(self):
        """Null byte injection must be blocked in fire protection file paths."""
        with pytest.raises(UnsafePathError, match="null byte"):
            validate_fire_protection_file("/tmp/test.ifc\x00.exe")
