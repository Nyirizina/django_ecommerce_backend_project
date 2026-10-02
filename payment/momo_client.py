"""
payment/momo_client.py
─────────────────────────────────────────────────────────────────────────────
Low-level MTN MoMo Collections API client.

Handles:
  • Sandbox provisioning  (create API User + API Key)
  • OAuth 2.0 token generation (cached until expiry)
  • Request To Pay initiation
  • Payment status polling

All network errors are raised as MoMoError (a subclass of Exception) so
callers can decide how to surface them.

Usage (production/sandbox identical except for MOMO_TARGET_ENVIRONMENT):
    from payment.momo_client import MoMoClient
    client = MoMoClient()
    ref_id = client.request_to_pay(
        amount="1000",
        phone="250781234567",
        external_id="ORD-001",
        payer_message="Payment for order ORD-001",
        payee_note="ORD-001",
        callback_url="https://yourdomain.com/payment/momo/callback/",
    )
    status = client.get_payment_status(ref_id)
"""

import uuid
import base64
import time
import logging
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


# ── Custom Exception ──────────────────────────────────────────────────────────

class MoMoError(Exception):
    """Raised for any MTN MoMo API error."""

    def __init__(self, message: str, status_code: int = None, response_body: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}

    def __str__(self):
        base = super().__str__()
        if self.status_code:
            return f"[HTTP {self.status_code}] {base}"
        return base


# ── MoMo Client ───────────────────────────────────────────────────────────────

