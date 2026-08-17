"""
Wompi payment gateway service.
Docs: https://docs.wompi.co/
"""

import os
import time
import hmac
import hashlib
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

WOMPI_BASE_URL = os.getenv("WOMPI_BASE_URL", "https://api.wompi.sv")
WOMPI_PUBLIC_KEY = os.getenv("WOMPI_PUBLIC_KEY", "")
WOMPI_PRIVATE_KEY = os.getenv("WOMPI_PRIVATE_KEY", "")
WOMPI_INTEGRITY_SECRET = os.getenv("WOMPI_INTEGRITY_SECRET", "")
WOMPI_EVENTS_SECRET = os.getenv("WOMPI_EVENTS_SECRET", "")

# Cache for acceptance tokens (valid ~4 hours)
_acceptance_token_cache: dict = {"token": "", "expires": 0}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {WOMPI_PRIVATE_KEY}",
        "Content-Type": "application/json",
    }


def get_acceptance_token() -> Optional[str]:
    """Fetch acceptance tokens from merchant info. Cached for ~4 hours."""
    now = time.time()
    if _acceptance_token_cache["token"] and _acceptance_token_cache["expires"] > now:
        return _acceptance_token_cache["token"]

    try:
        resp = requests.get(
            f"{WOMPI_BASE_URL}/v1/merchants/{WOMPI_PUBLIC_KEY}",
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        presigned = data.get("presigned_acceptance", {})
        acceptance_token = presigned.get("acceptance_token")
        expires_in = presigned.get("permalink", "")  # not actual expiry, default 4h

        if not acceptance_token:
            logger.error("No acceptance_token in merchant response")
            return None

        _acceptance_token_cache["token"] = acceptance_token
        _acceptance_token_cache["expires"] = now + 3 * 3600  # cache 3h to be safe
        logger.info("Wompi acceptance_token refreshed")
        return acceptance_token

    except Exception as e:
        logger.error(f"Error fetching Wompi acceptance token: {e}")
        return None


def generate_integrity_signature(reference: str, amount_in_cents: int, currency: str) -> str:
    """Generate SHA256 integrity signature for transaction creation."""
    if not WOMPI_INTEGRITY_SECRET:
        return ""
    raw = f"{reference}{amount_in_cents}{currency}{WOMPI_INTEGRITY_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_event_signature(event_data: dict) -> str:
    """Generate SHA256 signature for webhook event verification."""
    if not WOMPI_EVENTS_SECRET:
        return ""
    # Concatenate all values from the event transaction in order
    transaction = event_data.get("transaction", {})
    fields = [
        str(event_data.get("id", "")),
        str(transaction.get("id", "")),
        str(event_data.get("timestamp", "")),
        str(transaction.get("status", "")),
        str(transaction.get("status_message", "")),
        str(transaction.get("amount_in_cents", "")),
        str(transaction.get("currency", "")),
        str(transaction.get("reference", "")),
    ]
    concatenated = "".join(fields) + WOMPI_EVENTS_SECRET
    return hashlib.sha256(concatenated.encode()).hexdigest()


def create_transaction(
    reference: str,
    amount_in_cents: int,
    customer_email: str,
    customer_name: str,
    customer_phone: Optional[str] = None,
    payment_method: dict = None,
    redirect_url: str = "",
) -> dict:
    """
    Create a Wompi transaction.
    Returns dict with transaction_id, redirect_url, or error.
    """
    acceptance_token = get_acceptance_token()
    if not acceptance_token:
        return {"error": "No se pudo obtener el token de aceptación de Wompi"}

    currency = "COP"
    signature = generate_integrity_signature(reference, amount_in_cents, currency)

    payload = {
        "amount_in_cents": amount_in_cents,
        "currency": currency,
        "customer_email": customer_email,
        "customer_name": customer_name,
        "reference": reference,
        "acceptance_token": acceptance_token,
    }

    if customer_phone:
        payload["customer_phone_number"] = customer_phone

    if redirect_url:
        payload["redirect_url"] = redirect_url

    if signature:
        payload["signature"] = {
            "integrity": signature,
        }

    if payment_method:
        payload["payment_method"] = payment_method

    try:
        resp = requests.post(
            f"{WOMPI_BASE_URL}/v1/transactions",
            json=payload,
            headers=_headers(),
            timeout=20,
        )
        resp_data = resp.json()

        if resp.status_code in (200, 201):
            data = resp_data.get("data", {})
            return {
                "transaction_id": data.get("id"),
                "status": data.get("status"),
                "redirect_url": data.get("payment_method", {}).get("redirect_url"),
                "reference": reference,
            }
        else:
            error_msg = resp_data.get("error", {}).get("message", "Unknown error")
            logger.error(f"Wompi create transaction error: {resp.status_code} - {error_msg}")
            return {"error": error_msg}

    except Exception as e:
        logger.error(f"Wompi API error: {e}")
        return {"error": "Error al conectar con Wompi"}


def verify_webhook_signature(event: dict) -> bool:
    """Verify webhook event signature using WOMPI_EVENTS_SECRET."""
    if not WOMPI_EVENTS_SECRET:
        if os.getenv("ENVIRONMENT", "development") == "production":
            logger.error("WOMPI_EVENTS_SECRET not set — rejecting webhook in production")
            return False
        logger.warning("WOMPI_EVENTS_SECRET not set — accepting webhook in dev mode")
        return True

    sent_signature = event.get("signature", {}).get("checksum", "")
    expected = generate_event_signature(event)
    return hmac.compare_digest(sent_signature, expected)


def get_transaction_status(transaction_id: int) -> Optional[dict]:
    """Fetch current status of a transaction from Wompi."""
    try:
        resp = requests.get(
            f"{WOMPI_BASE_URL}/v1/transactions/{transaction_id}",
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("data", {})
        logger.error(f"Wompi get transaction error: {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"Wompi API error fetching transaction: {e}")
        return None
