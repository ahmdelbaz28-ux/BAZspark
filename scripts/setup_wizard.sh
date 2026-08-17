#!/usr/bin/env bash
#
# BAZspark Interactive Setup Wizard — walks a human through environment and secret configuration.
# Generated via /wizard skill.
#
# Everything above the "STAGES" marker is the wizard library: do not hand-edit
# it. Author the per-step stages below the marker.

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# Wizard library — delightful, consistent UX. Identical across every wizard.
# ──────────────────────────────────────────────────────────────────────────

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
  BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
  BLUE=$(tput setaf 4); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3); RED=$(tput setaf 1)
else
  BOLD=""; DIM=""; RESET=""; BLUE=""; GREEN=""; YELLOW=""; RED=""
fi

# Author sets this at the top of the stages section.
TOTAL_STAGES=7

_STAGE_INDEX=0
ENV_FILE="${ENV_FILE:-.env}"
WRITTEN_ENV=()    # KEYs written to ENV_FILE this run
WRITTEN_SECRET=() # secret NAMEs set this run
SKIPPED=()        # things we couldn't do (e.g. gh missing)

# _clear — wipe the terminal so only the current step is on screen. No-op when
# output isn't a terminal, so piped logs stay readable.
_clear() {
  [[ -t 1 ]] || return 0
  if command -v tput >/dev/null 2>&1; then tput clear; else printf '\033[2J\033[3J\033[H'; fi
}

# banner "Title" — opening frame: what this wizard does.
banner() {
  _clear
  printf '\n%s%s  %s%s\n' "$BOLD" "$BLUE" "$1" "$RESET"
  printf '%s  %s stages%s\n\n' "$DIM" "$TOTAL_STAGES" "$RESET"
  printf '%s  You drive the browser; this wizard tells you exactly what to do and\n' "$DIM"
  printf '  captures the values you copy back. Stop any time with Ctrl-C and re-run\n'
  printf '  later — it remembers values already saved.%s\n' "$RESET"
  pause "Ready to start?"
}

# stage "Name" — clear the screen, then announce a stage and show progress.
stage() {
  _clear
  _STAGE_INDEX=$((_STAGE_INDEX + 1))
  printf '\n%s%s▸ Stage %s/%s · %s%s\n' \
    "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET"
}

# say "..." — a plain instruction line.
say()  { printf '  %s\n' "$1"; }
# step "..." — a numbered-feeling action the human takes in the browser.
step() { printf '  %s•%s %s\n' "$BLUE" "$RESET" "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }

# open_url URL — open in the human's browser, cross-platform incl. WSL.
open_url() {
  local url="$1"
  printf '  %s↗ opening%s %s\n' "$GREEN" "$RESET" "$url"
  { if   command -v wslview     >/dev/null 2>&1; then wslview "$url"
    elif command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$url"
    elif command -v xdg-open    >/dev/null 2>&1; then xdg-open "$url"
    elif command -v open        >/dev/null 2>&1; then open "$url"
    else warn "couldn't open a browser — visit it manually: $url"; fi
  } >/dev/null 2>&1 || warn "couldn't open a browser — visit it manually: $url"
}

# pause "msg" — wait for the human to confirm they've done the manual part.
pause() {
  printf '  %s%s%s ' "$DIM" "${1:-Press Enter to continue}" "$RESET"
  read -r _ || true
}

# confirm "question" — y/N gate; returns success on yes.
confirm() {
  local reply=""
  printf '  %s? %s [y/N] ' "$YELLOW" "$1"
  read -r reply || true
  [[ "$reply" =~ ^[Yy] ]]
}

# _existing KEY — current value of KEY in ENV_FILE, if any.
_existing() {
  [[ -f "$ENV_FILE" ]] || return 1
  local line; line=$(grep -E "^${1}=" "$ENV_FILE" | tail -n1) || return 1
  printf '%s' "${line#*=}"
}

# ask KEY "Prompt" — read a value into $KEY. Offers the existing .env value as
# a default on re-runs (Enter keeps it). Visible input (non-secret).
ask() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter keeps current]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -r input || true
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

