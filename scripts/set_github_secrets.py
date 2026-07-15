import base64
import os

import requests
from dotenv import load_dotenv
from nacl import public

# Load .env file
load_dotenv()

# GitHub Configuration
GH_PAT = os.environ.get("GH_PAT")
GH_REPO = os.environ.get("GH_REPO", "ahmdelbaz28-ux/BAZspark")
API_URL = f"https://api.github.com/repos/{GH_REPO}/actions/secrets"

# Secret values to be pushed to GitHub Action Secrets (read from .env/env)
secrets_to_set = {
    "DAYTONA_API_TOKEN": os.environ.get("DAYTONA_API_TOKEN"),
    "HF_TOKEN": os.environ.get("HF_TOKEN"),
    "VERCEL_DEPLOY_TOKEN": os.environ.get("VERCEL_DEPLOY_TOKEN"),
    "VERCEL_DEPLOY_HOOK_TOKEN": os.environ.get("VERCEL_DEPLOY_TOKEN"),
    "VERCEL_PROJECT_ID": os.environ.get("VERCEL_PROJECT_ID"),
    "SUPABASE_SERVICE_ROLE_KEY": os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
}

def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key_bytes = base64.b64decode(public_key)
    pub_key = public.PublicKey(public_key_bytes)
    sealed_box = public.SealedBox(pub_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def main():
    if not GH_PAT:
        print("Error: GH_PAT environment variable is not set.")
        return

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GH_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"
    }

    print(f"Fetching GitHub Actions public key for {GH_REPO}...")
    resp = requests.get(f"{API_URL}/public-key", headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch public key: HTTP {resp.status_code} {resp.text}")
        return

    key_data = resp.json()
    key_id = key_data["key_id"]
    public_key = key_data["key"]
    print("Public key fetched successfully.")

    for name, value in secrets_to_set.items():
        if not value:
            print(f"Skipping {name} (no value found in environment)")
            continue

        print(f"Encrypting and pushing secret {name}...")
        encrypted_value = encrypt(public_key, value)

        payload = {
            "encrypted_value": encrypted_value,
            "key_id": key_id
        }

        put_url = f"{API_URL}/{name}"
        put_resp = requests.put(put_url, headers=headers, json=payload)

        if put_resp.status_code in (201, 204):
            print(f"SUCCESS: Secret {name} set successfully (HTTP {put_resp.status_code})")
        else:
            print(f"FAILED: Failed to set secret {name}: HTTP {put_resp.status_code} {put_resp.text}")

if __name__ == "__main__":
    main()
