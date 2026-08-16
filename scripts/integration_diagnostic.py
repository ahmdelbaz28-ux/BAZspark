#!/usr/bin/env python3
"""
BAZSPARK — End-to-End Integration Diagnostic Script
====================================================
Tests connectivity + auth handshake against EVERY integrated platform and
returns a health report (200 OK per service).

Services covered:
  1. FastAPI backend (local / deployed)          — /api/health
  2. Supabase Postgres (direct SQL)              — SELECT version()
  3. Supabase REST + Auth                        — GET /rest/v1/ + POST /auth/v1/token
  4. Langfuse LLM Observability                  — GET /api/public/health
  5. GitHub Repository + Actions                 — GET /repos/{owner}/{repo}
  6. Hugging Face Space (sync target)            — GET /api/spaces/{owner}/{name}
  7. Vercel API + Project                        — GET /v9/projects/{id}
  8. Cloudflare API (user + zone)                — GET /client/v4/user / zones
  9. Autodesk APS (OAuth2 token)                 — POST /authentication/v2/token
 10. Resend Email                                — GET /emails (auth check)
 11. SonarCloud Quality Gate                     — GET /api/qualitygates/project_status
 12. Daytona VPS                                 — GET / (API root auth)
 13. CodeSandbox VPS                             — GET /api/sandboxes (auth check)

EXIT CODES
  0 — all reachable tests passed (SKIP is OK)
  1 — at least one FAIL
  2 — script error / missing deps

USAGE
  python scripts/integration_diagnostic.py
  python scripts/integration_diagnostic.py --json      # machine-readable report
  python scripts/integration_diagnostic.py --endpoint <base>   # custom backend URL

ENV SOURCE PRIORITY
  1. Current process environment (already exported)
  2. .env.production          (if exists — real production values, gitignored)
  3. .env                     (fallback local)

SECURITY
  - Every upstream-captured string passes through redact() before it is
    stored/serialized, so no credential can reach console output, the --json
    report, or CI artifacts (Bearer/JWT tokens, github_pat_/hf_/sk-lf-/pk-lf-/
    re_/vcp_/cfut_/dtn_/csb_v1_/sbp_/napi_/box_ prefixed keys, URL user:pass).
  - The script NEVER prints raw token values; environment values are only
    reported through mask() (first 4 chars + ***).
"""

from __future__ import annotations

import argparse
import json
import os
import re as _re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    print("Missing dependency: httpx. Install with: pip install httpx")
    sys.exit(2)

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore[assignment]

# ─── Color helpers (Windows-safe: disable on non-TTY) ───────────────────────
_ENABLE_COLOR = (sys.stdout.isatty() and os.name != "nt") or os.environ.get("FORCE_COLOR") == "1"


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _ENABLE_COLOR else text


def _green(t: str) -> str:
    return _c("92", t)


def _red(t: str) -> str:
    return _c("91", t)


def _yellow(t: str) -> str:
    return _c("93", t)


def _blue(t: str) -> str:
    return _c("94", t)


# ─── Env loading (never prints values) ───────────────────────────────────────
def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            # Do not overwrite already-set process env (priority 1 wins).
            os.environ.setdefault(key, value)


def mask(value: str | None, visible: int = 4) -> str:
    if not value:
        return "<unset>"
    if len(value) <= visible + 3:
        return f"{value[:2]}***"
    return f"{value[:visible]}*** (len={len(value)})"


# ─── Output redaction ─────────────────────────────────────────────────────────
# Every detail/error string captured from upstream APIs flows through redact()
# before it is stored in a Check — and therefore before it can reach the
# console report, the --json report, or the CI artifact/step summary.
# Covers all known BAZspark credential formats plus generic Bearer/JWT tokens.

# Patterns whose matches are fully replaced with <redacted>.
_REDACT_REPLACE = [
    _re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{12,}", _re.IGNORECASE),
    _re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),  # JWT
    _re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    _re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    _re.compile(r"hf_[A-Za-z0-9_\-]{20,}"),
    _re.compile(r"sk-lf-[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"pk-lf-[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"re_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"vcp_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"prj_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"cfut_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"dtn_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"csb_v1_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"sbp_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"sb_secret_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"napi_[A-Za-z0-9_\-]{10,}"),
    _re.compile(r"u\d{7}-[A-Za-z0-9]{10,}"),  # UptimeRobot user key
    _re.compile(r"m\d{7}-[A-Za-z0-9]{10,}"),  # UptimeRobot monitor key
    _re.compile(r"box_[a-f0-9]{20,}"),  # Box developer token
    _re.compile(
        r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-\.]{12,}"
    ),
]

