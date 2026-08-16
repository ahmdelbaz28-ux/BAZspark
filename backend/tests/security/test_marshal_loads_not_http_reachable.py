"""Phase 5 — Strict verification of the M-1 (marshal.loads) claim.

CLAIM UNDER TEST (from worklog.md, Phase 3 verdict):
  "M-1: marshal.loads in isolation.py — defense-in-depth concern
   (not CRITICAL, not exposed via HTTP)"

METHODOLOGY:
  The user demanded: "apply the same strict methodology to M-1 — write a
  test that PROVES the current claim is accurate before accepting it."

  A claim of "not exposed via HTTP" is only verifiable by attempting to
  REACH the dangerous code path via HTTP and proving it cannot be reached.
  Static reasoning alone ("I read the code, it looks fine") is the exact
  evasion the user is rejecting.

  This file therefore writes MULTIPLE independent tests, each of which
  MUST pass for the claim to stand. If ANY test fails, the claim was
  false.

  Test 1 (static import graph — DIRECT):
      Walks every .py file under backend/. Asserts NONE of them imports
      facp_distributed, facp_distributed.security.isolation, or marshal.

  Test 1b (static import graph — TRANSITIVE):
      Extends Test 1. Walks the transitive import closure from backend/
      through every top-level repo package (fireai/, parsers/,
      facp_system/, core/, marine/). Asserts NONE of them imports
      facp_distributed. This catches the case where backend/ doesn't
      import facp_distributed directly, but transitively reaches it
      through fireai/.

  Test 1c (dynamic dispatch — STATIC SCAN):
      Walks every non-test .py file in the repo. Asserts NONE of them
      uses dynamic dispatch patterns that could reach marshal or
      facp_distributed at runtime:
        - __import__("marshal")
        - __import__("facp_distributed...")
        - importlib.import_module("marshal")
        - importlib.import_module("facp_distributed...")
      This defends against future regressions where someone tries to
      bypass the static import check via dynamic dispatch.

  Test 2 (static call graph):
      Walks every .py file in the repository. Asserts the ONLY call
      sites of create_sandboxed_execution() and execute_in_sandbox()
      are inside isolation.py itself (i.e., the dangerous path is dead
      code that no caller actually invokes).

  Test 3 (runtime reachability via HTTP):
      Patches marshal.loads and marshal.dumps with sentinels that record
      every call. Spins up the FastAPI TestClient. Hits EVERY route the
      app exposes. Asserts the sentinels were NEVER invoked from
      production code paths.

  Test 3b (runtime reachability — COVERAGE MEASUREMENT):
      Measures what fraction of routes actually executed their handler
      code (2xx or 5xx response). Asserts a minimum coverage threshold.
      If too few handlers ran, Test 3 is vacuously passing for the
      majority of the surface — the claim has NOT been verified.

  Test 4 (claim-text regression guard):
      Asserts the exact M-1 claim text exists verbatim in worklog.md.
      This prevents a future "fix" from quietly downgrading the severity
      (e.g., changing "not exposed via HTTP" to "exposed but mitigated")
      without updating the test.

  Test 5 (sanity check):
      Confirms marshal.dumps would fire if the sandbox path were ever
      invoked. Proves the M-1 concern is REAL, not just hypothetical.

  Test 6 (meta-test — DIRECT call detection):
      Constructs a tiny FastAPI app with a route that DIRECTLY calls
      marshal.loads. Verifies the sentinel fires and correctly attributes
      the call. If this fails, Test 3 is broken for direct violations.

  Test 7 (meta-test — TRANSITIVE call detection):
      Constructs a tiny FastAPI app with a route that calls
      ExecutionIsolationManager.create_sandboxed_execution() (which
      internally calls marshal.dumps). Verifies the sentinel fires and
      records the call from isolation.py. If this fails, Test 3 is
      broken for transitive violations through isolation.py — meaning
      a future router that wires up the sandbox would NOT be caught.

EVALUATION:
  - All tests PASS → claim verified, accept M-1 as MEDIUM.
  - Any test FAILS → claim was false; either escalate to CRITICAL
                     and patch the hole, or rewrite the worklog
                     claim to match reality.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── Paths ───────────────────────────────────────────────────────────────────
# __file__ = .../BAZspark/backend/tests/security/test_marshal_loads_not_http_reachable.py
# parents[0] = backend/tests/security
# parents[1] = backend/tests
# parents[2] = backend
# parents[3] = BAZspark  ← repository root
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
ISOLATION_PY = REPO_ROOT / "facp_distributed" / "security" / "isolation.py"
WORKLOG = REPO_ROOT / "worklog.md"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _iter_python_files(root: Path):
    """Yield every .py file under root, skipping common noise directories."""
    skip_dirs = {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "site-packages",
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            if fname.endswith(".py"):
                yield Path(dirpath) / fname


def _imports_any(ast_root: ast.AST, *targets: str) -> bool:
    """Return True if the module's AST imports any of the given module paths.

    Handles both `import X` and `from X import ...` forms, including
    dotted imports like `from facp_distributed.security import isolation`.
    """
    for node in ast.walk(ast_root):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == t or alias.name.startswith(t + ".") for t in targets):
                    return True
        elif isinstance(node, ast.ImportFrom):
            # node.module is None for relative imports like `from . import x`
            mod = node.module or ""
            # Resolve relative imports: a single leading dot in a backend/*
            # file cannot refer to facp_distributed (different top-level
            # package). We only flag absolute imports of the target names.
            if node.level == 0:
                if any(mod == t or mod.startswith(t + ".") for t in targets):
                    return True
    return False


def _calls_any(ast_root: ast.AST, *method_names: str) -> list[str]:
    """Return a list of method-name calls in the AST that match any of the
    given method names. Used to find call sites like
    `.create_sandboxed_execution(...)` or `.execute_in_sandbox(...)`.
    """
    hits: list[str] = []
    for node in ast.walk(ast_root):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in method_names:
                hits.append(node.func.attr)
    return hits


def _find_dynamic_dispatch(ast_root: ast.AST, *targets: str) -> list[str]:
    """Return list of dynamic-dispatch patterns that could reach `targets`.

    Detects:
      - __import__("target")
      - __import__("target.submodule")
      - importlib.import_module("target")
      - importlib.import_module("target.submodule")

    Returns a list of human-readable descriptions of each finding.
    """
    findings: list[str] = []
    for node in ast.walk(ast_root):
        if not isinstance(node, ast.Call):
            continue
        # __import__("marshal") pattern
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            if node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    val = node.args[0].value
                    if any(val == t or val.startswith(t + ".") for t in targets):
                        findings.append(f"__import__({val!r}) at line {node.lineno}")
        # importlib.import_module("marshal") pattern
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "importlib":
                if node.args and isinstance(node.args[0], ast.Constant):
                    if isinstance(node.args[0].value, str):
                        val = node.args[0].value
                        if any(val == t or val.startswith(t + ".") for t in targets):
                            findings.append(
                                f"importlib.import_module({val!r}) at line {node.lineno}"
                            )
    return findings


def _get_transitive_top_level_imports(
    pkg_name: str, repo_root: Path, _seen: set | None = None
) -> set[str]:
    """Return the set of top-level packages transitively imported by pkg_name.

    Walks the package's __init__.py and all submodules (non-test) to build
    a closure of top-level package names. Used by Test 1b to detect
    transitive reach to facp_distributed.
    """
    if _seen is None:
        _seen = set()
    if pkg_name in _seen:
        return set()
    _seen.add(pkg_name)

    result: set[str] = set()
    pkg_path = repo_root / pkg_name
    if not pkg_path.is_dir():
        return result

    def harvest(filepath: Path):
        try:
            tree = ast.parse(filepath.read_text(encoding="utf-8"))
        except Exception:
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top != pkg_name:
                        result.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split(".")[0]
                    if top != pkg_name:
                        result.add(top)

    init_file = pkg_path / "__init__.py"
    if init_file.exists():
        harvest(init_file)

    skip_dirs = {"__pycache__", "tests", "test", ".pytest_cache"}
    for dirpath, dirnames, filenames in os.walk(pkg_path):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            if fname.endswith(".py") and not fname.startswith("test_") and fname != "conftest.py":
                harvest(Path(dirpath) / fname)

    # Recurse into repo-local top-level packages
    for sub in list(result):
        if (repo_root / sub).is_dir() and sub not in _seen:
            result.update(_get_transitive_top_level_imports(sub, repo_root, _seen))
    return result


# ─── Test 1: backend/ never imports facp_distributed or marshal ──────────────


def test_backend_never_imports_isolation_or_marshal():
    """STATIC IMPORT-GRAPH TEST (DIRECT).

    The M-1 claim says marshal.loads is "not exposed via HTTP". For that
    to be true, no HTTP-serving code (anything under backend/ EXCEPT
    backend/tests/, which is not HTTP-reachable) may import either:
      (a) facp_distributed (any submodule) — which transitively could
          reach isolation.py, or
      (b) marshal — which would itself be a new violation.

    If this test FAILS, the claim is FALSE: a backend module has grown
    a dependency on the dangerous code path. The worklog claim must be
    updated and the import must either be removed or the severity
    escalated.

    NOTE on scope: backend/tests/ is excluded because tests are NOT
    HTTP-reachable production code. Tests may legitimately import
    facp_distributed (e.g., to verify the dangerous path exists) without
    that constituting HTTP exposure. Test-only imports are verified by
    the runtime reachability test instead.

    NOTE: This test only catches DIRECT imports. See Test 1b for the
    transitive-closure check (e.g., backend → fireai → facp_distributed).
    """
    offenders: list[str] = []

    for py in _iter_python_files(BACKEND_DIR):
        # Exclude test files — they are not HTTP-reachable production code.
        parts = py.parts
        if "tests" in parts or py.name.startswith("test_"):
            continue
        # Also exclude conftest.py (test infrastructure, not production).
        if py.name == "conftest.py":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue  # skip files that don't parse
        if _imports_any(tree, "facp_distributed", "marshal"):
            offenders.append(str(py))

    # Backend code that merely MENTIONS the word "isolation" in comments
    # or string literals is fine — we only flag actual imports.
    assert not offenders, (
        "M-1 CLAIM IS FALSE: backend/ contains non-test files that import "
        "facp_distributed or marshal — these are HTTP-reachable import "
        "paths to the marshal.loads code in isolation.py. Offenders:\n  " + "\n  ".join(offenders)
    )


# ─── Test 1b: transitive import closure from backend/ ────────────────────────


def test_no_transitive_path_from_backend_to_facp_distributed():
    """STATIC IMPORT-GRAPH TEST (TRANSITIVE).

    Test 1 only checks DIRECT imports in backend/. But backend/ imports
    other top-level repo packages (fireai/, parsers/, facp_system/, etc.).
    If ANY of those transitively imports facp_distributed, then backend/
    reaches marshal.loads via HTTP — the claim is FALSE.

    This test walks the transitive closure starting from each top-level
    package imported by backend/, and asserts NONE of them reaches
    facp_distributed.

    If this test FAILS, the claim is FALSE: a code path from HTTP entry
    points transitively reaches facp_distributed. Either remove the
    transitive import or escalate the severity in the worklog.

    CONFIRMED REAL CONCERN:
      The user's strict self-critique exposed this gap. Test 1 alone
      gives false confidence — it could pass while a transitive chain
      silently smuggles facp_distributed into HTTP-reachable code.
    """
    # Step 1: Find all top-level repo packages imported by backend/
    repo_top_level_packages: set[str] = set()
    for pkg in ("fireai", "parsers", "facp_system", "core", "marine"):
        if (REPO_ROOT / pkg).is_dir():
            repo_top_level_packages.add(pkg)

    # Also discover any other top-level dirs that backend/ imports
    backend_imports: set[str] = set()
    for py in _iter_python_files(BACKEND_DIR):
        parts = py.parts
        if "tests" in parts or py.name.startswith("test_") or py.name == "conftest.py":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    backend_imports.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split(".")[0]
                    backend_imports.add(top)

    # Filter to packages that exist as directories in the repo
    transitively_reachable = {
        pkg for pkg in backend_imports if (REPO_ROOT / pkg).is_dir() and pkg != "backend"
    }

    # Step 2: For each such package, walk its transitive closure
    offenders: list[str] = []
    for pkg in sorted(transitively_reachable):
        closure = _get_transitive_top_level_imports(pkg, REPO_ROOT)
        if "facp_distributed" in closure:
            offenders.append(
                f"{pkg} → transitively reaches facp_distributed (closure size: {len(closure)})"
            )

    assert not offenders, (
        "M-1 CLAIM IS FALSE: backend/ imports a package that transitively "
        "reaches facp_distributed — meaning HTTP-reachable code can reach "
        "marshal.loads in isolation.py. Offenders:\n  " + "\n  ".join(offenders)
    )


# ─── Test 1c: dynamic dispatch scan (defends against future regressions) ─────


def test_no_dynamic_dispatch_to_marshal_or_facp_distributed():
    """STATIC SCAN FOR DYNAMIC DISPATCH PATTERNS.

    Tests 1 and 1b catch `import` statements (direct and transitive),
    but they don't catch runtime dynamic dispatch:
        __import__("marshal")
        importlib.import_module("facp_distributed.security.isolation")

    These patterns would bypass the static AST check. This test scans
    EVERY non-test .py file in the repo for such patterns targeting
    marshal or facp_distributed.

    If this test FAILS, someone has introduced a dynamic-dispatch import
    that bypasses the static checks. Either remove the dynamic import
    or escalate the severity.

    CURRENT STATE: I (the author) confirmed via grep that NO such patterns
    exist in the repo as of this writing. This test exists to defend
    against FUTURE regressions — it is a tripwire, not a discovery tool.
    """
    offenders: list[str] = []

    for py in _iter_python_files(REPO_ROOT):
        parts = py.parts
        # Skip test files — tests may legitimately use dynamic dispatch
        # to verify the dangerous path exists.
        if "tests" in parts or py.name.startswith("test_") or py.name == "conftest.py":
            continue
        # Skip isolation.py itself — it uses `import marshal` (static),
        # but if it ever switched to dynamic dispatch we'd want to know.
        # Actually we DO want to flag isolation.py if it uses dynamic
        # dispatch, because that would be a clear evasion. So don't skip.
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        hits = _find_dynamic_dispatch(tree, "marshal", "facp_distributed")
        if hits:
            offenders.append(f"{py}: {hits}")

    assert not offenders, (
        "M-1 CLAIM EVASION DETECTED: non-test files use dynamic dispatch "
        "to import marshal or facp_distributed. This bypasses the static "
        "import-graph checks (Tests 1 and 1b). Either remove the dynamic "
        "dispatch or escalate the severity. Offenders:\n  " + "\n  ".join(offenders)
    )


# ─── Test 2: dangerous methods are dead code (only self-calls) ───────────────


def test_dangerous_methods_are_only_called_within_isolation_py():
    """STATIC CALL-GRAPH TEST.

    isolation.py defines two methods whose invocation eventually reaches
    marshal.dumps()/loads():
      - ExecutionIsolationManager.create_sandboxed_execution
      - SandboxController.execute_in_sandbox

    If either is called from ANYWHERE ELSE in the repository, then the
    dangerous path is reachable. This test walks every .py file in the
    repo (excluding tests, which are allowed to verify the path exists
    but cannot themselves be the trigger for production traffic).

    Allowed call sites:
      - isolation.py itself (execute_in_sandbox → create_sandboxed_execution)
      - test files under any tests/ or */tests/ directory

    If this test FAILS, the claim is FALSE: a non-test module invokes
    the dangerous path. Either the caller must be removed or the
    severity must be escalated.
    """
    offenders: list[str] = []

    for py in _iter_python_files(REPO_ROOT):
        # Skip the isolation.py file itself — its internal self-call is fine.
        if py.resolve() == ISOLATION_PY.resolve():
            continue
        # Skip test files — tests are not HTTP-reachable production code.
        # We allow tests to exercise the dangerous path directly to
        # verify it works, but tests do not constitute "exposure via HTTP".
        parts = py.parts
        if "tests" in parts or "test_" in py.name:
            continue

        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue

        hits = _calls_any(tree, "create_sandboxed_execution", "execute_in_sandbox")
        if hits:
            offenders.append(f"{py}: calls {hits}")

    assert not offenders, (
        "M-1 CLAIM IS FALSE: non-test files invoke "
        "create_sandboxed_execution() or execute_in_sandbox() — these are "
        "the entry points to marshal.dumps/loads in isolation.py. The "
        "dangerous path is reachable from production code. Offenders:\n  " + "\n  ".join(offenders)
    )


# ─── Test 3: marshal.loads never fires during HTTP traffic ───────────────────


def _make_sentinel(
    raw_log: list, filtered_log: list, test_file_prefixes: tuple[str, ...], func_name: str
):
    """Create a sentinel that records every call to a patched function.

    The sentinel walks the call stack past app/mock/unittest internals
    so the recorded (filename, lineno) is the APPLICATION caller, not
    the patching machinery.

    IMPORTANT — importlib .pyc loading is excluded:
      CPython's importlib._bootstrap_external reads/writes on-disk .pyc
      bytecode caches via marshal.loads/dumps. Any LAZY import executed
      from a route handler (e.g. `from fireai.core.device_placement
      import ...` inside an endpoint function) therefore triggers
      marshal.loads from a <frozen importlib._bootstrap_external>
      frame, and — because frozen frames are skipped by the walker —
      the sentinel would otherwise record the APPLICATION IMPORT LINE
      as a "violation". Those calls are interpreter internals operating
      on the module's own trusted bytecode cache, NOT the isolation.py
      sandbox path the M-1 claim is about. We detect the importlib
      pyc-read/write path in the walked chain and ignore it. Real
      application-level marshal calls (the only thing Test 3 must
      catch) never have importlib frames between the sentinel and the
      recorded caller.

    Records into BOTH logs as tuples of (filename, lineno, func_name):
      - raw_log:     EVERY call, no filtering. Used by the meta-test
                     to prove the sentinel actually fires.
      - filtered_log: calls NOT from this test file or pytest internals.
                     Used by Test 3 to detect real HTTP-triggered
                     violations (calls from production code).

    Returns b'' so the patched function doesn't crash the caller — we
    WANT a loud failure via the assertion, not via an exception that
    some router might silently catch.
    """

    def _sentinel(*args, **kwargs):
        import inspect

        frame = inspect.currentframe().f_back
        skip_substrings = ("/marshal", "<frozen", "/mock", "/unittest")
        # True when the call chain passes through importlib's .pyc
        # read/write machinery (frozen or source form). See docstring
        # above — such calls are interpreter internals, not application
        # code paths, and must NOT be recorded as violations.
        via_importlib_pyc = False
        while frame is not None:
            fn = frame.f_code.co_filename
            fn_posix = fn.replace(os.sep, "/")
            if (
                "<frozen importlib" in fn_posix
                or "/importlib/_bootstrap" in fn_posix
                or fn_posix.endswith("/lib/importlib/_bootstrap.py")
            ):
                via_importlib_pyc = True
            if not any(s in fn_posix for s in skip_substrings):
                break
            frame = frame.f_back
        if frame is None or via_importlib_pyc:
            return b""
        if frame is not None:
            fn = frame.f_code.co_filename
            ln = frame.f_lineno
            entry = (fn, ln, func_name)
            raw_log.append(entry)
            fn_posix = fn.replace(os.sep, "/")
            if (
                not fn_posix.startswith(tuple(p.replace(os.sep, "/") for p in test_file_prefixes))
                and "/_pytest/" not in fn_posix
                and "/site-packages/pytest" not in fn_posix
                and "conftest" not in os.path.basename(fn)
                # V214 MERGE FIX: Exclude APM/tracing libraries (ddtrace, opentelemetry,
                # sentry) that legitimately use marshal internally for bytecode
                # instrumentation. These are NOT reachable from HTTP request
                # handlers — they wrap Python import machinery. Excluding them
                # avoids false positives in local dev environments where these
                # libraries are installed (CI does not install them).
                and "/ddtrace/" not in fn_posix
                and "/opentelemetry/" not in fn_posix
                and "/sentry_sdk/" not in fn_posix
            ):
                filtered_log.append(entry)
        return b""

    return _sentinel


def _get_app_routes(app) -> list[tuple[str, str]]:
    """Return a list of (method, path) for every route in the FastAPI app.

    Skips routes that don't have a path (e.g., mounted sub-apps without
    a path) and routes mounted on websockets (which would require a
    different test client).
    """
    routes: list[tuple[str, str]] = []
    for route in app.routes:
        # FastAPI/Starlette APIRoute has .methods and .path
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", None)
        if not path:
            continue
        # Skip websocket routes — they need a different client.
        if "websocket" in str(type(route)).lower():
            continue
        for method in sorted(methods):
            if method in ("HEAD", "OPTIONS"):
                continue  # auto-generated, skip
            routes.append((method, path))
    return routes


def _sanitize_path(method: str, path: str) -> str:
    """Replace path parameters like {project_id} with a placeholder value
    so the TestClient can actually hit the route."""
    # {project_id} → "00000000-0000-0000-0000-000000000000"
    # {device_id} → "1"
    # etc.
    import re

    sanitized = re.sub(r"\{[^}]+\}", "1", path)
    return sanitized


def _http_probe_routes(client, routes, raw_log, filtered_log):
    """Hit every route with placeholder payloads. Return a status distribution.

    Returns a dict mapping HTTP status code (or 'EXC: TypeName') to count.
    Used by Test 3 (asserts no marshal calls) and Test 3b (asserts minimum
    handler-execution coverage).
    """
    from collections import Counter

    status_counter: Counter = Counter()

    for method, path in routes:
        sanitized = _sanitize_path(method, path)
        try:
            if method == "GET":
                resp = client.get(sanitized)
            elif method == "POST":
                resp = client.post(sanitized, json={})
            elif method == "PUT":
                resp = client.put(sanitized, json={})
            elif method == "DELETE":
                resp = client.delete(sanitized)
            elif method == "PATCH":
                resp = client.patch(sanitized, json={})
            else:
                continue
            code = resp.status_code
            status_counter[code] += 1
        except Exception as e:
            status_counter[f"EXC: {type(e).__name__}"] += 1

    return status_counter


@pytest.mark.timeout(120)
def test_marshal_never_invoked_during_http_traffic():
    """RUNTIME REACHABILITY TEST.

    This is the killer test. Even if the static analysis is wrong (e.g.,
    a dynamic import we missed, a string-based getattr call, a metaclass
    trick), this test will catch it: we patch marshal.loads AND
    marshal.dumps with sentinels that record every invocation, then run
    the FastAPI TestClient through EVERY route the app exposes. If
    either sentinel fires from non-test code, the claim "not exposed via
    HTTP" is FALSE.

    Sentinel design:
      - We do NOT raise on call. Some routers may legitimately catch
        exceptions and continue, which would mask the failure. Instead
        we record every call site (filename:lineno) and assert the list
        is empty after the HTTP battery.
      - We DO filter out calls originating from this test file itself,
        from the conftest, or from pytest internals.
      - The sentinel walks UP the call stack past mock/unittest/marshal
        internals so the recorded call site is the APPLICATION code,
        not the patching machinery.

    If this test FAILS, the claim is FALSE: an HTTP request reached
    marshal.loads (or marshal.dumps). The call-site list will show
    exactly which file/line was responsible.

    NOTE: This test alone is INSUFFICIENT — it only proves no HTTP
    request CURRENTLY reaches marshal. See Test 3b for the coverage
    measurement that proves the test actually exercised a meaningful
    fraction of the surface area.
    """
    # Defer importing the app until the test runs — the conftest sets up
    # env vars that the app requires. If we import at module top, the
    # app fails to load in CI environments.
    try:
        from backend.app import app
    except Exception as e:
        pytest.skip(f"FastAPI app could not be imported in this environment: {e}")

    from fastapi.testclient import TestClient

    raw_log: list[tuple[str, int, str]] = []
    filtered_log: list[tuple[str, int, str]] = []
    test_file_prefixes = (
        str(Path(__file__).resolve()),  # this test
        str(BACKEND_DIR / "tests" / "conftest.py"),  # backend conftest
    )

    loads_sentinel = _make_sentinel(raw_log, filtered_log, test_file_prefixes, "loads")
    dumps_sentinel = _make_sentinel(raw_log, filtered_log, test_file_prefixes, "dumps")

    import marshal as _marshal_mod

    # We need to patch BOTH the module-level functions AND any module
    # that did `from marshal import loads` (which captured the original
    # reference at import time). Walk sys.modules and patch in place.
    original_loads = _marshal_mod.loads
    original_dumps = _marshal_mod.dumps

    # Track which modules we patched so we can restore them
    patched: list[tuple[str, str, object]] = []  # (mod_name, attr_name, original)

    def _patch_attr(mod_name: str, mod: object, attr: str, new_value):
        try:
            if hasattr(mod, attr) and getattr(mod, attr) is original_loads:
                setattr(mod, attr, new_value)
                patched.append((mod_name, attr, original_loads))
            elif hasattr(mod, attr) and getattr(mod, attr) is original_dumps:
                setattr(mod, attr, new_value)
                patched.append((mod_name, attr, original_dumps))
        except Exception:
            pass  # some modules don't allow attribute mutation

    # Patch marshal.loads and marshal.dumps at the source
    with (
        patch.object(_marshal_mod, "loads", side_effect=loads_sentinel) as _pl,
        patch.object(_marshal_mod, "dumps", side_effect=dumps_sentinel) as _pd,
    ):
        # Walk sys.modules to catch `from marshal import loads` patterns.
        # Note: we compare against original_loads/original_dumps (captured
        # BEFORE patching) because that's what modules would have
        # imported at their import time.
        for mod_name, mod in list(sys.modules.items()):
            if mod is None or mod is _marshal_mod:
                continue
            # Skip test modules to avoid noise
            if "test" in mod_name or "conftest" in mod_name:
                continue
            _patch_attr(mod_name, mod, "loads", _pl.side_effect)
            _patch_attr(mod_name, mod, "dumps", _pd.side_effect)

        try:
            client = TestClient(app)
            routes = _get_app_routes(app)

            # Defensive: if we somehow got zero routes, the test is broken.
            assert routes, (
                "No routes found in the FastAPI app — the runtime test "
                "cannot verify the M-1 claim. This is a test bug, not a "
                "claim failure."
            )

            _http_probe_routes(client, routes, raw_log, filtered_log)
        finally:
            # Restore patched module attributes
            for mod_name, attr, orig in patched:
                mod = sys.modules.get(mod_name)
                if mod is not None:
                    try:
                        setattr(mod, attr, orig)
                    except Exception:
                        pass

    # The filtered_log contains calls NOT from this test file or pytest
    # internals. Any entry here is a real HTTP-triggered violation.
    suspicious = list(filtered_log)

    assert not suspicious, (
        "M-1 CLAIM IS FALSE: marshal.loads or marshal.dumps was invoked "
        "while serving HTTP requests. The dangerous code path IS "
        "reachable via HTTP. Call sites:\n  "
        + "\n  ".join(f"{fn}:{ln} ({fn_name})" for fn, ln, fn_name in suspicious)
    )


# ─── Test 3b: measure handler-execution coverage ─────────────────────────────


@pytest.mark.timeout(45)
def test_http_probe_actually_exercises_handlers():
    """COVERAGE MEASUREMENT FOR TEST 3.

    Test 3 hits every route in the FastAPI app and asserts no route
    triggered marshal.loads/dumps. But if most routes return 4xx
    (validation errors, auth failures, etc.) BEFORE the handler runs,
    then Test 3 is vacuously passing — the handler code that could
    potentially call marshal.loads never executes.

    This test re-runs the same HTTP probe and measures what fraction of
    routes actually executed their handler (i.e., returned 2xx or 5xx).
    2xx = handler ran successfully. 5xx = handler ran but errored.
    4xx = handler likely never ran (auth/validation/not-found).

    If the handler-execution rate is too low, Test 3 cannot be trusted
    as verification of the M-1 claim. We assert a minimum threshold.

    CONFIRMED REAL CONCERN:
      In the initial strict audit (2026-07-28), the handler-execution
      rate was 35% (90/257 routes). 60% of routes returned 422 due to
      placeholder `{}` bodies failing Pydantic validation. Test 3 was
      technically passing but vacuously so for 60% of the surface.

      The fix is NOT to construct per-route valid payloads (impractical
      for 257 routes). Instead, we:
        (a) Document the coverage honestly in the assertion message
        (b) Fail if coverage drops below a sanity threshold (20%)
        (c) Recommend the user run additional ad-hoc tests for any
            route that handles untrusted binary input (e.g., file
            upload routes) — those are the highest-risk for marshal
            deserialization attacks.

    If this test FAILS, Test 3's PASS is meaningless — the runtime
    verification didn't actually exercise enough of the surface. Either
    add per-route fixtures to raise coverage, or document the gap as
    a known limitation in the worklog.
    """
    try:
        from backend.app import app
    except Exception as e:
        pytest.skip(f"FastAPI app could not be imported in this environment: {e}")

    from fastapi.testclient import TestClient

    client = TestClient(app)
    routes = _get_app_routes(app)
    assert routes, "No routes found — app did not load correctly"

    # Use the same probe as Test 3, but WITHOUT the sentinel patches
    # (we don't need them — we just want the status code distribution).
    status_counter = _http_probe_routes(client, routes, [], [])

    total = sum(status_counter.values())
    handler_ran = sum(
        c
        for k, c in status_counter.items()
        if isinstance(k, int) and (200 <= k < 300 or 500 <= k < 600)
    )
    handler_blocked = sum(
        c for k, c in status_counter.items() if isinstance(k, int) and (300 <= k < 500)
    )
    exceptions = sum(c for k, c in status_counter.items() if isinstance(k, str))

    coverage_pct = (handler_ran / total * 100) if total else 0

    # 20% is a deliberately low bar. The initial audit measured 35%.
    # If coverage drops below 20%, the test is too weak to verify the
    # M-1 claim — something has changed (e.g., more routes require
    # authentication, more routes have required body params) and the
    # placeholder payloads are no longer reaching enough handlers.
    MIN_COVERAGE_PCT = 20.0

    assert coverage_pct >= MIN_COVERAGE_PCT, (
        f"M-1 VERIFICATION TOO WEAK: only {coverage_pct:.1f}% of routes "
        f"({handler_ran}/{total}) actually executed their handler code. "
        f"Test 3 is vacuously passing for the other {handler_blocked} "
        f"routes that returned 4xx and the {exceptions} routes that "
        f"raised client-side exceptions. The M-1 claim has NOT been "
        f"verified for the majority of the HTTP surface. "
        f"Status distribution: {dict(status_counter)}"
    )


# ─── Test 4: the claim text exists verbatim in worklog.md ────────────────────


def test_m1_claim_text_exists_in_worklog():
    """CLAIM-TEXT REGRESSION GUARD.

    The M-1 claim is the worklog entry:
      "M-1: marshal.loads in isolation.py — defense-in-depth concern
       (not CRITICAL, not exposed via HTTP)"

    If a future "fix" rewrites this claim (e.g., to "exposed via HTTP
    but mitigated"), the severity has implicitly escalated and the
    claim is no longer accurate. This test forces the change to be
    made CONSCIOUSLY: if you rewrite the claim, you must also update
    this test, which forces you to think about whether the new claim
    is itself accurate.

    If this test FAILS, the worklog claim was edited. Either:
      (a) Restore the original wording (if the rewrite was an accident)
      (b) Update this test to assert the new wording AND escalate the
          severity in the worklog accordingly.
    """
    if not WORKLOG.exists():
        pytest.skip(f"Worklog not found at {WORKLOG}")

    worklog_text = WORKLOG.read_text(encoding="utf-8")

    # The exact substring from the Phase 3 verdict section.
    expected_substring = (
        "M-1: marshal.loads in isolation.py — defense-in-depth concern "
        "(not CRITICAL, not exposed via HTTP)"
    )

    assert expected_substring in worklog_text, (
        "M-1 claim text not found verbatim in worklog.md. The claim has "
        "been edited — either restore the original wording or update "
        "this test to match the new wording AND escalate the severity "
        "in the worklog if the new wording admits HTTP exposure."
    )


# ─── Bonus: verify the dangerous code path actually works (sanity check) ─────
# This isn't part of the claim verification per se, but it ensures that
# IF someone later wires up the sandbox path, it would actually fire
# marshal.loads — i.e., the danger is real, not theoretical. This makes
# the test suite self-documenting: the claim is meaningful because the
# dangerous code genuinely exists and works.


def test_marshal_loads_actually_fires_when_sandbox_is_invoked():
    """SANITY CHECK: confirm marshal.loads would fire if the sandbox path
    were ever invoked. This proves the M-1 concern is REAL (the dangerous
    code genuinely uses marshal.loads), not just a hypothetical.

    We invoke ExecutionIsolationManager.create_sandboxed_execution()
    directly in a subprocess-safe way, with marshal.loads patched to
    record. If the recording fires, the dangerous path is genuinely
    wired to marshal.loads.

    Note: the actual call spawns a subprocess that reads from a file,
    so the marshal.loads call happens in the CHILD process, not the
    parent. The parent calls marshal.dumps(). We therefore patch BOTH
    and verify at least one fires.

    We use a trivial function whose marshal.dumps is fast and whose
    subprocess execution is short. We don't care about the result —
    we care that marshal.dumps was invoked in the parent.
    """
    # Import lazily so this test doesn't pollute module collection.
    # If isolation.py is moved or renamed, this test would fail loudly,
    # which is also a useful signal.
    try:
        from facp_distributed.security.isolation import (
            ExecutionIsolationManager,
        )
    except ImportError as e:
        pytest.skip(f"facp_distributed not importable: {e}")

    call_log: list[str] = []
    import marshal as _marshal_mod

    original_dumps = _marshal_mod.dumps

    def _tracking_dumps(*args, **kwargs):
        call_log.append("dumps")
        return original_dumps(*args, **kwargs)

    manager = ExecutionIsolationManager()

    def trivial():
        return 42

    try:
        with patch.object(_marshal_mod, "dumps", side_effect=_tracking_dumps):
            # Use a very short timeout so the test doesn't hang.
            # The subprocess will start, run, and finish quickly.
            try:
                manager.create_sandboxed_execution(
                    trivial,
                    args=(),
                    kwargs=None,
                    timeout=2000,
                    max_memory_mb=64,
                )
            except Exception:
                # We don't care if the execution itself succeeds or
                # fails — we only care that marshal.dumps was invoked
                # in the parent process.
                pass

        assert "dumps" in call_log, (
            "marshal.dumps was NOT invoked when create_sandboxed_execution() "
            "was called. The dangerous code path may have been refactored "
            "away — which is good news, but means the M-1 claim is now "
            "moot and the worklog should be updated to reflect that."
        )
    finally:
        # Best-effort cleanup of the sandbox temp dir
        try:
            import shutil

            shutil.rmtree(manager.sandbox_base_path, ignore_errors=True)
        except Exception:
            pass


# ─── META-TEST 1: prove the runtime sentinel actually catches violations ────
# Without this test, Test 3 could be vacuously passing — the sentinel
# might never fire because of a bug in the patching logic, not because
# the claim is true. This meta-test deliberately constructs a FastAPI
# app with a route that calls marshal.loads, then verifies the sentinel
# fires. If this meta-test fails, Test 3 is broken and the M-1 claim
# has NOT been verified.


def test_runtime_sentinel_actually_catches_violations():
    """META-TEST 1 (DIRECT CALL): prove the runtime sentinel mechanism in
    Test 3 is capable of detecting a real, DIRECT violation.

    Constructs a tiny FastAPI app with a single route that calls
    `marshal.loads()` directly. Patches marshal.loads with the SAME
    sentinel mechanism used in Test 3. Hits the route. Asserts the
    sentinel fired and recorded the application code as the caller.

    If this test FAILS, Test 3 is vacuous for DIRECT violations — it
    cannot detect a real marshal.loads call from a route handler. The
    M-1 claim has NOT been verified. The sentinel mechanism must be
    fixed before Test 3's PASS can be trusted.
    """
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("FastAPI not available")

    # Construct a deliberately-violating app
    violation_app = FastAPI()

    @violation_app.get("/__deliberate_violation__")
    def deliberately_call_marshal_loads():
        import marshal

        # Marshal bytes for the integer 42
        marshal.loads(b"\xe9\x2a\x00\x00\x00")  # noqa: S301 — intentional for test
        return {"ok": True}

    # Set up the SAME sentinel mechanism as Test 3.
    # We use raw_log (which records EVERY call, including from this test
    # file) because the violating route is defined in this test file.
    # The filtered_log would discard these calls (correctly, for Test 3's
    # purposes), but for the meta-test we WANT to see them — that's how
    # we prove the sentinel actually fires.
    raw_log: list[tuple[str, int, str]] = []
    filtered_log: list[tuple[str, int, str]] = []
    test_file_prefixes = (
        str(Path(__file__).resolve()),
        str(BACKEND_DIR / "tests" / "conftest.py"),
    )
    loads_sentinel = _make_sentinel(raw_log, filtered_log, test_file_prefixes, "loads")

    import marshal as _marshal_mod

    with patch.object(_marshal_mod, "loads", side_effect=loads_sentinel):
        client = TestClient(violation_app)
        try:
            client.get("/__deliberate_violation__")
        except Exception:
            pass  # the sentinel returns b'' which may cause downstream errors

    # The raw_log MUST have at least one entry — this proves the sentinel
    # actually fires when an HTTP route calls marshal.loads.
    assert raw_log, (
        "META-TEST FAILURE: sentinel did NOT fire when an HTTP route "
        "called marshal.loads. This means Test 3 is vacuously passing — "
        "it cannot detect real violations. The M-1 claim has NOT been "
        "verified. Fix the sentinel mechanism in _make_sentinel() before "
        "trusting Test 3's result."
    )

    # The recorded call should be attributed to this test file (where
    # the violating route handler is defined). This proves the sentinel
    # correctly walks up the stack to find the application caller.
    recorded_filenames = [fn for fn, _ln, _name in raw_log]
    assert any(
        "test_marshal_loads_not_http_reachable" in fn or "<string>" in fn or "<module>" in fn
        for fn in recorded_filenames
    ), (
        f"META-TEST FAILURE: sentinel fired but recorded wrong call site. "
        f"Expected the deliberately-violating route (defined in this test) "
        f"to be recorded. Got: {raw_log}"
    )

    # Additionally: the filtered_log should be EMPTY here because the
    # violating route is in this test file (which the filter excludes).
    # This proves the filter is doing its job — in Test 3, calls from
    # production code would NOT be filtered, so they would appear in
    # filtered_log and cause Test 3 to fail.
    assert not filtered_log, (
        "META-TEST UNEXPECTED: filtered_log should be empty because the "
        "violating route is in this test file (which the filter excludes). "
        f"Got: {filtered_log}. This means the filter is broken — Test 3 "
        "may be silently swallowing real violations."
    )


# ─── META-TEST 2: prove the sentinel catches TRANSITIVE violations ──────────
# This is the test the user's strict self-critique demanded. Test 6 only
# proves DIRECT marshal.loads calls are caught. But the actual dangerous
# code path in isolation.py is:
#   route handler → create_sandboxed_execution() → marshal.dumps()
# The sentinel must walk UP the stack past isolation.py's frame to
# record the call. If the sentinel can't attribute calls coming from
# inside isolation.py, a future router that wires up the sandbox would
# NOT be caught — Test 3 would silently pass while the claim is false.


def test_runtime_sentinel_catches_transitive_violation_via_isolation():
    """META-TEST 2 (TRANSITIVE CALL): prove the runtime sentinel can
    detect a TRANSITIVE violation where the marshal.dumps call is made
    INSIDE facp_distributed.security.isolation (not directly by the
    route handler).

    Constructs a tiny FastAPI app with a route that calls
    ExecutionIsolationManager.create_sandboxed_execution(). This
    internally calls marshal.dumps() in the PARENT process. The
    sentinel must:
      (a) fire when marshal.dumps is called
      (b) walk up the stack past isolation.py's frame to record the
          call (so we know it came from production code, not just
          "isolation internals")

    If this test FAILS, Test 3 is vacuous for TRANSITIVE violations
    through isolation.py — exactly the kind of violation the M-1 claim
    is supposed to defend against. The claim has NOT been verified.

    CONFIRMED REAL CONCERN:
      Test 6 only proves the sentinel catches DIRECT marshal.loads
      calls from a route. The actual dangerous code path goes THROUGH
      isolation.py — the route calls create_sandboxed_execution(),
      which calls marshal.dumps(). If the sentinel fails to attribute
      this transitive call, a future regression that wires up the
      sandbox from a router would NOT be caught.

      The user's strict demand ("لا تتهاون" — don't be lenient)
      exposed this gap. Without Test 7, the test suite gives false
      confidence that the M-1 claim is verified.
    """
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("FastAPI not available")
    try:
        from facp_distributed.security.isolation import (
            ExecutionIsolationManager,
        )
    except ImportError as e:
        pytest.skip(f"facp_distributed not importable: {e}")

    # Construct a deliberately-violating app whose route calls
    # create_sandboxed_execution() — the dangerous path.
    violation_app = FastAPI()

    @violation_app.get("/__deliberate_transitive_violation__")
    def deliberately_invoke_sandbox():
        """Trigger the marshal.dumps code path indirectly.

        We use a trivial function whose marshal.dumps is fast. The
        execution itself may fail (subprocess issues, sandbox cleanup),
        but that doesn't matter — we only care that marshal.dumps was
        called in the parent process.
        """
        manager = ExecutionIsolationManager()

        def trivial():
            return 42

        try:
            manager.create_sandboxed_execution(
                trivial,
                args=(),
                kwargs=None,
                timeout=2000,
                max_memory_mb=64,
            )
        except Exception:
            pass  # we don't care if the sandbox runs successfully

        # Best-effort cleanup
        try:
            import shutil

            shutil.rmtree(manager.sandbox_base_path, ignore_errors=True)
        except Exception:
            pass

        return {"ok": True}

    # Set up the SAME sentinel mechanism as Test 3.
    raw_log: list[tuple[str, int, str]] = []
    filtered_log: list[tuple[str, int, str]] = []
    test_file_prefixes = (
        str(Path(__file__).resolve()),
        str(BACKEND_DIR / "tests" / "conftest.py"),
    )
    dumps_sentinel = _make_sentinel(raw_log, filtered_log, test_file_prefixes, "dumps")

    import marshal as _marshal_mod

    with patch.object(_marshal_mod, "dumps", side_effect=dumps_sentinel):
        client = TestClient(violation_app)
        try:
            client.get("/__deliberate_transitive_violation__")
        except Exception:
            pass  # we don't care about the response, only the sentinel log

    # The raw_log MUST have at least one entry — proving marshal.dumps
    # was called (transitively, via create_sandboxed_execution).
    assert raw_log, (
        "META-TEST 2 FAILURE: sentinel did NOT fire when a route "
        "transitively called marshal.dumps via "
        "ExecutionIsolationManager.create_sandboxed_execution(). "
        "This means Test 3 would NOT catch a future regression that "
        "wires up the sandbox from a router. The M-1 claim has NOT "
        "been verified for transitive violations through isolation.py. "
        "Fix the sentinel mechanism (likely the stack-walking logic in "
        "_make_sentinel) before trusting Test 3's result."
    )

    # The recorded call site MUST be in isolation.py (because that's
    # where marshal.dumps is called from). This proves the sentinel
    # correctly walks up the stack past mock/unittest internals and
    # records the APPLICATION caller (which in this case is isolation.py
    # — a non-test file).
    recorded_filenames = [fn for fn, _ln, _name in raw_log]
    assert any("isolation" in fn or "facp_distributed" in fn for fn in recorded_filenames), (
        f"META-TEST 2 FAILURE: sentinel fired but did NOT record the "
        f"call as coming from isolation.py / facp_distributed. This "
        f"means the sentinel is mis-attributing transitive calls. "
        f"Got: {raw_log}"
    )

    # CRITICAL: The filtered_log MUST be NON-EMPTY here. isolation.py
    # is NOT a test file, so calls from it should NOT be filtered out.
    # If filtered_log is empty, the filter is too aggressive — Test 3
    # would silently swallow a real violation.
    assert filtered_log, (
        "META-TEST 2 FAILURE: filtered_log is empty even though the "
        "sentinel fired from isolation.py (a non-test file). This "
        "means the filter in _make_sentinel is too aggressive — Test 3 "
        "would silently swallow a real HTTP-reachable violation coming "
        "through isolation.py. The M-1 claim has NOT been verified. "
        f"raw_log shows the call WAS detected: {raw_log}. Fix the "
        f"filter logic so non-test files are not excluded."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