# ask_secret KEY "Prompt" — like ask, but input is hidden.
ask_secret() {
  local key="$1" prompt="$2" current input
  current=$(_existing "$key" || true)
  if [[ -n "$current" ]]; then
    printf '  %s%s%s %s[Enter keeps current]%s ' "$BOLD" "$prompt" "$RESET" "$DIM" "$RESET"
  else
    printf '  %s%s%s ' "$BOLD" "$prompt" "$RESET"
  fi
  read -rs input || true
  printf '\n'
  [[ -z "$input" && -n "$current" ]] && input="$current"
  printf -v "$key" '%s' "$input"
}

# write_env KEY VALUE — upsert KEY=VALUE into ENV_FILE (creates it; replaces
# any existing line). Idempotent.
write_env() {
  local key="$1" value="$2" tmp
  touch "$ENV_FILE"
  tmp=$(mktemp)
  grep -vE "^${key}=" "$ENV_FILE" > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
  WRITTEN_ENV+=("$key")
  printf '  %s✓ wrote%s %s → %s\n' "$GREEN" "$RESET" "$key" "$ENV_FILE"
}

# set_secret NAME VALUE — set a GitHub Actions repo secret via gh. Falls back
# to a warning (and records it) if gh is unavailable or unauthenticated.
set_secret() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if printf '%s' "$value" | gh secret set "$name" >/dev/null 2>&1; then
      WRITTEN_SECRET+=("$name")
      printf '  %s✓ set%s GitHub secret %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub secret $name (set it manually: gh secret set $name)")
  warn "skipped GitHub secret $name — gh not ready; set it later"
}

# set_var NAME VALUE — set a GitHub Actions repo variable (non-secret).
set_var() {
  local name="$1" value="$2"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if gh variable set "$name" --body "$value" >/dev/null 2>&1; then
      printf '  %s✓ set%s GitHub variable %s\n' "$GREEN" "$RESET" "$name"
      return
    fi
  fi
  SKIPPED+=("GitHub variable $name")
  warn "skipped GitHub variable $name — gh not ready; set it later"
}

