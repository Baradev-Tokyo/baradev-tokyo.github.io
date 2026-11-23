"""Small Stripe sandbox adapter for hosted Checkout and snapshot webhooks."""

import json
import re
import time
from urllib.parse import urlsplit

from django.conf import settings


class StripeError(Exception):
    pass


class InvalidEvent(ValueError):
    pass


def stripe_sdk():
    try:
        import stripe
    except ImportError:
        raise StripeError("Install the private reporting dependencies to use Stripe.") from None
    return stripe


class StripeGateway:
    def __init__(self):
        key = settings.BARA_STRIPE_TEST_KEY
        if not key.startswith(("sk_test_", "rk_test_")):
            raise StripeError("A Stripe test key is required.")
        self.sdk = stripe_sdk()
        self.client = self.sdk.StripeClient(
            key, stripe_version=settings.BARA_STRIPE_API_VERSION,
            max_network_retries=0, http_client=self.sdk.RequestsClient(timeout=10),
        ).v1

    def request(self, method, *args, **kwargs):
        try:
            result = method(*args, **kwargs)
            if isinstance(result, self.sdk.StripeObject):
                result = result.to_dict_recursive()
        except (self.sdk.StripeError, OSError, ValueError) as exc:
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
            "line_items": [{"price": order.stripe_price, "quantity": 1}],
            "success_url": success,
            "cancel_url": cancel,
            "client_reference_id": str(order.pk),
        }
        if order.mode == "payment":
            fields["invoice_creation"] = {"enabled": True}
        return self.request(self.client.checkout.sessions.create, fields,
                            options={"idempotency_key": f"bara-test-checkout-{order.pk}"})

    def test_payment_link(self, price_id, request_id):
        if not re.fullmatch(r"price_[A-Za-z0-9]+", price_id) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", request_id):
            raise StripeError("Use a sandbox Price ID and a stable test request ID.")
        return self.request(
            self.client.payment_links.create,
            {"line_items": [{"price": price_id, "quantity": 1}],
             "restrictions": {"completed_sessions": {"limit": 1}}},
            options={"idempotency_key": f"bara-test-link-{request_id}"},
        )

    def retrieve(self, resource, identifier):
        prefix = {"checkout/sessions": "cs_test_", "subscriptions": "sub_", "invoices": "in_"}[resource]
        if not re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9]+", identifier):
            raise InvalidEvent("Invalid Stripe object identifier.")
        service = {"checkout/sessions": self.client.checkout.sessions,
                   "subscriptions": self.client.subscriptions, "invoices": self.client.invoices}[resource]
        return self.request(service.retrieve, identifier)


def verify_snapshot(payload, signature_header, secret, now=None):
    if not secret.startswith("whsec_"):
        raise StripeError("A webhook signing secret is required.")
    if not signature_header.isascii():
        raise InvalidEvent("Invalid signature header.")
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
    sdk = stripe_sdk()
    try:
        body = payload.decode("utf-8")
        sdk.WebhookSignature.verify_header(body, signature_header, secret, tolerance=None)
        event = json.loads(body)
    except sdk.SignatureVerificationError as exc:
        raise InvalidEvent("Invalid signature.") from exc
    except (UnicodeError, ValueError) as exc:
        raise InvalidEvent("Invalid event body.") from exc
    if (
        not isinstance(event, dict) or event.get("livemode") is not False
        or not isinstance(event.get("id"), str) or not re.fullmatch(r"evt_[A-Za-z0-9]+", event["id"])
        or not isinstance(event.get("type"), str) or len(event["type"]) > 100
    ):
        raise InvalidEvent("Invalid sandbox event.")
    return event
