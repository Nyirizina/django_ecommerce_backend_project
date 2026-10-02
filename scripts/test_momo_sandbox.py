#!/usr/bin/env python
"""
scripts/test_momo_sandbox.py
────────────────────────────────────────────────────────────────────────────
End-to-end sandbox test script for MTN MoMo Collections.

Runs OUTSIDE of Django — no server needed. Uses requests directly.

USAGE:
  1. Copy .env.example to .env and fill in:
       MOMO_SUBSCRIPTION_KEY=<from momodeveloper.mtn.com>
       MOMO_BASE_URL=https://sandbox.momodeveloper.mtn.com
       MOMO_TARGET_ENVIRONMENT=sandbox
       MOMO_CURRENCY=EUR

  2. Run:
       python scripts/test_momo_sandbox.py

  3. The script will:
       a) Provision a new API User (UUID) and API Key in the sandbox
       b) Request a Bearer token
       c) Initiate a requestToPay to the sandbox test MSISDN (auto-succeeds)
       d) Poll status until SUCCESSFUL (or max 12 attempts)
       e) Print the financial transaction ID on success

SANDBOX TEST MSISDNs (always respond predictably):
  56733123453  →  SUCCESSFUL
  46733123454  →  PENDING (stays pending)
  46733123450  →  FAILED

REQUIREMENTS:
  pip install requests python-dotenv
"""

import sys
import os
import time
import uuid
import base64

# Force UTF-8 output on Windows to avoid cp1252 UnicodeEncodeError
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load .env from project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, '.env'))
except ImportError:
    pass  # dotenv optional; set env vars manually if missing

import requests

BASE_URL    = os.environ.get('MOMO_BASE_URL', 'https://sandbox.momodeveloper.mtn.com').rstrip('/')
SUB_KEY     = os.environ.get('MOMO_SUBSCRIPTION_KEY', '')
TARGET_ENV  = os.environ.get('MOMO_TARGET_ENVIRONMENT', 'sandbox')
CURRENCY    = os.environ.get('MOMO_CURRENCY', 'EUR')

# Sandbox test MSISDN that always returns SUCCESSFUL
TEST_MSISDN = '56733123453'
TEST_AMOUNT = '100'

BOLD  = '\033[1m'
GREEN = '\033[92m'
RED   = '\033[91m'
CYAN  = '\033[96m'
RESET = '\033[0m'

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}"); sys.exit(1)
def info(msg): print(f"  {CYAN}→{RESET} {msg}")


def step(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def provision_user():
    """POST /v1_0/apiuser — create a new sandbox API User."""
    step("Step 1: Provision Sandbox API User")
    if not SUB_KEY:
        fail("MOMO_SUBSCRIPTION_KEY is not set. Check your .env file.")

    api_user_id = str(uuid.uuid4())
    info(f"Generated api_user UUID: {api_user_id}")

    url = f"{BASE_URL}/v1_0/apiuser"
    headers = {
        'X-Reference-Id': api_user_id,
        'Ocp-Apim-Subscription-Key': SUB_KEY,
        'Content-Type': 'application/json',
    }
    resp = requests.post(url, headers=headers, json={'providerCallbackHost': 'webhook.site'}, timeout=15)

    if resp.status_code == 201:
        ok(f"API User created: {api_user_id}")
        return api_user_id
    else:
        fail(f"Failed to provision user: HTTP {resp.status_code} — {resp.text}")


def provision_api_key(api_user_id):
    """POST /v1_0/apiuser/{id}/apikey — generate API Key."""
    step("Step 2: Generate API Key")
    url = f"{BASE_URL}/v1_0/apiuser/{api_user_id}/apikey"
    headers = {'Ocp-Apim-Subscription-Key': SUB_KEY}
    resp = requests.post(url, headers=headers, timeout=15)

    if resp.status_code == 201:
        api_key = resp.json()['apiKey']
        ok(f"API Key generated: {api_key[:8]}…")
        return api_key
    else:
        fail(f"Failed to generate API Key: HTTP {resp.status_code} — {resp.text}")


def get_token(api_user_id, api_key):
    """POST /collection/token/ — get Bearer token."""
    step("Step 3: Request Bearer Token")
    credentials = f"{api_user_id}:{api_key}"
    encoded = base64.b64encode(credentials.encode()).decode()

    url = f"{BASE_URL}/collection/token/"
    headers = {
        'Authorization': f'Basic {encoded}',
        'Ocp-Apim-Subscription-Key': SUB_KEY,
    }
    resp = requests.post(url, headers=headers, timeout=15)

    if resp.status_code == 200:
        token = resp.json()['access_token']
        ok(f"Bearer token acquired: {token[:12]}…")
        return token
    else:
        fail(f"Token request failed: HTTP {resp.status_code} — {resp.text}")


def request_to_pay(token):
    """POST /collection/v1_0/requesttopay"""
    step("Step 4: Initiate Request To Pay")
    reference_id = str(uuid.uuid4())
    info(f"Reference ID: {reference_id}")
    info(f"MSISDN: {TEST_MSISDN}  (sandbox — always SUCCESSFUL)")
    info(f"Amount: {TEST_AMOUNT} {CURRENCY}")

    url = f"{BASE_URL}/collection/v1_0/requesttopay"
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Reference-Id': reference_id,
        'X-Target-Environment': TARGET_ENV,
        'Ocp-Apim-Subscription-Key': SUB_KEY,
        'Content-Type': 'application/json',
    }
    payload = {
        'amount': TEST_AMOUNT,
        'currency': CURRENCY,
        'externalId': 'SANDBOX-TEST-001',
        'payer': {'partyIdType': 'MSISDN', 'partyId': TEST_MSISDN},
        'payerMessage': 'Sandbox test payment',
        'payeeNote': 'Sandbox test',
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)

    if resp.status_code == 202:
        ok("requestToPay accepted (HTTP 202)")
        return reference_id, token
    else:
        fail(f"requestToPay failed: HTTP {resp.status_code} — {resp.text}")