# finish — clear, then a closing summary of everything configured.
finish() {
  _clear
  printf '\n%s%s  ✓ BAZspark Setup Complete%s\n' "$BOLD" "$GREEN" "$RESET"
  (( ${#WRITTEN_ENV[@]} ))    && note "wrote ${#WRITTEN_ENV[@]} value(s) to $ENV_FILE: ${WRITTEN_ENV[*]}"
  (( ${#WRITTEN_SECRET[@]} )) && note "set ${#WRITTEN_SECRET[@]} GitHub secret(s): ${WRITTEN_SECRET[*]}"
  if (( ${#SKIPPED[@]} )); then
    printf '\n'; warn "still to do by hand:"
    for s in "${SKIPPED[@]}"; do note "  - $s"; done
  fi
  printf '\n'
}

# Helper to generate cryptographic random string if python3 is present
gen_token_urlsafe() {
  local length="$1"
  python3 -c "import secrets; print(secrets.token_urlsafe($length))" 2>/dev/null || openssl rand -base64 "$length" 2>/dev/null || echo "fallback-token-$(date +%s%N)"
}

gen_token_hex() {
  local bytes="$1"
  python3 -c "import secrets; print(secrets.token_hex($bytes))" 2>/dev/null || openssl rand -hex "$bytes" 2>/dev/null || echo "fallback-hex-$(date +%s%N)"
}

# ──────────────────────────────────────────────────────────────────────────
# STAGES
# ──────────────────────────────────────────────────────────────────────────

TOTAL_STAGES=7

banner "BAZspark Unified Environment & Secrets Wizard"

# ── Stage 1: Runtime & Core Cryptographic Secrets ──
stage "Runtime Environment & Core Cryptographic Security Secrets"
say "Configuring execution mode, client API authentication, and cryptographic HMAC/AES keys."

ask FIREAI_ENV "Enter deployment environment (development / production) [default: development]:"
FIREAI_ENV="${FIREAI_ENV:-development}"
write_env FIREAI_ENV "$FIREAI_ENV"

# Generate or input FIREAI_API_KEY
DEF_API_KEY=$(gen_token_urlsafe 32)
ask_secret FIREAI_API_KEY "Paste or generate FIREAI_API_KEY (Enter generates new):"
FIREAI_API_KEY="${FIREAI_API_KEY:-$DEF_API_KEY}"
write_env FIREAI_API_KEY "$FIREAI_API_KEY"
set_secret FIREAI_API_KEY "$FIREAI_API_KEY"

# Generate or input FIREAI_SESSION_SECRET (min 43 chars)
DEF_SESSION_SEC=$(gen_token_urlsafe 64)
ask_secret FIREAI_SESSION_SECRET "Paste or generate FIREAI_SESSION_SECRET (min 43 chars, Enter generates 64-char):"
FIREAI_SESSION_SECRET="${FIREAI_SESSION_SECRET:-$DEF_SESSION_SEC}"
write_env FIREAI_SESSION_SECRET "$FIREAI_SESSION_SECRET"
set_secret FIREAI_SESSION_SECRET "$FIREAI_SESSION_SECRET"

# Cryptographic HMAC & Encryption Keys (Audit & QOMN Kernel)
DEF_AUDIT_HMAC=$(gen_token_hex 32)
ask_secret AUDIT_HMAC_KEY "Paste or generate AUDIT_HMAC_KEY (32-byte hex, Enter generates new):"
AUDIT_HMAC_KEY="${AUDIT_HMAC_KEY:-$DEF_AUDIT_HMAC}"
write_env AUDIT_HMAC_KEY "$AUDIT_HMAC_KEY"
set_secret AUDIT_HMAC_KEY "$AUDIT_HMAC_KEY"

DEF_QOMN_HMAC=$(gen_token_hex 32)
ask_secret FIREAI_QOMN_HMAC_KEY "Paste or generate FIREAI_QOMN_HMAC_KEY (32-byte hex, Enter generates new):"
FIREAI_QOMN_HMAC_KEY="${FIREAI_QOMN_HMAC_KEY:-$DEF_QOMN_HMAC}"
write_env FIREAI_QOMN_HMAC_KEY "$FIREAI_QOMN_HMAC_KEY"
set_secret FIREAI_QOMN_HMAC_KEY "$FIREAI_QOMN_HMAC_KEY"

DEF_QOMN_AUDIT=$(gen_token_urlsafe 32)
ask_secret QOMN_AUDIT_SECRET_KEY "Paste or generate QOMN_AUDIT_SECRET_KEY (Enter generates new):"
QOMN_AUDIT_SECRET_KEY="${QOMN_AUDIT_SECRET_KEY:-$DEF_QOMN_AUDIT}"
write_env QOMN_AUDIT_SECRET_KEY "$QOMN_AUDIT_SECRET_KEY"
set_secret QOMN_AUDIT_SECRET_KEY "$QOMN_AUDIT_SECRET_KEY"

DEF_ADMIN_TOKEN=$(gen_token_urlsafe 48)
ask_secret BAZSPARK_MASTER_ADMIN_TOKEN "Paste or generate BAZSPARK_MASTER_ADMIN_TOKEN (Enter generates new):"
BAZSPARK_MASTER_ADMIN_TOKEN="${BAZSPARK_MASTER_ADMIN_TOKEN:-$DEF_ADMIN_TOKEN}"
write_env BAZSPARK_MASTER_ADMIN_TOKEN "$BAZSPARK_MASTER_ADMIN_TOKEN"
set_secret BAZSPARK_MASTER_ADMIN_TOKEN "$BAZSPARK_MASTER_ADMIN_TOKEN"

DEF_ENC_KEY=$(gen_token_hex 32)
ask_secret FIREAI_VISION_KEY_ENCRYPTION_KEY "Paste or generate FIREAI_VISION_KEY_ENCRYPTION_KEY (32-byte hex):"
FIREAI_VISION_KEY_ENCRYPTION_KEY="${FIREAI_VISION_KEY_ENCRYPTION_KEY:-$DEF_ENC_KEY}"
write_env FIREAI_VISION_KEY_ENCRYPTION_KEY "$FIREAI_VISION_KEY_ENCRYPTION_KEY"
set_secret FIREAI_VISION_KEY_ENCRYPTION_KEY "$FIREAI_VISION_KEY_ENCRYPTION_KEY"

DEF_FDS_SEC=$(gen_token_hex 32)
ask_secret FDS_WEBHOOK_SECRET "Paste or generate FDS_WEBHOOK_SECRET (Enter generates new):"
FDS_WEBHOOK_SECRET="${FDS_WEBHOOK_SECRET:-$DEF_FDS_SEC}"
write_env FDS_WEBHOOK_SECRET "$FDS_WEBHOOK_SECRET"
set_secret FDS_WEBHOOK_SECRET "$FDS_WEBHOOK_SECRET"


# ── Stage 2: Database Layer (PostgreSQL / Supabase / SQLite) ──
stage "Database Layer (Supabase PostgreSQL / SQLite)"
say "Configuring database connection pooling and Supabase authentication tokens."
open_url "https://supabase.com/dashboard"
step "Select your project → Project Settings → Database (Connection String) and API (Keys)."

ask DATABASE_URL "Enter DATABASE_URL [default: sqlite:///./fireai.db]:"
DATABASE_URL="${DATABASE_URL:-sqlite:///./fireai.db}"
write_env DATABASE_URL "$DATABASE_URL"
set_secret DATABASE_URL "$DATABASE_URL"

ask SUPABASE_URL "Paste SUPABASE_URL (e.g. https://<project>.supabase.co):"
if [[ -n "$SUPABASE_URL" ]]; then
  write_env SUPABASE_URL "$SUPABASE_URL"
  set_secret SUPABASE_URL "$SUPABASE_URL"
  ask_secret SUPABASE_ANON_KEY "Paste SUPABASE_ANON_KEY:"
  if [[ -n "$SUPABASE_ANON_KEY" ]]; then
    write_env SUPABASE_ANON_KEY "$SUPABASE_ANON_KEY"
    set_secret SUPABASE_ANON_KEY "$SUPABASE_ANON_KEY"
  fi
  ask_secret SUPABASE_SERVICE_ROLE_KEY "Paste SUPABASE_SERVICE_ROLE_KEY:"
  if [[ -n "$SUPABASE_SERVICE_ROLE_KEY" ]]; then
    write_env SUPABASE_SERVICE_ROLE_KEY "$SUPABASE_SERVICE_ROLE_KEY"
    set_secret SUPABASE_SERVICE_ROLE_KEY "$SUPABASE_SERVICE_ROLE_KEY"
  fi
fi

ask NEON_DATABASE_URL "Paste NEON_DATABASE_URL (optional fallback DB, leave blank to skip):"
if [[ -n "$NEON_DATABASE_URL" ]]; then
  write_env NEON_DATABASE_URL "$NEON_DATABASE_URL"
  set_secret NEON_DATABASE_URL "$NEON_DATABASE_URL"
fi


# ── Stage 3: AI, LLMs & Observability ──
stage "AI Subsystems (Zenmux, Langfuse, NVIDIA, OpenAI/Gemini)"
say "Configuring primary LLM endpoints, observability tracing, and embedding models."

# Zenmux Primary LLM
open_url "https://zenmux.ai"
step "Log in to Zenmux → API Keys → copy your zm_... key."
ask_secret ZENMUX_API_KEY "Paste ZENMUX_API_KEY (leave blank to skip):"
if [[ -n "$ZENMUX_API_KEY" ]]; then
  write_env ZENMUX_API_KEY "$ZENMUX_API_KEY"
  write_env ZENMUX_BASE_URL "https://zenmux.ai/api/v1"
  write_env ZENMUX_MODEL "z-ai/glm-4.7-flash-free"
  set_secret ZENMUX_API_KEY "$ZENMUX_API_KEY"
fi

# Langfuse Observability
open_url "https://cloud.langfuse.com"
step "Project Settings → API Keys → copy Public and Secret keys."
ask LANGFUSE_PUBLIC_KEY "Paste LANGFUSE_PUBLIC_KEY (pk-lf-...):"
if [[ -n "$LANGFUSE_PUBLIC_KEY" ]]; then
  write_env LANGFUSE_PUBLIC_KEY "$LANGFUSE_PUBLIC_KEY"
  set_secret LANGFUSE_PUBLIC_KEY "$LANGFUSE_PUBLIC_KEY"
  ask_secret LANGFUSE_SECRET_KEY "Paste LANGFUSE_SECRET_KEY (sk-lf-...):"
  write_env LANGFUSE_SECRET_KEY "$LANGFUSE_SECRET_KEY"
  set_secret LANGFUSE_SECRET_KEY "$LANGFUSE_SECRET_KEY"
  write_env LANGFUSE_HOST "https://cloud.langfuse.com"
  write_env LANGFUSE_ENABLED "true"
fi

# NVIDIA / OpenAI / Gemini
ask_secret NVIDIA_API_KEY "Paste NVIDIA_API_KEY (build.nvidia.com, leave blank to skip):"
if [[ -n "$NVIDIA_API_KEY" ]]; then
  write_env NVIDIA_API_KEY "$NVIDIA_API_KEY"
  write_env NVIDIA_BASE_URL "https://integrate.api.nvidia.com/v1"
  write_env NVIDIA_MODEL "z-ai/glm-5.2"
  set_secret NVIDIA_API_KEY "$NVIDIA_API_KEY"
fi

ask_secret OPENAI_API_KEY "Paste OPENAI_API_KEY (Mem0 vector embeddings, leave blank to skip):"
if [[ -n "$OPENAI_API_KEY" ]]; then
  write_env OPENAI_API_KEY "$OPENAI_API_KEY"
  set_secret OPENAI_API_KEY "$OPENAI_API_KEY"
fi

ask_secret GEMINI_API_KEY "Paste GEMINI_API_KEY (fallback embeddings, leave blank to skip):"
if [[ -n "$GEMINI_API_KEY" ]]; then
  write_env GEMINI_API_KEY "$GEMINI_API_KEY"
  set_secret GEMINI_API_KEY "$GEMINI_API_KEY"
fi


# ── Stage 4: Autodesk APS & BIM Cloud Bridge ──
stage "Autodesk APS (Forge / Revit & AutoCAD Cloud Bridge)"
say "Configuring APS App credentials for DWG/RVT cloud translation and webhooks."
open_url "https://aps.autodesk.com/myapps"
step "Select your APS App → Copy Client ID & Client Secret."

ask APS_CLIENT_ID "Paste APS_CLIENT_ID (leave blank to skip):"
if [[ -n "$APS_CLIENT_ID" ]]; then
  write_env APS_CLIENT_ID "$APS_CLIENT_ID"
  set_secret APS_CLIENT_ID "$APS_CLIENT_ID"
  ask_secret APS_CLIENT_SECRET "Paste APS_CLIENT_SECRET:"
  write_env APS_CLIENT_SECRET "$APS_CLIENT_SECRET"
  set_secret APS_CLIENT_SECRET "$APS_CLIENT_SECRET"
  write_env APS_CLIENT_NAME "bazspark"
  ask APS_WEBHOOK_URL "Paste APS_WEBHOOK_URL [default: https://api.bazspark.example/api/v2/aps/webhook]:"
  APS_WEBHOOK_URL="${APS_WEBHOOK_URL:-https://api.bazspark.example/api/v2/aps/webhook}"
  write_env APS_WEBHOOK_URL "$APS_WEBHOOK_URL"
  set_secret APS_WEBHOOK_URL "$APS_WEBHOOK_URL"
fi


# ── Stage 5: Communications, Storage & Meeza Payment Gateway ──
stage "Communications, Storage & Meeza Payment Gateway"
say "Configuring transactional emails (Resend), Cloud Box storage, and Egyptian Meeza billing."

# Resend
open_url "https://resend.com/api-keys"
step "API Keys → Create API Key → Copy token (starts with re_)."
ask_secret RESEND_API_KEY "Paste RESEND_API_KEY (leave blank to skip):"
if [[ -n "$RESEND_API_KEY" ]]; then
  write_env RESEND_API_KEY "$RESEND_API_KEY"
  write_env RESEND_FROM_EMAIL "BAZspark <onboarding@resend.dev>"
  set_secret RESEND_API_KEY "$RESEND_API_KEY"
fi

# Box
ask_secret BOX_DEVELOPER_TOKEN "Paste BOX_DEVELOPER_TOKEN (leave blank to skip):"
if [[ -n "$BOX_DEVELOPER_TOKEN" ]]; then
  write_env BOX_DEVELOPER_TOKEN "$BOX_DEVELOPER_TOKEN"
  set_secret BOX_DEVELOPER_TOKEN "$BOX_DEVELOPER_TOKEN"
fi

# Meeza Payment Gateway
open_url "https://accept.paymob.com/portal2/en/settings"
step "Settings → Account Info & Payment Integrations (Meeza ID)."
ask MEEZA_PSP_PROVIDER "Enter MEEZA_PSP_PROVIDER (sandbox / paymob / fawry / nbe) [default: sandbox]:"
MEEZA_PSP_PROVIDER="${MEEZA_PSP_PROVIDER:-sandbox}"
write_env MEEZA_PSP_PROVIDER "$MEEZA_PSP_PROVIDER"

DEF_MEEZA_HMAC=$(gen_token_hex 32)
ask_secret MEEZA_WEBHOOK_HMAC_SECRET "Paste or generate MEEZA_WEBHOOK_HMAC_SECRET (Enter generates new):"
MEEZA_WEBHOOK_HMAC_SECRET="${MEEZA_WEBHOOK_HMAC_SECRET:-$DEF_MEEZA_HMAC}"
write_env MEEZA_WEBHOOK_HMAC_SECRET "$MEEZA_WEBHOOK_HMAC_SECRET"
set_secret MEEZA_WEBHOOK_HMAC_SECRET "$MEEZA_WEBHOOK_HMAC_SECRET"

if [[ "$MEEZA_PSP_PROVIDER" == "paymob" ]]; then
  ask_secret MEEZA_PSP_API_KEY "Paste PayMob MEEZA_PSP_API_KEY:"
  if [[ -n "$MEEZA_PSP_API_KEY" ]]; then
    write_env MEEZA_PSP_API_KEY "$MEEZA_PSP_API_KEY"
    set_secret MEEZA_PSP_API_KEY "$MEEZA_PSP_API_KEY"
  fi
  ask MEEZA_MERCHANT_ID "Paste MEEZA_MERCHANT_ID:"
  if [[ -n "$MEEZA_MERCHANT_ID" ]]; then
    write_env MEEZA_MERCHANT_ID "$MEEZA_MERCHANT_ID"
    set_secret MEEZA_MERCHANT_ID "$MEEZA_MERCHANT_ID"
  fi
  ask MEEZA_PAYMOB_INTEGRATION_ID "Paste MEEZA_PAYMOB_INTEGRATION_ID (from Meeza payment method):"
  if [[ -n "$MEEZA_PAYMOB_INTEGRATION_ID" ]]; then
    write_env MEEZA_PAYMOB_INTEGRATION_ID "$MEEZA_PAYMOB_INTEGRATION_ID"
    set_secret MEEZA_PAYMOB_INTEGRATION_ID "$MEEZA_PAYMOB_INTEGRATION_ID"
  fi
fi


# ── Stage 6: Cloud Deployments (Hugging Face Spaces & Vercel) ──
stage "Cloud Deployment Platforms (Hugging Face & Vercel)"
say "Configuring tokens for automated backend (HF Spaces) and frontend (Vercel) deployments."

# Hugging Face Space
open_url "https://huggingface.co/settings/tokens"
step "Create/Copy Access Token with 'write' permissions (starts with hf_)."
ask_secret HF_TOKEN "Paste HF_TOKEN (leave blank to skip):"
if [[ -n "$HF_TOKEN" ]]; then
  write_env HF_TOKEN "$HF_TOKEN"
  set_secret HF_TOKEN "$HF_TOKEN"
  write_env HF_USERNAME "ahmdelbaz28"
  write_env HF_SPACE_NAME "BAZSPARK"
  write_env HF_SPACE_REPO "https://huggingface.co/spaces/ahmdelbaz28/BAZSPARK"
fi

# Vercel
open_url "https://vercel.com/account/tokens"
step "Create/Copy Vercel Personal Access Token (starts with vcp_)."
ask_secret VERCEL_DEPLOY_TOKEN "Paste VERCEL_DEPLOY_TOKEN (leave blank to skip):"
if [[ -n "$VERCEL_DEPLOY_TOKEN" ]]; then
  write_env VERCEL_DEPLOY_TOKEN "$VERCEL_DEPLOY_TOKEN"
  set_secret VERCEL_DEPLOY_TOKEN "$VERCEL_DEPLOY_TOKEN"
  ask VERCEL_PROJECT_ID "Paste VERCEL_PROJECT_ID (from Project Settings):"
  if [[ -n "$VERCEL_PROJECT_ID" ]]; then
    write_env VERCEL_PROJECT_ID "$VERCEL_PROJECT_ID"
    set_secret VERCEL_PROJECT_ID "$VERCEL_PROJECT_ID"
  fi
  ask VERCEL_TEAM_ID "Paste VERCEL_TEAM_ID (optional, leave blank for personal):"
  if [[ -n "$VERCEL_TEAM_ID" ]]; then
    write_env VERCEL_TEAM_ID "$VERCEL_TEAM_ID"
    set_secret VERCEL_TEAM_ID "$VERCEL_TEAM_ID"
  fi
fi


# ── Stage 7: CI/CD Quality Gates & Security (GitHub, SonarCloud, Cloudflare) ──
stage "CI/CD Gates & Edge Security (GitHub Actions, SonarCloud, Cloudflare)"
say "Configuring automated secret synchronization, code quality analysis, and edge WAF."

# GitHub PAT (Fine-grained token for repo secret pushing)
open_url "https://github.com/settings/tokens?type=beta"
step "Create fine-grained PAT with repository 'Secrets' write access."
ask_secret GH_PAT "Paste GH_PAT (leave blank to skip):"
if [[ -n "$GH_PAT" ]]; then
  write_env GH_PAT "$GH_PAT"
  write_env GH_REPO "ahmdelbaz28-ux/BAZspark"
  write_env GH_DEFAULT_BRANCH "main"
  note "GH_PAT saved locally in $ENV_FILE. (GH_PAT is NOT pushed as a repo secret for safety)."
fi

# SonarCloud
open_url "https://sonarcloud.io/account/security"
step "Generate/Copy SonarCloud User Token."
ask_secret SONAR_TOKEN "Paste SONAR_TOKEN (leave blank to skip):"
if [[ -n "$SONAR_TOKEN" ]]; then
  write_env SONAR_TOKEN "$SONAR_TOKEN"
  set_secret SONAR_TOKEN "$SONAR_TOKEN"
  write_env SONAR_ORGANIZATION "ahmdelbaz28-ux"
  write_env SONAR_PROJECT_KEY "ahmdelbaz28-ux_revit"
  write_env SONAR_HOST_URL "https://sonarcloud.io"
fi

# Cloudflare
ask_secret CLOUDFLARE_API_TOKEN "Paste CLOUDFLARE_API_TOKEN (leave blank to skip):"
if [[ -n "$CLOUDFLARE_API_TOKEN" ]]; then
  write_env CLOUDFLARE_API_TOKEN "$CLOUDFLARE_API_TOKEN"
  set_secret CLOUDFLARE_API_TOKEN "$CLOUDFLARE_API_TOKEN"
fi

# CORS Origins & Trusted Proxies
ask CORS_ORIGINS "Enter comma-separated CORS_ORIGINS [default: http://localhost:5173,http://localhost:3000,http://localhost:8000]:"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://localhost:3000,http://localhost:8000}"
write_env CORS_ORIGINS "$CORS_ORIGINS"
set_secret CORS_ORIGINS "$CORS_ORIGINS"

ask TRUSTED_PROXIES "Enter TRUSTED_PROXIES CIDRs [default: 127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16]:"
TRUSTED_PROXIES="${TRUSTED_PROXIES:-127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}"
write_env TRUSTED_PROXIES "$TRUSTED_PROXIES"
set_secret TRUSTED_PROXIES "$TRUSTED_PROXIES"

# Optional: Run python scripts/set_github_secrets.py if GH_PAT is present
if [[ -n "${GH_PAT:-}" ]] && command -v python3 >/dev/null 2>&1; then
  if confirm "Would you like to sync all configured secrets directly to GitHub Actions now via scripts/set_github_secrets.py?"; then
    say "Running python3 scripts/set_github_secrets.py..."
    python3 scripts/set_github_secrets.py || warn "Failed to sync secrets to GitHub Actions automatically. Run scripts/set_github_secrets.py manually."
  fi
fi

finish
