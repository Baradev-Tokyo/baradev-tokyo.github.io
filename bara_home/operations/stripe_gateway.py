"""Small Stripe sandbox adapter for hosted Checkout and snapshot webhooks."""

import hashlib
import hmac
import json
import re
import time
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings


class StripeError(Exception):
    pass


class InvalidEvent(ValueError):
    pass


class StripeGateway:
    def __init__(self):
        self.key = settings.BARA_STRIPE_TEST_KEY
        if not self.key.startswith(("sk_test_", "rk_test_")):
            raise StripeError("A Stripe test key is required.")

    def request(self, path, fields=None, idempotency_key=None):
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Stripe-Version": settings.BARA_STRIPE_API_VERSION,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        data = urlencode(fields).encode() if fields is not None else None
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request("https://api.stripe.com/v1/" + path, data=data, headers=headers)
        try:
            with urlopen(request, timeout=10) as response:
                result = json.load(response)
        except (OSError, URLError, ValueError) as exc:
            raise StripeError("Stripe sandbox request failed.") from exc
        if not isinstance(result, dict) or result.get("livemode") is not False:
            raise StripeError("Unexpected Stripe sandbox response.")
        return result

    def checkout(self, order):
        if not re.fullmatch(r"cus_[A-Za-z0-9]+", order.customer.stripe_id):
            raise StripeError("Invalid Stripe customer ID.")
        if not re.fullmatch(r"price_[A-Za-z0-9]+", order.stripe_price):
            raise StripeError("Invalid Stripe price ID.")
        base = settings.BARA_BILLING_BASE_URL.rstrip("/")
        origin = urlsplit(base)
        if (
            not origin.hostname or origin.username or origin.path or origin.query or origin.fragment
            or not (origin.scheme == "https" or
                    origin.scheme == "http" and origin.hostname in {"localhost", "127.0.0.1", "::1"})
        ):
            raise StripeError("Billing return origin must use HTTPS or loopback HTTP.")
        success = base + "/ops/billing/result/?outcome=returned"
        cancel = base + "/ops/billing/result/?outcome=cancelled"
        fields = {
            "customer": order.customer.stripe_id,
            "mode": order.mode,
            "line_items[0][price]": order.stripe_price,
            "line_items[0][quantity]": 1,
            "success_url": success,
            "cancel_url": cancel,
            "client_reference_id": str(order.pk),
        }
        if order.mode == "payment":
            fields["invoice_creation[enabled]"] = "true"
        return self.request("checkout/sessions", fields, idempotency_key=f"bara-test-checkout-{order.pk}")

    def retrieve(self, resource, identifier):
        prefix = {"checkout/sessions": "cs_test_", "subscriptions": "sub_", "invoices": "in_"}[resource]
        if not re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9]+", identifier):
            raise InvalidEvent("Invalid Stripe object identifier.")
        return self.request(f"{resource}/{identifier}")


def verify_snapshot(payload, signature_header, secret, now=None):
    if not secret.startswith("whsec_"):
        raise StripeError("A webhook signing secret is required.")
    parts = [part.partition("=") for part in signature_header.split(",")]
    try:
        timestamp, = [value for name, _, value in parts if name == "t"]
        if not timestamp.isascii() or not timestamp.isdecimal():
            raise ValueError
        timestamp_number = int(timestamp)
    except ValueError as exc:
        raise InvalidEvent("Invalid timestamp.") from exc
    if abs((time.time() if now is None else now) - timestamp_number) > 300:
        raise InvalidEvent("Expired signature.")
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    if not any(
        name == "v1" and value.isascii() and hmac.compare_digest(value, expected)
        for name, _, value in parts
    ):
        raise InvalidEvent("Invalid signature.")
    try:
        event = json.loads(payload)
    except (UnicodeError, ValueError) as exc:
        raise InvalidEvent("Invalid event body.") from exc
    if (
        not isinstance(event, dict) or event.get("livemode") is not False
        or not isinstance(event.get("id"), str) or not re.fullmatch(r"evt_[A-Za-z0-9]+", event["id"])
        or not isinstance(event.get("type"), str) or len(event["type"]) > 100
    ):
        raise InvalidEvent("Invalid sandbox event.")
    return event