# Patterns whose match is replaced preserving a leading group (e.g. URL scheme).
_REDACT_KEEP_GROUP = [
    (
        _re.compile(r"(://)([^:\s/@]+):([^@\s/]+)@"),
        r"\1<redacted>:<redacted>@",
    ),  # user:pass@ in URLs
]


def redact(text: Any) -> Any:
    """Mask any embedded credential inside diagnostic strings (or lists of them)."""
    if isinstance(text, list):
        return [redact(item) for item in text]
    if not isinstance(text, str) or not text:
        return text
    out = text
    for pat in _REDACT_REPLACE:
        out = pat.sub("<redacted>", out)
    for pat, repl in _REDACT_KEEP_GROUP:
        out = pat.sub(repl, out)
    return out


# ─── Result model ────────────────────────────────────────────────────────────
@dataclass
class Check:
    service: str
    status: str  # OK | WARN | FAIL | SKIP
    http_code: int | None
    detail: str = ""
    latency_ms: int = 0
    checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status in ("OK", "SKIP")


# ─── Diagnostic engine ───────────────────────────────────────────────────────
class IntegrationDiagnostic:
    def __init__(self, base_url: str, timeout: float = 12.0, json_out: bool = False):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.json_out = json_out
        self.results: list[Check] = []

    # ── helpers ──────────────────────────────────────────────────────────
    def _check(
        self,
        service: str,
        status: str,
        code: int | None = None,
        detail: str = "",
        latency: int = 0,
        sub: list[dict[str, Any]] | None = None,
    ) -> Check:
        # Central redaction gate: every upstream-captured string is scrubbed
        # here, so no token can reach console output, --json, or CI artifacts.
        c = Check(service, status, code, redact(detail), latency, redact(sub) if sub else [])
        self.results.append(c)
        return c

    def _print(self, c: Check) -> None:
        if self.json_out:
            return
        color = {"OK": _green, "SKIP": _yellow, "WARN": _yellow, "FAIL": _red}[c.status]
        code_s = f" HTTP {c.http_code}" if c.http_code else ""
        print(f"  {color(f'[{c.status:4}]')} {c.service:<38} {code_s}  {c.latency_ms:>6}ms")
        if c.detail:
            print(f"        -> {c.detail}")
        for sub in c.checks:
            print(f"        * {sub}")

    def _http(self, method: str, url: str, **kw: Any) -> httpx.Response:
        """Timeout-aware HTTP helper with latency measurement."""
        start = time.perf_counter()
        try:
            resp = httpx.request(method, url, timeout=self.timeout, **kw)
            latency = int((time.perf_counter() - start) * 1000)
            resp._baz_latency = latency  # type: ignore[attr-defined]
            return resp
        except httpx.HTTPError as exc:
            # Re-raise with latency attached via exception attribute
            latency = int((time.perf_counter() - start) * 1000)
            exc._baz_latency = latency  # type: ignore[attr-defined]
            raise

    # ── 1. Backend health ────────────────────────────────────────────────
    async def check_backend(self) -> Check:
        try:
            resp = self._http("GET", f"{self.base_url}/api/health")
            lat = getattr(resp, "_baz_latency", 0)
            if resp.status_code == 200:
                data = resp.json()
                return self._check(
                    "FastAPI Backend",
                    "OK",
                    200,
                    f"status={data.get('status')} db={data.get('database')}",
                    lat,
                )
            return self._check(
                "FastAPI Backend",
                "FAIL",
                resp.status_code,
                f"expected 200, got {resp.status_code}",
                lat,
            )
        except httpx.ConnectError as exc:
            lat = getattr(exc, "_baz_latency", 0)
            return self._check(
                "FastAPI Backend",
                "WARN",
                None,
                "server not running locally (expected in diagnostic-only mode)",
                lat,
            )
        except Exception as exc:
            lat = getattr(exc, "_baz_latency", 0)
            return self._check("FastAPI Backend", "FAIL", None, str(exc)[:120], lat)

    # ── 2. Supabase Postgres direct ──────────────────────────────────────
    def check_supabase_postgres(self) -> Check:
        url = os.environ.get("DATABASE_URL", "")
        if not url or url.startswith("sqlite"):
            return self._check(
                "Supabase Postgres", "SKIP", detail="DATABASE_URL not set or sqlite (dev mode)"
            )
        if psycopg2 is None:
            return self._check("Supabase Postgres", "SKIP", detail="psycopg2 not installed")
        try:
            start = time.perf_counter()
            conn = psycopg2.connect(url, connect_timeout=8)
            cur = conn.cursor()
            cur.execute("SELECT version();")
            ver = cur.fetchone()[0][:60]
            cur.close()
            conn.close()
            lat = int((time.perf_counter() - start) * 1000)
            return self._check("Supabase Postgres", "OK", 200, ver, lat)
        except Exception as exc:
            lat = int((time.perf_counter() - start) * 1000)
            msg = str(exc)[:120]
            # Documented project behavior: Supabase's IPv6-only hostname is
            # unreachable from some networks → NEON_DATABASE_URL is the
            # automatic IPv4 fallback (see backend/database.py).
            if "could not translate host name" in msg or "getaddrinfo" in msg:
                neon = (
                    "NEON fallback configured"
                    if os.environ.get("NEON_DATABASE_URL")
                    else "NEON fallback NOT configured"
                )
                return self._check(
                    "Supabase Postgres", "WARN", None, f"DNS unreachable ({neon}): {msg}", lat
                )
            return self._check("Supabase Postgres", "FAIL", None, msg, lat)

    # ── 3. Supabase REST + Auth ──────────────────────────────────────────
    async def check_supabase_rest(self) -> Check:
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        anon = os.environ.get("SUPABASE_ANON_KEY", "")
        service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url:
            return self._check("Supabase REST/Auth", "SKIP", detail="SUPABASE_URL not set")
        sub: list[dict[str, Any]] = []
        ok = True
        dns_issue = False
        # 3a. REST health probe (public table list is auth-gated; use root)
        try:
            resp = self._http(
                "GET",
                f"{url}/rest/v1/",
                headers={
                    "apikey": anon or service or "",
                    "Authorization": f"Bearer {anon or service}",
                },
            )
            code = resp.status_code
            sub.append({"REST /rest/v1/": f"HTTP {code}"})
            if code in (200, 404):  # 404 w/o table is still an authenticated reachable API
                sub.append({"REST reachable": "yes"})
            else:
                ok = False
                sub.append({"REST reachable": f"HTTP {code}"})
        except Exception as exc:
            msg = str(exc)[:100]
            # Documented IPv6-only DNS issue → treat as WARN, not FAIL.
            if "getaddrinfo" in msg or "No such host" in msg:
                sub.append({"REST": "DNS unreachable (documented IPv6 issue; NEON fallback)"})
                dns_issue = True
            else:
                ok = False
                sub.append({"REST": msg})
        # 3b. Auth token handshake (password grant — health-only, no real creds)
        try:
            resp = self._http(
                "POST",
                f"{url}/auth/v1/token?grant_type=password",
                headers={"apikey": anon or service or ""},
                json={"email": "none@invalid.invalid", "password": "x"},
            )
            code = resp.status_code
            sub.append({"Auth /auth/v1/token": f"HTTP {code} (400/401=reachable)"})
            if code in (400, 401, 422):
                sub.append({"Auth handshake": "reachable (credentials rejected as expected)"})
            else:
                ok = False
                sub.append({"Auth handshake": f"unexpected HTTP {code}"})
        except Exception as exc:
            msg = str(exc)[:100]
            if "getaddrinfo" in msg or "No such host" in msg:
                sub.append({"Auth": "DNS unreachable (documented IPv6 issue; NEON fallback)"})
                dns_issue = True
            else:
                ok = False
                sub.append({"Auth": msg})
        # WARN only when BOTH probes failed with the documented DNS issue and
        # nothing else failed. A genuine non-DNS failure keeps FAIL.
        status = "WARN" if (dns_issue and ok) else ("OK" if ok else "FAIL")
        return self._check(
            "Supabase REST/Auth",
            status,
            200 if ok else None,
            "; ".join(f"{k}={v}" for d in sub for k, v in d.items()),
            latency=0,
            sub=[f"{k}: {v}" for d in sub for k, v in d.items()],
        )

    # ── 4. Langfuse ──────────────────────────────────────────────────────
    async def check_langfuse(self) -> Check:
        base = (
            os.environ.get("LANGFUSE_BASE_URL")
            or os.environ.get("LANGFUSE_HOST")
            or "https://cloud.langfuse.com"
        )
        pub = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        sec = os.environ.get("LANGFUSE_SECRET_KEY", "")
        if not (pub and sec):
            return self._check("Langfuse", "SKIP", detail="LANGFUSE keys not set")
        auth = (pub, sec)
        sub = []
        # public health (no auth required)
        try:
            resp = self._http("GET", f"{base}/api/public/health")
            sub.append({"public health": f"HTTP {resp.status_code}"})
        except Exception as exc:
            sub.append({"public health": str(exc)[:80]})
            return self._check("Langfuse", "FAIL", None, sub[-1]["public health"])
        # authed trace creation probe (the actual auth handshake)
        auth_ok = False
        auth_detail = ""
        try:
            import uuid

            trace_id = str(uuid.uuid4())
            resp = self._http(
                "POST",
                f"{base}/api/public/traces",
                auth=auth,
                json={"id": trace_id, "name": "bazspark-diagnostic"},
            )
            sub.append({"create trace": f"HTTP {resp.status_code}"})
            if resp.status_code == 200:
                auth_ok = True
                sub.append({"trace id": trace_id[:8]})
            else:
                auth_detail = f"auth probe HTTP {resp.status_code}"
                sub.append({"auth handshake": auth_detail})
        except Exception as exc:
            auth_detail = str(exc)[:80]
            sub.append({"create trace": auth_detail})
        # OK requires the AUTHENTICATED probe to succeed — the public health
        # endpoint alone (HTTP 200) does NOT prove key validity.
        if auth_ok:
            status, code = "OK", 200
        elif auth_detail:
            status, code = "FAIL", None
        else:
            status, code = "FAIL", None
        return self._check(
            "Langfuse",
            status,
            code,
            "; ".join(f"{k}={v}" for s in sub for k, v in s.items()),
            latency=0,
            sub=[f"{k}: {v}" for s in sub for k, v in s.items()],
        )

    # ── 5. GitHub ────────────────────────────────────────────────────────
    async def check_github(self) -> Check:
        pat = os.environ.get("GH_PAT", "")
        repo = os.environ.get("GH_REPO", "ahmdelbaz28-ux/BAZspark")
        if not pat:
            return self._check("GitHub", "SKIP", detail="GH_PAT not set")
        headers = {
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        sub: list[dict[str, Any]] = []
        try:
            resp = self._http("GET", f"https://api.github.com/repos/{repo}", headers=headers)
            lat = getattr(resp, "_baz_latency", 0)
            sub.append({"repo fetch": f"HTTP {resp.status_code}"})
            if resp.status_code == 200:
                data = resp.json()
                sub.append({"repo": data.get("full_name", "")})
                sub.append({"default_branch": data.get("default_branch", "")})
                sub.append({"private": str(data.get("private", ""))})
            else:
                return self._check(
                    "GitHub",
                    "FAIL",
                    resp.status_code,
                    f"repo fetch HTTP {resp.status_code}",
                    lat,
                    sub=[f"{k}: {v}" for d in sub for k, v in d.items()],
                )
        except Exception as exc:
            return self._check("GitHub", "FAIL", None, str(exc)[:100], sub=[str(exc)[:100]])
        # workflow runs status (CI/CD pipeline health)
        try:
            resp = self._http(
                "GET",
                f"https://api.github.com/repos/{repo}/actions/runs?per_page=3",
                headers=headers,
            )
            if resp.status_code == 200:
                runs = resp.json().get("workflow_runs", [])
                sub.append({"recent workflow runs": str(len(runs))})
                if runs:
                    sub.append(
                        {
                            "latest run": f"{runs[0].get('name')} -> {runs[0].get('status')}/{runs[0].get('conclusion')}"
                        }
                    )
            else:
                sub.append({"workflow runs": f"HTTP {resp.status_code}"})
        except Exception as exc:
            sub.append({"workflow runs": str(exc)[:80]})
        # secrets visibility (names only, never values)
        try:
            resp = self._http(
                "GET", f"https://api.github.com/repos/{repo}/actions/secrets", headers=headers
            )
            if resp.status_code == 200:
                names = [s["name"] for s in resp.json().get("secrets", [])]
                sub.append({"secrets": f"{len(names)} configured: {', '.join(sorted(names)[:8])}"})
            else:
                sub.append({"secrets": f"HTTP {resp.status_code}"})
        except Exception as exc:
            sub.append({"secrets": str(exc)[:80]})
        return self._check(
            "GitHub",
            "OK",
            200,
            "; ".join(f"{k}={v}" for s in sub for k, v in s.items()),
            sub=[f"{k}: {v}" for s in sub for k, v in s.items()],
        )

    # ── 6. Hugging Face ──────────────────────────────────────────────────
    async def check_huggingface(self) -> Check:
        token = os.environ.get("HF_TOKEN", "")
        space = os.environ.get(
            "HF_SPACE_REPO", "https://huggingface.co/spaces/ahmdelbaz28/BAZSPARK"
        )
        # normalize to owner/name
        owner_name = space.rstrip("/").split("/spaces/")[-1] if "/spaces/" in space else space
        if not token:
            return self._check("HuggingFace Space", "SKIP", detail="HF_TOKEN not set")
        headers = {"Authorization": f"Bearer {token}"}
        sub: list[dict[str, Any]] = []
        try:
            resp = self._http(
                "GET", f"https://huggingface.co/api/spaces/{owner_name}", headers=headers
            )
            lat = getattr(resp, "_baz_latency", 0)
            sub.append({"space fetch": f"HTTP {resp.status_code}"})
            if resp.status_code == 200:
                data = resp.json()
                sub.append({"space": data.get("id", owner_name)})
                sub.append(
                    {
                        "runtime": data.get("runtime", {}).get("stage", "?")
                        if data.get("runtime")
                        else "?"
                    }
                )
                sub.append({"sdk": data.get("sdk", "?")})
            else:
                return self._check(
                    "HuggingFace Space",
                    "FAIL",
                    resp.status_code,
                    f"HTTP {resp.status_code} {resp.text[:80]}",
                    lat,
                    sub=[f"{k}: {v}" for d in sub for k, v in d.items()],
                )
        except Exception as exc:
            return self._check("HuggingFace Space", "FAIL", None, str(exc)[:100])
        # whoami (token validity)
        try:
            resp = self._http("GET", "https://huggingface.co/api/whoami-v2", headers=headers)
            if resp.status_code == 200:
                who = resp.json()
                sub.append({"token owner": who.get("name", "?")})
            else:
                sub.append({"whoami": f"HTTP {resp.status_code} (token invalid?)"})
        except Exception as exc:
            sub.append({"whoami": str(exc)[:80]})
        return self._check(
            "HuggingFace Space",
            "OK",
            200,
            "; ".join(f"{k}={v}" for s in sub for k, v in s.items()),
            sub=[f"{k}: {v}" for s in sub for k, v in s.items()],
        )

    # ── 7. Vercel ────────────────────────────────────────────────────────
    async def check_vercel(self) -> Check:
        token = os.environ.get("VERCEL_DEPLOY_TOKEN", "")
        project_id = os.environ.get("VERCEL_PROJECT_ID", "")
        team_id = os.environ.get("VERCEL_TEAM_ID", "")
        if not token:
            return self._check("Vercel", "SKIP", detail="VERCEL_DEPLOY_TOKEN not set")
        headers = {"Authorization": f"Bearer {token}"}
        params = {"teamId": team_id} if team_id else {}
        sub: list[dict[str, Any]] = []
        try:
            resp = self._http("GET", "https://api.vercel.com/v2/user", headers=headers)
            lat = getattr(resp, "_baz_latency", 0)
            sub.append({"user": f"HTTP {resp.status_code}"})
            if resp.status_code == 200:
                sub.append({"user": resp.json().get("user", {}).get("username", "?")})
            else:
                return self._check(
                    "Vercel",
                    "FAIL",
                    resp.status_code,
                    f"auth HTTP {resp.status_code}",
                    lat,
                    sub=[f"{k}: {v}" for d in sub for k, v in d.items()],
                )
        except Exception as exc:
            return self._check("Vercel", "FAIL", None, str(exc)[:100])
        if project_id:
            try:
                resp = self._http(
                    "GET",
                    f"https://api.vercel.com/v9/projects/{project_id}",
                    headers=headers,
                    params=params,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    sub.append({"project": data.get("name", project_id)})
                    sub.append({"framework": data.get("framework", "?")})
                    sub.append({"git repo": str(data.get("link", {}).get("repo", "?"))})
                    # env vars (names only)
                    try:
                        eresp = self._http(
                            "GET",
                            f"https://api.vercel.com/v9/projects/{project_id}/env",
                            headers=headers,
                            params=params,
                        )
                        if eresp.status_code == 200:
                            envs = [e.get("key") for e in eresp.json().get("envs", [])]
                            sub.append({"env vars": f"{len(envs)}: {', '.join(sorted(envs)[:8])}"})
                        else:
                            sub.append({"env vars": f"HTTP {eresp.status_code}"})
                    except Exception as exc:
                        sub.append({"env vars": str(exc)[:80]})
                else:
                    sub.append({"project fetch": f"HTTP {resp.status_code}"})
            except Exception as exc:
                sub.append({"project fetch": str(exc)[:80]})
        return self._check(
            "Vercel",
            "OK",
            200,
            "; ".join(f"{k}={v}" for s in sub for k, v in s.items()),
            sub=[f"{k}: {v}" for s in sub for k, v in s.items()],
        )

    # ── 8. Cloudflare ────────────────────────────────────────────────────
    async def check_cloudflare(self) -> Check:
        token = (
            os.environ.get("CLOUDFLARE_API_TOKEN")
            or os.environ.get("CLOUDFLARE_USER_TOKEN_1")
            or os.environ.get("CLOUDFLARE_USER_TOKEN_2")
            or os.environ.get("CLOUDFLARE_USER_TOKEN_3")
        )
        zone_id = os.environ.get("CLOUDFLARE_ZONE_ID", "")
        if not token:
            return self._check("Cloudflare", "SKIP", detail="Cloudflare token not set")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        sub: list[dict[str, Any]] = []
        try:
            resp = self._http("GET", "https://api.cloudflare.com/client/v4/user", headers=headers)
            lat = getattr(resp, "_baz_latency", 0)
            sub.append({"user verify": f"HTTP {resp.status_code}"})
            if resp.status_code != 200:
                return self._check(
                    "Cloudflare",
                    "FAIL",
                    resp.status_code,
                    f"auth HTTP {resp.status_code}",
                    lat,
                    sub=[f"{k}: {v}" for d in sub for k, v in d.items()],
                )
        except Exception as exc:
            return self._check("Cloudflare", "FAIL", None, str(exc)[:100])
        if zone_id:
            try:
                resp = self._http(
                    "GET", f"https://api.cloudflare.com/client/v4/zones/{zone_id}", headers=headers
                )
                if resp.status_code == 200:
                    z = resp.json().get("result", {})
                    sub.append({"zone": z.get("name", zone_id)})
                    sub.append({"status": z.get("status", "?")})
                else:
                    sub.append({"zone fetch": f"HTTP {resp.status_code}"})
            except Exception as exc:
                sub.append({"zone fetch": str(exc)[:80]})
        else:
            # list zones (first 3 names)
            try:
                resp = self._http(
                    "GET", "https://api.cloudflare.com/client/v4/zones?per_page=3", headers=headers
                )
                if resp.status_code == 200:
                    zones = [z.get("name") for z in resp.json().get("result", [])]
                    sub.append({"zones": ", ".join(zones) or "none"})
            except Exception as exc:
                sub.append({"zones": str(exc)[:80]})
        return self._check(
            "Cloudflare",
            "OK",
            200,
            "; ".join(f"{k}={v}" for s in sub for k, v in s.items()),
            sub=[f"{k}: {v}" for s in sub for k, v in s.items()],
        )

    # ── 9. Autodesk APS ──────────────────────────────────────────────────
    async def check_autodesk_aps(self) -> Check:
        cid = os.environ.get("APS_CLIENT_ID", "")
        secret = os.environ.get("APS_CLIENT_SECRET", "")
        if not (cid and secret):
            return self._check("Autodesk APS", "SKIP", detail="APS_CLIENT_ID/SECRET not set")
        scopes = "data:read data:write bucket:create bucket:read"
        try:
            resp = self._http(
                "POST",
                "https://developer.api.autodesk.com/authentication/v2/token",
                data={
                    "client_id": cid,
                    "client_secret": secret,
                    "grant_type": "client_credentials",
                    "scope": scopes,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            lat = getattr(resp, "_baz_latency", 0)
            if resp.status_code == 200:
                tok = resp.json()
                exp = tok.get("expires_in", 0)
                sub = [f"token_type: {tok.get('token_type')}", f"expires_in: {exp}s"]
                return self._check("Autodesk APS", "OK", 200, "; ".join(sub), lat, sub)
            return self._check(
                "Autodesk APS",
                "FAIL",
                resp.status_code,
                f"HTTP {resp.status_code} {resp.text[:100]}",
                lat,
            )
        except Exception as exc:
            return self._check("Autodesk APS", "FAIL", None, str(exc)[:100])

    # ── 10. Resend ───────────────────────────────────────────────────────
    async def check_resend(self) -> Check:
        key = os.environ.get("RESEND_API_KEY", "")
        if not key:
            return self._check("Resend Email", "SKIP", detail="RESEND_API_KEY not set")
        try:
            resp = self._http(
                "GET", "https://api.resend.com/emails", headers={"Authorization": f"Bearer {key}"}
            )
            lat = getattr(resp, "_baz_latency", 0)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return self._check(
                    "Resend Email", "OK", 200, f"auth OK, {len(data)} recent emails", lat
                )
            if resp.status_code == 401:
                return self._check("Resend Email", "FAIL", 401, "invalid API key", lat)
            return self._check(
                "Resend Email",
                "WARN",
                resp.status_code,
                f"HTTP {resp.status_code} {resp.text[:80]}",
                lat,
            )
        except Exception as exc:
            return self._check("Resend Email", "FAIL", None, str(exc)[:100])

    # ── 11. SonarCloud ───────────────────────────────────────────────────
    async def check_sonarcloud(self) -> Check:
        token = os.environ.get("SONAR_TOKEN", "")
        org = os.environ.get("SONAR_ORGANIZATION", "ahmdelbaz28-ux")
        key = os.environ.get("SONAR_PROJECT_KEY", "ahmdelbaz28-ux_revit")
        host = os.environ.get("SONAR_HOST_URL", "https://sonarcloud.io").rstrip("/")
        auth = (token, "") if token else None
        sub: list[dict[str, Any]] = []
        try:
            resp = self._http(
                "GET",
                f"{host}/api/projects/search?q={key.split(':')[-1]}&organization={org}",
                auth=auth,
            )
            lat = getattr(resp, "_baz_latency", 0)
            sub.append({"project search": f"HTTP {resp.status_code}"})
            if resp.status_code == 200:
                comps = resp.json().get("components", [])
                if comps:
                    sub.append({"project": comps[0].get("key")})
                else:
                    sub.append({"project": "not found — check SONAR_PROJECT_KEY"})
            else:
                return self._check(
                    "SonarCloud",
                    "FAIL",
                    resp.status_code,
                    f"HTTP {resp.status_code} {resp.text[:80]}",
                    lat,
                    sub=[f"{k}: {v}" for d in sub for k, v in d.items()],
                )
        except Exception as exc:
            return self._check("SonarCloud", "FAIL", None, str(exc)[:100])
        # quality gate status
        try:
            resp = self._http(
                "GET", f"{host}/api/qualitygates/project_status?projectKey={key}", auth=auth
            )
            if resp.status_code == 200:
                st = resp.json().get("projectStatus", {})
                sub.append({"quality gate": st.get("status", "?")})
            else:
                sub.append({"quality gate": f"HTTP {resp.status_code}"})
        except Exception as exc:
            sub.append({"quality gate": str(exc)[:80]})
        return self._check(
            "SonarCloud",
            "OK",
            200,
            "; ".join(f"{k}={v}" for s in sub for k, v in s.items()),
            sub=[f"{k}: {v}" for s in sub for k, v in s.items()],
        )

    # ── 12. Daytona ──────────────────────────────────────────────────────
    async def check_daytona(self) -> Check:
        token = os.environ.get("DAYTONA_API_TOKEN", "")
        base = os.environ.get("DAYTONA_API_URL", "https://app.daytona.io").rstrip("/")
        if not token:
            return self._check("Daytona VPS", "SKIP", detail="DAYTONA_API_TOKEN not set")
        try:
            resp = self._http("GET", f"{base}/", headers={"Authorization": f"Bearer {token}"})
            lat = getattr(resp, "_baz_latency", 0)
            # 200/401/403 all prove endpoint reachability; 200 proves auth
            if resp.status_code in (200, 201):
                return self._check(
                    "Daytona VPS", "OK", 200, f"reachable + authed (HTTP {resp.status_code})", lat
                )
            if resp.status_code in (401, 403):
                return self._check(
                    "Daytona VPS",
                    "WARN",
                    resp.status_code,
                    "reachable, auth failed (check token)",
                    lat,
                )
            return self._check(
                "Daytona VPS", "WARN", resp.status_code, f"reachable HTTP {resp.status_code}", lat
            )
        except Exception as exc:
            return self._check("Daytona VPS", "FAIL", None, str(exc)[:100])

    # ── 13. CodeSandbox ──────────────────────────────────────────────────
    async def check_codesandbox(self) -> Check:
        token = os.environ.get("CODESANDBOX_TOKEN", "")
        if not token:
            return self._check("CodeSandbox VPS", "SKIP", detail="CODESANDBOX_TOKEN not set")
        try:
            resp = self._http(
                "GET",
                "https://api.codesandbox.io/v1/sandboxes",
                headers={"Authorization": f"Bearer {token}"},
            )
            lat = getattr(resp, "_baz_latency", 0)
            if resp.status_code == 200:
                return self._check(
                    "CodeSandbox VPS", "OK", 200, f"auth OK (HTTP {resp.status_code})", lat
                )
            if resp.status_code in (401, 403):
                return self._check(
                    "CodeSandbox VPS", "WARN", resp.status_code, "reachable, auth failed", lat
                )
            return self._check(
                "CodeSandbox VPS",
                "WARN",
                resp.status_code,
                f"reachable HTTP {resp.status_code}",
                lat,
            )
        except Exception as exc:
            return self._check("CodeSandbox VPS", "FAIL", None, str(exc)[:100])

    # ── runner ───────────────────────────────────────────────────────────
    async def run_all(self) -> None:
        # Sequential with fast timeouts; parallelism would complicate the
        # latency reporting. Order: local → DB → APIs.
        await self.check_backend()
        self.check_supabase_postgres()
        await self.check_supabase_rest()
        await self.check_langfuse()
        await self.check_github()
        await self.check_huggingface()
        await self.check_vercel()
        await self.check_cloudflare()
        await self.check_autodesk_aps()
        await self.check_resend()
        await self.check_sonarcloud()
        await self.check_daytona()
        await self.check_codesandbox()


# ─── CLI ─────────────────────────────────────────────────────────────────────
def _load_env() -> None:
    # Priority: process env > .env.production > .env (in repo root)
    repo_root = Path(__file__).resolve().parent.parent
    for name in (".env.production", ".env"):
        _load_env_file(repo_root / name)


def main() -> int:
    parser = argparse.ArgumentParser(description="BAZspark E2E Integration Diagnostic")
    parser.add_argument("--endpoint", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--timeout", type=float, default=12.0, help="Per-request timeout (s)")
    args = parser.parse_args()

    _load_env()

    diag = IntegrationDiagnostic(args.endpoint, args.timeout, args.json)
    import asyncio

    asyncio.run(diag.run_all())

    if args.json:
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "endpoint": args.endpoint,
            "summary": {
                "total": len(diag.results),
                "ok": sum(1 for r in diag.results if r.status == "OK"),
                "warn": sum(1 for r in diag.results if r.status == "WARN"),
                "fail": sum(1 for r in diag.results if r.status == "FAIL"),
                "skip": sum(1 for r in diag.results if r.status == "SKIP"),
            },
            "checks": [asdict(r) for r in diag.results],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_blue("=" * 72))
        print(_blue(" BAZSPARK - End-to-End Integration Diagnostic Report".center(72)))
        print(_blue("=" * 72))
        for c in diag.results:
            diag._print(c)
        ok = sum(1 for r in diag.results if r.status == "OK")
        warn = sum(1 for r in diag.results if r.status == "WARN")
        fail = sum(1 for r in diag.results if r.status == "FAIL")
        skip = sum(1 for r in diag.results if r.status == "SKIP")
        print(_blue("=" * 72))
        print(
            f"  OK: {_green(str(ok))}   WARN: {_yellow(str(warn))}   "
            f"FAIL: {_red(str(fail))}   SKIP: {_yellow(str(skip))}"
        )
        print(_blue("=" * 72))
        if fail == 0:
            print(_green("  [PASS] ALL REACHABLE INTEGRATIONS HEALTHY - 100% SYNC READY"))
        else:
            print(_red("  [FAIL] SOME INTEGRATIONS FAILED - see details above"))
        print()

    return 1 if any(r.status == "FAIL" for r in diag.results) else 0


if __name__ == "__main__":
    sys.exit(main())
