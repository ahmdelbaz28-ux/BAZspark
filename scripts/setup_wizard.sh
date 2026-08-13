#!/usr/bin/env bash
#
# BAZspark Interactive Setup Wizard — walks a human through environment and secret configuration.
# Generated via /wizard skill.
#

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

TOTAL_STAGES=5

_STAGE_INDEX=0
ENV_FILE="${ENV_FILE:-.env}"
WRITTEN_ENV=()    # KEYs written to ENV_FILE this run
WRITTEN_SECRET=() # secret NAMEs set this run
SKIPPED=()        # things we couldn't do (e.g. gh missing)

# _clear — wipe the terminal so only the current step is on screen.
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

# stage "Name" — clear screen & show progress.
stage() {
  _clear
  _STAGE_INDEX=$((_STAGE_INDEX + 1))
  printf '\n%s%s▸ Stage %s/%s · %s%s\n' \
    "$BOLD" "$BLUE" "$_STAGE_INDEX" "$TOTAL_STAGES" "$1" "$RESET"
}

say()  { printf '  %s\n' "$1"; }
step() { printf '  %s•%s %s\n' "$BLUE" "$RESET" "$1"; }
note() { printf '  %s%s%s\n' "$DIM" "$1" "$RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$YELLOW" "$1" "$RESET"; }

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

pause() {
  printf '  %s%s%s ' "$DIM" "${1:-Press Enter to continue}" "$RESET"
  read -r _ || true
}

confirm() {
  local reply=""
  printf '  %s? %s [y/N] ' "$YELLOW" "$1"
  read -r reply || true
  [[ "$reply" =~ ^[Yy] ]]
}

_existing() {
  [[ -f "$ENV_FILE" ]] || return 1
  local line; line=$(grep -E "^${1}=" "$ENV_FILE" | tail -n1) || return 1
  printf '%s' "${line#*=}"
}

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

# ──────────────────────────────────────────────────────────────────────────
# STAGES
# ──────────────────────────────────────────────────────────────────────────

banner "BAZspark Interactive Environment & Secrets Wizard"

# ── Stage 1: Runtime & Core Security Secrets ──
stage "Runtime Environment & Core Security Secrets"
say "Configuring core environment flags and session security secret."
ask FIREAI_ENV "Enter environment (development/production) [default: development]:"
FIREAI_ENV="${FIREAI_ENV:-development}"

# Generate default session secret if not set
DEFAULT_SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))" 2>/dev/null || echo "dev-session-secret-64-chars-minimum-bazspark-default-token")
ask_secret FIREAI_SESSION_SECRET "Paste/enter FIREAI_SESSION_SECRET (Enter uses generated secure token):"
FIREAI_SESSION_SECRET="${FIREAI_SESSION_SECRET:-$DEFAULT_SESSION_SECRET}"

write_env FIREAI_ENV "$FIREAI_ENV"
write_env FIREAI_SESSION_SECRET "$FIREAI_SESSION_SECRET"

# ── Stage 2: Zenmux LLM Integration ──
stage "Zenmux LLM Subsystem Setup"
say "Configuring the primary Chat LLM key for /api/v1/llm/chat."
open_url "https://zenmux.ai"
step "Copy your Zenmux API key (starts with zm_)."
ask_secret ZENMUX_API_KEY "Paste your ZENMUX_API_KEY (leave blank to skip):"

if [[ -n "$ZENMUX_API_KEY" ]]; then
  write_env ZENMUX_API_KEY "$ZENMUX_API_KEY"
  write_env ZENMUX_BASE_URL "https://zenmux.ai/api/v1"
  write_env ZENMUX_MODEL "z-ai/glm-4.7-flash-free"
  set_secret ZENMUX_API_KEY "$ZENMUX_API_KEY"
else
  warn "Skipping ZENMUX_API_KEY — chat endpoints will return 503 until set."
fi

# ── Stage 3: Supabase Authentication & Database ──
stage "Supabase Auth & Database Credentials"
say "Configuring Supabase database and authentication service role keys."
open_url "https://supabase.com/dashboard"
step "Select your project → Project Settings → API."
ask SUPABASE_URL "Paste SUPABASE_URL (https://YOUR_PROJECT.supabase.co):"
ask_secret SUPABASE_ANON_KEY "Paste SUPABASE_ANON_KEY:"
ask_secret SUPABASE_SERVICE_ROLE_KEY "Paste SUPABASE_SERVICE_ROLE_KEY:"

if [[ -n "$SUPABASE_URL" ]]; then
  write_env SUPABASE_URL "$SUPABASE_URL"
  write_env SUPABASE_ANON_KEY "$SUPABASE_ANON_KEY"
  write_env SUPABASE_SERVICE_ROLE_KEY "$SUPABASE_SERVICE_ROLE_KEY"
  set_secret SUPABASE_ANON_KEY "$SUPABASE_ANON_KEY"
  set_secret SUPABASE_SERVICE_ROLE_KEY "$SUPABASE_SERVICE_ROLE_KEY"
else
  warn "Skipping Supabase setup."
fi

# ── Stage 4: Resend Email & Box Integration ──
stage "Resend Email & Box Cloud Integration"
say "Configuring email notifications and cloud storage integrations."
open_url "https://resend.com/api-keys"
step "Create/Copy your Resend API key (starts with re_)."
ask_secret RESEND_API_KEY "Paste RESEND_API_KEY (leave blank to skip):"

if [[ -n "$RESEND_API_KEY" ]]; then
  write_env RESEND_API_KEY "$RESEND_API_KEY"
  write_env RESEND_FROM_EMAIL "BAZspark <onboarding@resend.dev>"
  set_secret RESEND_API_KEY "$RESEND_API_KEY"
fi

ask_secret BOX_DEVELOPER_TOKEN "Paste BOX_DEVELOPER_TOKEN (leave blank to skip):"
if [[ -n "$BOX_DEVELOPER_TOKEN" ]]; then
  write_env BOX_DEVELOPER_TOKEN "$BOX_DEVELOPER_TOKEN"
fi

# ── Stage 5: Hugging Face & Vercel Deployment Secrets ──
stage "Deployment Secrets (HuggingFace & Vercel)"
say "Configuring deployment tokens for automated CI/CD pushes."
open_url "https://huggingface.co/settings/tokens"
step "Copy your HuggingFace User Access Token (starts with hf_)."
ask_secret HF_TOKEN "Paste HF_TOKEN (leave blank to skip):"

if [[ -n "$HF_TOKEN" ]]; then
  write_env HF_TOKEN "$HF_TOKEN"
  set_secret HF_TOKEN "$HF_TOKEN"
fi

open_url "https://vercel.com/account/tokens"
step "Copy your Vercel Access Token (starts with vcp_)."
ask_secret VERCEL_DEPLOY_TOKEN "Paste VERCEL_DEPLOY_TOKEN (leave blank to skip):"

if [[ -n "$VERCEL_DEPLOY_TOKEN" ]]; then
  write_env VERCEL_DEPLOY_TOKEN "$VERCEL_DEPLOY_TOKEN"
  set_secret VERCEL_DEPLOY_TOKEN "$VERCEL_DEPLOY_TOKEN"
fi

finish
