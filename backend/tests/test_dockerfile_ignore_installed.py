# ═══════════════════════════════════════════════════════════════════════════
# test_dockerfile_ignore_installed.py — V279 regression tests guarding the
# Dockerfile `--ignore-installed` flag on the Python requirements install step.
#
# BACKGROUND (production incident, 2026-08-03):
#   The HuggingFace Space crashed at runtime with
#   `ModuleNotFoundError: No module named 'packaging'` (slowapi -> limits.util
#   imports packaging at module load). Root cause:
#     * The multi-stage Dockerfile installs deps into a SEPARATE prefix:
#         pip install --prefix=/install -r requirements.txt
#     * The builder stage first runs `pip install setuptools==70.3.0 wheel`,
#       which pulls `packaging` into the BUILDER's base site-packages.
#     * pip's `--prefix` install then sees packaging as "already satisfied" in
#       the base env and SKIPS installing it into /install.
#     * The runtime stage is a FRESH python:3.14-slim image (no packaging) and
#       only receives `COPY --from=python-builder /install /usr/local` — so
#       packaging is missing at runtime.
#   FIX: `--ignore-installed` forces pip to install EVERY dependency (including
#   transitive `packaging`) into the /install prefix.
#
# These tests statically guard the Dockerfile (fast, no Docker daemon required)
# so the flag, the prefix target, the runtime COPY, and the packaging pin cannot
# silently regress. They run in BOTH the CI Build Gate (`pytest backend/tests/`)
# and the CI/CD Pipeline Gate 2 (`pytest tests/ backend/tests/`).
#
# Run: pytest backend/tests/test_dockerfile_ignore_installed.py -v
# ═══════════════════════════════════════════════════════════════════════════

"""Guard the Dockerfile `--ignore-installed` requirements-install behavior."""

from __future__ import annotations

import importlib.util
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"
REQUIREMENTS = REPO_ROOT / "requirements.txt"


@pytest.fixture(scope="module")
def dockerfile_lines() -> list[str]:
    """Return the Dockerfile as a list of lines (skips module if file absent)."""
    if not DOCKERFILE.exists():
        pytest.skip(f"{DOCKERFILE} not found — Dockerfile not present in this checkout")
    return DOCKERFILE.read_text(encoding="utf-8").splitlines()


@pytest.fixture(scope="module")
def requirements_text() -> str:
    """Return requirements.txt contents (skips module if file absent)."""
    if not REQUIREMENTS.exists():
        pytest.skip(f"{REQUIREMENTS} not found — requirements.txt not present")
    return REQUIREMENTS.read_text(encoding="utf-8")


def _requirements_install_lines(dockerfile_lines: list[str]) -> list[str]:
    """Return the RUN lines that install requirements.txt."""
    return [
        line.strip()
        for line in dockerfile_lines
        if line.strip().startswith("RUN pip install") and "-r requirements.txt" in line
    ]


# ── 1. The requirements install must use --ignore-installed ─────────────────


def test_requirements_install_uses_ignore_installed(dockerfile_lines: list[str]) -> None:
    """The requirements pip install MUST carry --ignore-installed (V279 fix).

    Without this flag, pip skips installing `packaging` into the /install prefix
    when the builder's base env already satisfies the pin (via the setuptools
    bootstrap), which breaks the runtime stage with ModuleNotFoundError.
    """
    req_lines = _requirements_install_lines(dockerfile_lines)
    assert req_lines, (
        "Dockerfile has no `RUN pip install ... -r requirements.txt` line — "
        "the python-builder stage is missing its dependency install."
    )
    assert any("--ignore-installed" in line for line in req_lines), (
        "Dockerfile requirements install MUST use `--ignore-installed` so transitive "
        "deps like packaging (already satisfied in the builder base env via the "
        "setuptools bootstrap) are still copied into the /install prefix. "
        "See commit 0b330576 / V279."
    )