def poll_status(reference_id, token, max_attempts=12):
    """GET /collection/v1_0/requesttopay/{referenceId} — poll until terminal."""
    step("Step 5: Poll Payment Status")
    url = f"{BASE_URL}/collection/v1_0/requesttopay/{reference_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Target-Environment': TARGET_ENV,
        'Ocp-Apim-Subscription-Key': SUB_KEY,
    }

    for attempt in range(1, max_attempts + 1):
        info(f"Poll attempt {attempt}/{max_attempts}…")
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            print(f"     HTTP {resp.status_code}: {resp.text}")
            time.sleep(5)
            continue

        data   = resp.json()
        status = data.get('status', 'UNKNOWN')
        print(f"     Status: {BOLD}{status}{RESET}")

        if status == 'SUCCESSFUL':
            fin_id = data.get('financialTransactionId', 'N/A')
            ok(f"Payment SUCCESSFUL 🎉")
            ok(f"Financial Transaction ID: {fin_id}")
            return data
        elif status in ('FAILED', 'REJECTED', 'TIMEOUT'):
            fail(f"Payment terminal failure: {status} — {data.get('reason', '')}")
        else:
            time.sleep(5)

    fail(f"Max poll attempts reached without terminal status.")


def simulate_callback(reference_id, financial_tx_id):
    """Print the simulated callback body that MTN would POST to your endpoint."""
    step("Step 6: Simulated MoMo Callback Body")
    print("  MTN would POST this JSON to /payment/momo/callback/:")
    import json
    body = {
        "referenceId": reference_id,
        "status": "SUCCESSFUL",
        "financialTransactionId": financial_tx_id,
        "amount": TEST_AMOUNT,
        "currency": CURRENCY,
        "payer": {"partyIdType": "MSISDN", "partyId": TEST_MSISDN},
    }
    print(json.dumps(body, indent=4))
    ok("Your momo_callback view would receive this, look up the MoMoTransaction")
    ok("by reference_id, verify it's not already terminal, then call _finalize_order_from_shipping()")


def _update_env_file(api_user_id: str, api_key: str):
    """
    Auto-save provisioned MOMO_API_USER and MOMO_API_KEY into the .env file
    so the user doesn't have to copy-paste them manually.
    """
    env_path = os.path.join(ROOT, '.env')
    if not os.path.isfile(env_path):
        info(f".env not found at {env_path} — skipping auto-save.")
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('MOMO_API_USER='):
            lines[i] = f'MOMO_API_USER={api_user_id}\n'
            updated = True
        elif stripped.startswith('MOMO_API_KEY='):
            lines[i] = f'MOMO_API_KEY={api_key}\n'
            updated = True

    if updated:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        ok(f"Credentials auto-saved to {env_path}")
    else:
        info("MOMO_API_USER / MOMO_API_KEY lines not found in .env — add them manually.")


if __name__ == '__main__':
    print(f"\n{BOLD}MTN MoMo Sandbox End-to-End Test{RESET}")
    print(f"Base URL: {BASE_URL}  |  Environment: {TARGET_ENV}  |  Currency: {CURRENCY}\n")

    api_user_id = provision_user()
    api_key     = provision_api_key(api_user_id)

    # Auto-save provisioned credentials to .env
    _update_env_file(api_user_id, api_key)

    token       = get_token(api_user_id, api_key)
    ref_id, tok = request_to_pay(token)
    data        = poll_status(ref_id, tok)
    fin_id      = data.get('financialTransactionId', 'sandbox-fin-id')
    simulate_callback(ref_id, fin_id)

    print(f"\n{BOLD}{GREEN}All sandbox tests passed ✓{RESET}\n")
    print("Credentials have been auto-saved to your .env file:")
    print(f"  MOMO_API_USER={api_user_id}")
    print(f"  MOMO_API_KEY={api_key[:8]}…(saved in .env)")
    print()
