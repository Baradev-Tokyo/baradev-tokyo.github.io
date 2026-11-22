import hashlib
import hmac
import json
import time
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .costs import (
    CostLine, Receivable, ResourceMapping, SampleExport, Settlement, budget_thresholds,
    overdue_for_review, summarize,
)
from .models import BillingCustomer, BillingOrder, Invoice, StripeEvent, Subscription, Workspace
from .stripe_gateway import StripeError

SECRET = "whsec_fixture"
WEBHOOK = "/ops/billing/webhook/"


@override_settings(
    BARA_STRIPE_SANDBOX_ENABLED=True, BARA_STRIPE_TEST_KEY="sk_test_fixture",
    BARA_STRIPE_WEBHOOK_SECRET=SECRET,
)
class SandboxTests(TestCase):
    def setUp(self):
        workspace = Workspace.objects.create(name="Fixture")
        self.customer = BillingCustomer.objects.create(
            workspace=workspace, label="Fixture", stripe_id="cus_Fixture"
        )
        self.order = BillingOrder.objects.create(
            customer=self.customer, kind=BillingOrder.Kind.DEPOSIT, stripe_price="price_Fixture"
        )
        self.checkout_url = reverse("sandbox_checkout", args=(self.order.pk,))

    def sign(self, body, timestamp=None):
        timestamp = int(time.time()) if timestamp is None else timestamp
        signature = hmac.new(SECRET.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
        return f"t={timestamp},v1={signature.hexdigest()}"

    def send_event(self, kind, object_data, identifier="evt_Fixture", **overrides):
        event = {"id": identifier, "type": kind, "livemode": False, "data": {"object": object_data}}
        body = json.dumps(event | overrides).encode()
        return self.client.post(WEBHOOK, body, content_type="application/json",
                                HTTP_STRIPE_SIGNATURE=self.sign(body))

    def login_owner(self):
        owner = get_user_model().objects.create_superuser("owner", password="fixture")
        self.client.force_login(owner)
        return owner

    def test_checkout_owner_and_csrf(self):
        self.assertEqual(self.client.post(self.checkout_url).status_code, 302)
        staff = get_user_model().objects.create_user("staff", is_staff=True)
        self.client.force_login(staff)
        self.assertIn("/admin/login/", self.client.post(self.checkout_url)["Location"])
        owner = self.login_owner()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(owner)
        self.assertEqual(csrf_client.post(self.checkout_url).status_code, 403)
        self.assertEqual(self.client.get(self.checkout_url).status_code, 405)
        with override_settings(BARA_STRIPE_SANDBOX_ENABLED=False):
            self.assertEqual(self.client.post(self.checkout_url).status_code, 404)
            self.assertEqual(self.client.post(WEBHOOK).status_code, 404)

    @patch("operations.stripe_gateway.urlopen")
    def test_checkout_uses_server_price_and_idempotency_key(self, network):
        self.login_owner()
        payload = {"id": "cs_test_Fixture", "url": "https://checkout.stripe.com/c/pay/test", "livemode": False}
        network.side_effect = [TimeoutError, BytesIO(json.dumps(payload).encode())]
        self.assertEqual(self.client.post(self.checkout_url).status_code, 503)
        self.assertEqual(self.client.post(self.checkout_url, {"price": "price_Attacker"})["Location"], payload["url"])
        self.assertEqual(self.client.post(self.checkout_url)["Location"], payload["url"])
        self.assertEqual(network.call_count, 2)
        first, second = [call.args[0] for call in network.call_args_list]
        self.assertEqual(first.headers["Idempotency-key"], second.headers["Idempotency-key"])
        self.assertEqual(parse_qs(second.data.decode())["line_items[0][price]"], ["price_Fixture"])
        self.assertEqual(parse_qs(second.data.decode())["mode"], ["payment"])
        self.assertEqual(parse_qs(second.data.decode())["invoice_creation[enabled]"], ["true"])
        self.client.get("/ops/billing/result/?outcome=returned")
        self.client.get("/ops/billing/result/?outcome=cancelled")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "pending")

    @patch("operations.stripe_gateway.urlopen")
    def test_maintenance_uses_recurring_checkout(self, network):
        self.login_owner()
        order = BillingOrder.objects.create(
            customer=self.customer, kind=BillingOrder.Kind.MAINTENANCE, stripe_price="price_Monthly"
        )
        network.return_value = BytesIO(json.dumps({
            "id": "cs_test_Monthly", "url": "https://checkout.stripe.com/c/pay/test", "livemode": False,
        }).encode())
        response = self.client.post(reverse("sandbox_checkout", args=(order.pk,)))
        self.assertEqual(response.status_code, 302)
        fields = parse_qs(network.call_args.args[0].data.decode())
        self.assertEqual(fields["mode"], ["subscription"])
        self.assertNotIn("invoice_creation[enabled]", fields)

    def test_webhook_refuses_invalid_expired_and_live_events(self):
        body = b"{}"
        self.assertEqual(self.client.post(WEBHOOK, body, content_type="application/json",
                                         HTTP_STRIPE_SIGNATURE="v1=bad").status_code, 400)
        self.assertEqual(self.client.post(WEBHOOK, body, content_type="application/json",
                                         HTTP_STRIPE_SIGNATURE=self.sign(body, 1)).status_code, 400)
        self.assertEqual(self.send_event("checkout.session.completed", {}, livemode=True).status_code, 400)
        self.assertEqual(StripeEvent.objects.count(), 0)

    @patch("operations.billing.StripeGateway")
    def test_webhook_rolls_back_failed_delivery_then_deduplicates(self, stripe):
        self.login_owner()
        session = {"id": "cs_test_Fixture", "customer": self.customer.stripe_id,
                   "client_reference_id": str(self.order.pk), "payment_status": "paid",
                   "payment_intent": "pi_Fixture", "invoice": "in_Fixture", "status": "complete", "mode": "payment"}
        stripe.return_value.checkout.return_value = dict(session, url="https://checkout.stripe.com/c/pay/test")
        self.client.post(self.checkout_url)
        stripe.return_value.retrieve.side_effect = [StripeError(), session, session]
        args = ("checkout.session.completed", session)
        self.assertEqual(self.send_event(*args).status_code, 503)
        self.assertFalse(StripeEvent.objects.exists())
        self.assertEqual(self.send_event(*args).status_code, 204)
        self.assertEqual(self.send_event(*args).status_code, 204)
        self.assertEqual(StripeEvent.objects.count(), 1)
        self.assertEqual(self.send_event("checkout.session.async_payment_failed", session, "evt_Stale").status_code, 204)
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.payment_intent_id), ("paid", "pi_Fixture"))
        self.assertEqual(self.order.invoice_id, "in_Fixture")
        self.assertEqual(stripe.return_value.retrieve.call_count, 3)

    @patch("operations.billing.StripeGateway")
    def test_reconciles_current_subscription_and_invoice(self, stripe):
        subscription = {"id": "sub_Fixture", "customer": self.customer.stripe_id,
                        "status": "canceled", "cancel_at_period_end": False}
        invoice = {"id": "in_Fixture", "customer": self.customer.stripe_id,
                   "status": "open", "currency": "jpy", "amount_due": 3000,
                   "amount_paid": 0, "attempt_count": 1}
        stripe.return_value.retrieve.side_effect = [
            subscription, invoice, dict(invoice, status="paid", amount_paid=3000)
        ]
        self.assertEqual(self.send_event("customer.subscription.updated", subscription).status_code, 204)
        self.assertEqual(Subscription.objects.get().status, "canceled")
        self.assertEqual(self.send_event("invoice.payment_failed", invoice, "evt_Failed").status_code, 204)
        self.assertTrue(Invoice.objects.get().payment_failed)
        self.assertEqual(self.send_event("invoice.paid", invoice, "evt_Paid").status_code, 204)
        current = Invoice.objects.get()
        self.assertEqual((current.status, current.amount_paid, current.payment_failed), ("paid", 3000, False))

    @patch("operations.stripe_gateway.urlopen")
    @override_settings(BARA_STRIPE_TEST_KEY="sk_live_fixture")
    def test_live_key_is_refused_before_network(self, network):
        self.login_owner()
        self.assertEqual(self.client.post(self.checkout_url).status_code, 503)
        network.assert_not_called()