def test_requirements_install_targets_install_prefix(dockerfile_lines: list[str]) -> None:
    """The requirements install must target the /install prefix."""
    req_lines = _requirements_install_lines(dockerfile_lines)
    assert req_lines, "No `RUN pip install ... -r requirements.txt` line found."
    assert any("--prefix=/install" in line for line in req_lines), (
        "Dockerfile requirements install must use `--prefix=/install` so the runtime "
        "stage can COPY the isolated dependency tree."
    )


def test_ignore_installed_on_requirements_line_not_bootstrap(dockerfile_lines: list[str]) -> None:
    """`--ignore-installed` must be on the REQUIREMENTS line specifically.

    A future edit that adds the flag only to the setuptools bootstrap line would
    NOT fix the packaging gap — the guard must be on the `-r requirements.txt`
    install itself. This test pins the flag to the correct line.
    """
    req_lines = _requirements_install_lines(dockerfile_lines)
    assert req_lines, "No `RUN pip install ... -r requirements.txt` line found."
    assert all("--ignore-installed" in line for line in req_lines), (
        "`--ignore-installed` must be on EVERY `-r requirements.txt` line (V279), "
        "not just elsewhere in the Dockerfile. Lines: " + repr(req_lines)
    )


# ── 2. The runtime stage must COPY the /install prefix ───────────────────────


def test_runtime_stage_copies_builder_install(dockerfile_lines: list[str]) -> None:
    """The runtime stage must copy /install from the python-builder stage.

    The whole point of the isolated prefix + --ignore-installed is that the
    runtime stage receives a COMPLETE dependency tree via this COPY. If a future
    refactor removes it, packaging (and everything else) disappears at runtime.
    """
    joined = "\n".join(dockerfile_lines)
    assert "COPY --from=python-builder /install /usr/local" in joined, (
        "Dockerfile runtime stage MUST copy the python-builder /install prefix "
        "(`COPY --from=python-builder /install /usr/local`)."
    )


# ── 3. requirements.txt must keep packaging pinned ──────────────────────────


def test_requirements_pins_packaging(requirements_text: str) -> None:
    """requirements.txt must pin `packaging` explicitly (V278/V279).

    packaging is a transitive dep (matplotlib/slowapi->limits) that is NOT
    guaranteed in the runtime stage otherwise. A dependabot/cleanup that drops
    the pin would reintroduce the ModuleNotFoundError.
    """
    assert re.search(r"^packaging>=.*$", requirements_text, re.MULTILINE), (
        "requirements.txt MUST pin `packaging>=...` (V278 fix) so the runtime "
        "stage reliably imports it via slowapi -> limits."
    )


# ── 4. Functional proof: pip + --ignore-installed populates the prefix ───────


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skipif(
    importlib.util.find_spec("pip") is None,
    reason="pip module not available for sys.executable -m pip invocation",
)
def test_pip_ignore_installed_forces_packaging_into_prefix() -> None:
    """Prove the mechanism: --ignore-installed lands packaging in a --prefix.

    Simulates the Dockerfile python-builder stage with the real pip: installs
    `packaging` into a fresh temp prefix with `--ignore-installed` and asserts
    the package is physically present under that prefix. Requires network to
    fetch the wheel; skipped gracefully when unavailable.
    """
    prefix = pathlib.Path(tempfile.mkdtemp(prefix="pip-prefix-"))
    try:
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-q",
                    "--disable-pip-version-check",
                    "--only-binary",
                    ":all:",
                    "--ignore-installed",
                    "--prefix",
                    str(prefix),
                    "packaging",
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            pytest.skip(f"pip install unavailable in this env ({exc!r}) — static guards still enforced")

        found = any(
            child.name == "packaging" and child.is_dir()
            for child in prefix.rglob("*")
        )
        assert found, (
            "`--ignore-installed` must physically install packaging under the "
            "--prefix target even when it is already present in the invoking env."
        )
    finally:
        shutil.rmtree(prefix, ignore_errors=True)
