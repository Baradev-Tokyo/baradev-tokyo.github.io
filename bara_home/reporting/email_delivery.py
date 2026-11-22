"""Transactional email boundary. Network delivery is disabled unless opted in."""

import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class DeliveryError(Exception):
    def __init__(self, code, *, retryable=False):
        super().__init__(code)
        self.retryable = retryable


class EmailProvider(Protocol):
    def send(self, message) -> str:
        """Return the provider message ID for this idempotent submission."""


class MockEmailProvider:
    def send(self, message):
        return f"mock-{message.message_id}"


class ResendEmailProvider:
    def send(self, message):
        key = settings.BARA_RESEND_API_KEY
        if (
            not settings.BARA_REPORTS_LIVE_EMAIL or not key or message.run.configuration.sample
            or message.sender != settings.BARA_REPORTS_FROM_EMAIL
            or not settings.BARA_REPORTS_SENDER_DOMAIN
            or message.sender.rsplit("@", 1)[-1].lower() != settings.BARA_REPORTS_SENDER_DOMAIN.lower()
        ):
            raise DeliveryError("live_delivery_disabled_or_sender_changed")
        try:
            validate_email(message.sender)
            validate_email(message.address)
        except ValidationError as exc:
            raise DeliveryError("invalid_email_address") from exc
        req = Request("https://api.resend.com/emails", data=json.dumps({
            "from": message.sender, "to": [message.address], "subject": message.subject,
            "html": message.html, "text": message.text,
            "tags": [{"name": "bara_message", "value": str(message.message_id)}],
        }).encode(), headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Idempotency-Key": f"bara-report-{message.message_id}",
            "User-Agent": "BaraDevelopment-Reporting/1.0",
        })
        try:
            with urlopen(req, timeout=15) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise DeliveryError(
                f"email_http_{exc.code}",
                retryable=exc.code in (408, 409, 429) or 500 <= exc.code < 600,
            ) from exc
        except (OSError, ValueError) as exc:
            raise DeliveryError("email_transport", retryable=True) from exc
        identifier = result.get("id") if isinstance(result, dict) else None
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 100:
            raise DeliveryError("email_response_invalid", retryable=True)
        return identifier


def get_provider(name):
    if name == "mock":
        return MockEmailProvider()
    if name == "resend":
        return ResendEmailProvider()
    raise DeliveryError("email_provider_not_configured")


def verify_resend(payload, headers, secret, now=None):
    if not secret.startswith("whsec_"):
        raise DeliveryError("webhook_disabled")
    event_id = headers.get("svix-id", "")
    timestamp = headers.get("svix-timestamp", "")
    if not event_id.isascii() or not 1 <= len(event_id) <= 100 or "." in event_id:
        raise DeliveryError("invalid_signature_headers")
    try:
        if not timestamp.isascii() or not timestamp.isdecimal() or len(timestamp) > 12:
            raise ValueError
        issued = int(timestamp)
        key = base64.b64decode(secret[6:], validate=True)
        if not key:
            raise ValueError
    except (ValueError, binascii.Error) as exc:
        raise DeliveryError("invalid_signature_headers") from exc
    if abs((time.time() if now is None else now) - issued) > 300:
        raise DeliveryError("expired_signature")
    signed = f"{event_id}.{timestamp}.".encode() + payload
    expected = base64.b64encode(hmac.digest(key, signed, hashlib.sha256)).decode()
    for item in headers.get("svix-signature", "").split():
        version, _, signature = item.partition(",")
        if version == "v1" and signature.isascii() and hmac.compare_digest(signature, expected):
            return event_id
    raise DeliveryError("invalid_signature")