class MoMoClient:
    """
    Stateful MTN MoMo Collections API client.

    Credentials are read from Django settings (populated from .env):
        MOMO_BASE_URL             - https://sandbox.momodeveloper.mtn.com
        MOMO_SUBSCRIPTION_KEY     - Ocp-Apim-Subscription-Key from developer portal
        MOMO_API_USER             - UUID provisioned via /v1_0/apiuser (sandbox only)
        MOMO_API_KEY              - Key generated via /v1_0/apiuser/{id}/apikey
        MOMO_TARGET_ENVIRONMENT   - "sandbox" | "mtnrwanda" | "mtnuganda" etc.
        MOMO_CURRENCY             - "EUR" for sandbox; "RWF" for Rwanda production
    """

    def __init__(self):
        self.base_url         = settings.MOMO_BASE_URL.strip().rstrip('/')
        self.subscription_key = settings.MOMO_SUBSCRIPTION_KEY.strip()
        self.api_user         = settings.MOMO_API_USER.strip()
        self.api_key          = settings.MOMO_API_KEY.strip()
        self.target_env       = settings.MOMO_TARGET_ENVIRONMENT.strip()
        self.currency         = settings.MOMO_CURRENCY.strip()

        # Fail fast: raise a clear error naming any missing required variable
        # so misconfiguration surfaces at instantiation, not at the first HTTP call.
        _required = {
            'MOMO_SUBSCRIPTION_KEY':   self.subscription_key,
            'MOMO_API_USER':           self.api_user,
            'MOMO_API_KEY':            self.api_key,
            'MOMO_BASE_URL':           self.base_url,
            'MOMO_TARGET_ENVIRONMENT': self.target_env,
        }
        missing = [name for name, val in _required.items() if not val]
        if missing:
            raise ImproperlyConfigured(
                f"MTN MoMo: required setting(s) are empty or missing: "
                f"{', '.join(missing)}. Check your .env file."
            )

        # Token cache: (access_token_str, expiry_epoch_float)
        self._token_cache: tuple[str, float] | None = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _subscription_headers(self) -> dict:
        return {
            'Ocp-Apim-Subscription-Key': self.subscription_key,
            'Content-Type': 'application/json',
        }

    def _auth_headers(self) -> dict:
        """Returns headers including a fresh Bearer token."""
        return {
            'Authorization': f'Bearer {self._get_token()}',
            'X-Target-Environment': self.target_env,
            'Ocp-Apim-Subscription-Key': self.subscription_key,
            'Content-Type': 'application/json',
        }

    def _raise_for_status(self, response: requests.Response, context: str):
        """Raise MoMoError with a helpful message if the response is not 2xx."""
        if not response.ok:
            try:
                body = response.json()
            except Exception:
                body = {'raw': response.text}
            logger.error(
                "MoMo API error [%s]: HTTP %s — %s",
                context, response.status_code, body
            )
            raise MoMoError(
                f"{context} failed: {body.get('message', response.text)}",
                status_code=response.status_code,
                response_body=body,
            )

    # ── Token management ──────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """
        Returns a valid Bearer token, requesting a new one if the cached token
        is missing or within 60 seconds of expiry.
        """
        now = time.time()
        if self._token_cache:
            token, expiry = self._token_cache
            if now < expiry - 60:          # 60-second safety margin
                return token

        return self._request_token()

    def _request_token(self) -> str:
        """POST /collection/token/ with Basic Auth to get a new Bearer token."""
        credentials = f"{self.api_user}:{self.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()

        url = f"{self.base_url}/collection/token/"
        headers = {
            'Authorization': f'Basic {encoded}',
            'Ocp-Apim-Subscription-Key': self.subscription_key,
        }

        try:
            response = requests.post(url, headers=headers, timeout=15)
        except requests.RequestException as exc:
            raise MoMoError(f"Token request network error: {exc}") from exc

        self._raise_for_status(response, "Token generation")

        data = response.json()
        access_token = data['access_token']
        expires_in   = int(data.get('expires_in', 3600))

        self._token_cache = (access_token, time.time() + expires_in)
        logger.info("MoMo: New Bearer token acquired (expires in %ds)", expires_in)
        return access_token

    # ── Sandbox Provisioning (sandbox only) ───────────────────────────────────

    def provision_sandbox_user(self, callback_host: str = "webhook.site") -> str:
        """
        Creates a new API User in the sandbox and returns the api_user UUID.
        Call this once during initial setup; not needed in production.

        Args:
            callback_host: The host (no scheme) MoMo will use for callbacks,
                           e.g. "yourdomain.com"

        Returns:
            The api_user UUID string (save this as MOMO_API_USER in .env).
        """
        api_user_id = str(uuid.uuid4())
        url = f"{self.base_url}/v1_0/apiuser"
        headers = {
            'X-Reference-Id': api_user_id,
            **self._subscription_headers(),
        }
        body = {'providerCallbackHost': callback_host}

        try:
            response = requests.post(url, headers=headers, json=body, timeout=15)
        except requests.RequestException as exc:
            raise MoMoError(f"Provision user network error: {exc}") from exc

        self._raise_for_status(response, "Sandbox user provisioning")
        logger.info("MoMo sandbox: API User created → %s", api_user_id)
        return api_user_id

    def provision_sandbox_api_key(self, api_user_id: str) -> str:
        """
        Generates an API Key for an existing sandbox API User.
        Call this once after provision_sandbox_user().

        Args:
            api_user_id: The UUID returned by provision_sandbox_user().

        Returns:
            The api_key string (save this as MOMO_API_KEY in .env).
        """
        url = f"{self.base_url}/v1_0/apiuser/{api_user_id}/apikey"
        headers = {
            'Ocp-Apim-Subscription-Key': self.subscription_key,
        }

        try:
            response = requests.post(url, headers=headers, timeout=15)
        except requests.RequestException as exc:
            raise MoMoError(f"Provision API key network error: {exc}") from exc

        self._raise_for_status(response, "Sandbox API key generation")
        api_key = response.json()['apiKey']
        logger.info("MoMo sandbox: API Key generated for user %s", api_user_id)
        return api_key

    # ── Collections API ───────────────────────────────────────────────────────

    def normalize_phone(self, phone: str) -> str:
        """
        Normalise a Rwandan (or other) phone number to MSISDN format
        (international digits only, no + or spaces).

        Rwandan numbers:
          +250 78X XXX XXX  →  25078XXXXXXX
           250 78X XXX XXX  →  25078XXXXXXX
             0 78X XXX XXX  →  25078XXXXXXX
            78X XXX XXX     →  25078XXXXXXX (assumed Rwanda)

        For sandbox testing use the test MSISDNs (no normalization applied):
            56733123453  → SUCCESSFUL
            46733123454  → PENDING
            46733123450  → FAILED
        """
        # Strip whitespace, dashes, parentheses
        phone = ''.join(c for c in phone if c.isdigit())

        if phone.startswith('250'):
            return phone                        # Already international
        if phone.startswith('0') and len(phone) == 10:
            return '250' + phone[1:]            # 0781234567 → 250781234567
        if len(phone) == 9:
            return '250' + phone                # 781234567  → 250781234567
        # Already fully numeric international — return as-is
        return phone

    def request_to_pay(
        self,
        amount: str,
        phone: str,
        external_id: str,
        payer_message: str = "Payment",
        payee_note: str    = "Order payment",
        callback_url: str  = None,
    ) -> str:
        """
        Initiates a Request To Pay to the customer's MoMo wallet.

        Args:
            amount:        Amount as a string (e.g. "1000").
            phone:         Customer's phone number (will be normalized).
            external_id:   Your internal order/invoice ID for reconciliation.
            payer_message: Text the payer sees on their phone prompt.
            payee_note:    Internal note (not visible to payer).
            callback_url:  Full HTTPS URL for async status updates.

        Returns:
            reference_id (UUID str) — store this to poll status later.
        """
        reference_id  = str(uuid.uuid4())
        msisdn        = self.normalize_phone(phone)
        headers       = {**self._auth_headers(), 'X-Reference-Id': reference_id}

        if callback_url:
            headers['X-Callback-Url'] = callback_url

        payload = {
            'amount':       str(amount),
            'currency':     self.currency,
            'externalId':   external_id,
            'payer': {
                'partyIdType': 'MSISDN',
                'partyId':     msisdn,
            },
            'payerMessage': payer_message,
            'payeeNote':    payee_note,
        }

        url = f"{self.base_url}/collection/v1_0/requesttopay"
        logger.info(
            "MoMo: requestToPay → reference_id=%s amount=%s currency=%s msisdn=%s",
            reference_id, amount, self.currency, msisdn
        )

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
        except requests.RequestException as exc:
            raise MoMoError(f"requestToPay network error: {exc}") from exc

        # 202 Accepted = success for requestToPay (no response body)
        if response.status_code != 202:
            self._raise_for_status(response, "requestToPay")

        logger.info("MoMo: requestToPay accepted → reference_id=%s", reference_id)
        return reference_id

    def get_payment_status(self, reference_id: str) -> dict:
        """
        Polls the payment status for a given reference_id.

        Returns a dict with at least:
            {
                "status": "SUCCESSFUL" | "PENDING" | "FAILED" | "REJECTED" | "TIMEOUT",
                "financialTransactionId": "...",   (present on SUCCESSFUL)
                "amount": "...",
                "currency": "...",
                "payer": {...},
                ...
            }
        """
        url     = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
        headers = self._auth_headers()

        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException as exc:
            raise MoMoError(f"getPaymentStatus network error: {exc}") from exc

        self._raise_for_status(response, "getPaymentStatus")
        data = response.json()
        logger.info(
            "MoMo: payment status → reference_id=%s status=%s",
            reference_id, data.get('status')
        )
        return data