class CostTests(SimpleTestCase):
    def test_cost_report_credits_currency_precedence_and_unassigned(self):
        day = date(2026, 11, 22)
        cost = SampleExport((
            CostLine(day, "202611", "shared", "run", "svc", "JPY", Decimal(1000), Decimal(-100)),
            CostLine(day, "202611", "shared", "storage", "bucket", "JPY", Decimal(70)),
            CostLine(day, "202611", "unknown", "run", "svc", "USD", Decimal(2)),
        ))
        mappings = (ResourceMapping("shared", "owner", day),
                    ResourceMapping("shared", "client", day, service="run", resource="svc"))
        settled = (Settlement("client", "202611", "JPY", Decimal(2000), Decimal(200), Decimal(100)),)
        daily, monthly, margin = summarize(cost, day, day, mappings, settled)
        self.assertEqual(daily[day, "client", "JPY"], 900)
        self.assertEqual(monthly["202611", None, "USD"], 2)
        self.assertEqual(margin["202611", "client", "JPY"], 800)
        self.assertEqual(budget_thresholds(Decimal(900), Decimal(1000)), (Decimal(".5"), Decimal(".9")))
        with self.assertRaises(ValueError):
            summarize(cost, day, day, (*mappings, mappings[1]))

    def test_grace_period_produces_review_only_after_expiry(self):
        due = date(2026, 11, 20)
        grace = date(2026, 11, 25)
        items = (Receivable("open", "open", due, grace), Receivable("paid", "paid", due, None))
        self.assertEqual(overdue_for_review(items, grace), [])
        self.assertEqual(overdue_for_review(items, date(2026, 11, 26)), ["open"])
