"""
set_github_secrets.py — Push BAZspark production secrets to GitHub Actions.

Encrypts each value with the repository's Actions public key (libsodium
SealedBox, per GitHub's documented workflow) and PUTs it as an Actions secret.
Only the secret NAME is printed; values are NEVER logged.

Usage:
    python scripts/set_github_secrets.py

Env source: .env.production (or .env) via python-dotenv, or process env.

Required env var:
    GH_PAT   — GitHub Personal Access Token (fine-grained, repo secrets:write)
Optional:
    GH_REPO  — "owner/repo" (defaults to ahmdelbaz28-ux/BAZspark)

The secret name list mirrors .env.production.example — the canonical
single source of truth for every BAZspark platform credential.
"""

import base64
import os
import sys

import requests
from dotenv import load_dotenv
from nacl import public

# ─── Config ──────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load in priority order: .env.production (canonical) → .env (dev fallback)
for _env_name in (".env.production", ".env"):
    _env_path = os.path.join(REPO_ROOT, _env_name)
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=False)
        break

GH_PAT = os.environ.get("GH_PAT")
GH_REPO = os.environ.get("GH_REPO", "ahmdelbaz28-ux/BAZspark")
API_URL = f"https://api.github.com/repos/{GH_REPO}/actions/secrets"

# Canonical secret list — keep in sync with .env.production.example
SECRET_KEYS = [
    # Runtime / App
    "FIREAI_API_KEY",
    "FIREAI_SESSION_SECRET",
    # Database
    "DATABASE_URL",
    "NEON_DATABASE_URL",
    # Supabase Auth + REST
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    # Langfuse LLM Observability
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "LANGFUSE_BASE_URL",
    # NVIDIA LLM
    "NVIDIA_API_KEY",
    "NVIDIA_BASE_URL",
    "NVIDIA_MODEL",
    # Resend Email
    "RESEND_API_KEY",
    "RESEND_FROM_EMAIL",
    # Box
    "BOX_CLIENT_ID",
    "BOX_CLIENT_SECRET",
    "BOX_DEVELOPER_TOKEN",
    "CLIENT_NAME",
    # Autodesk APS
    "APS_CLIENT_ID",
    "APS_CLIENT_SECRET",
    "APS_WEBHOOK_URL",
    "APS_CALLBACK_URL",
    # Vercel
    "VERCEL_DEPLOY_TOKEN",
    "VERCEL_DEPLOY_HOOK_URL",
    "VERCEL_PROJECT_ID",
    "VERCEL_TEAM_ID",
    # Hugging Face
    "HF_TOKEN",
    "HF_USERNAME",
    "HF_SPACE_NAME",
    "HF_SPACE_REPO",
    # GitHub
    # NOTE: GH_PAT is intentionally NOT in this list. The token used to push
    # secrets (auth for this script) must never also be stored as a repo
    # secret — otherwise every workflow run could obtain the credential that
    # manages the whole secret store. If a workflow genuinely needs GitHub
    # API access, use a dedicated least-privilege token under its own name
    # (e.g. GH_TOKEN_DEPLOY) or the built-in GITHUB_TOKEN.
    # SonarCloud
    "SONAR_TOKEN",
    "SONAR_ORGANIZATION",
    "SONAR_PROJECT_KEY",
    "SONAR_HOST_URL",
    # Cloudflare
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_ZONE_ID",
    "CLOUDFLARE_USER_TOKEN_1",
    "CLOUDFLARE_USER_TOKEN_2",
    "CLOUDFLARE_USER_TOKEN_3",
    # Daytona / CodeSandbox
    "DAYTONA_API_TOKEN",
    "DAYTONA_API_URL",
    "CODESANDBOX_TOKEN",
    # UptimeRobot
    "UPTIMEROBOT_USER_KEY",
    "UPTIMEROBOT_MONITOR_KEY",
    # CORS
    "CORS_ORIGINS",
    "CORS_ALLOWED_ORIGINS",
    # Self-healing audit
    "QOMN_AUDIT_SECRET_KEY",
]


def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the repository's Actions public key."""
    public_key_bytes = base64.b64decode(public_key)
    pub_key = public.PublicKey(public_key_bytes)
    sealed_box = public.SealedBox(pub_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def main() -> int:
    if not GH_PAT:
        print("Error: GH_PAT environment variable is not set.")
        print("Set GH_PAT in .env.production / .env, or export it.")
        return 1

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GH_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }

    print(f"Fetching GitHub Actions public key for {GH_REPO}...")
    resp = requests.get(f"{API_URL}/public-key", headers=headers, timeout=15)
    if resp.status_code != 200:
        print(f"Failed to fetch public key: HTTP {resp.status_code} {resp.text}")
        return 1

    key_data = resp.json()
    key_id = key_data["key_id"]
    public_key = key_data["key"]
    print("Public key fetched successfully.")

    ok_count = skip_count = fail_count = 0
    for name in SECRET_KEYS:
        value = os.environ.get(name, "")
        if not value:
            print(f"Skipping {name} (no value found in environment)")
            skip_count += 1
            continue

        print(f"Encrypting and pushing secret {name}...")
        encrypted_value = encrypt(public_key, value)
        payload = {"encrypted_value": encrypted_value, "key_id": key_id}

        put_resp = requests.put(f"{API_URL}/{name}", headers=headers, json=payload, timeout=15)
        if put_resp.status_code in (201, 204):
            print(f"SUCCESS: Secret {name} set (HTTP {put_resp.status_code})")
            ok_count += 1
        else:
            print(f"FAILED: Secret {name}: HTTP {put_resp.status_code} {put_resp.text}")
            fail_count += 1

    print(f"\nSummary: {ok_count} set, {skip_count} skipped, {fail_count} failed")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
