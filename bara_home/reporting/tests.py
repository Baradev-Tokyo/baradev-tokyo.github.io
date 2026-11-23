import base64
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone as utc
from decimal import Decimal
from io import BytesIO
from threading import Barrier
from unittest.mock import patch
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from operations.models import BillingCustomer, Workspace
from .email_delivery import DeliveryError
from .integrations import AvailabilitySample, CloudCost, import_availability, import_cloud_costs, sync_verified_stripe_invoice
from .models import (
    AuditEvent, BillingPeriod, CloudResourceOwnership, CustomerContact, EmailDeliveryEvent,
    JobStatus, PaymentEvent, ReportArtifact, ReportConfiguration, ReportDelivery, ReportKind,
    ReportRun, UsageRecord, VerifiedEmailRecipient,
)
from .reports import ReportError, finish, render_pdf, render_report, sample_rows
from .scheduling import claim_next, closed_period, complete, deliver, enqueue, generate, process, redact_expired


class CalendarAndRenderTests(SimpleTestCase):
    def test_jst_month_boundary_lag_and_week(self):
        now = datetime(2028, 2, 29, 15, tzinfo=utc.utc)
        self.assertEqual(closed_period(now, "Asia/Tokyo", "monthly", 0),
                         (date(2028, 2, 1), date(2028, 3, 1)))
        self.assertEqual(closed_period(now, "Asia/Tokyo", "daily", 0),
                         (date(2028, 2, 29), date(2028, 3, 1)))
        self.assertEqual(closed_period(now, "Asia/Tokyo", "monthly", 2),
                         (date(2028, 1, 1), date(2028, 2, 1)))
        now = datetime(2026, 11, 22, 15, tzinfo=utc.utc)
        self.assertEqual(closed_period(now, "Asia/Tokyo", "weekly", 0),
                         (date(2026, 11, 16), date(2026, 11, 23)))

    def test_bilingual_html_plain_and_pdf(self):
        for lang in ("en", "ja"):
            with self.subTest(lang=lang):
                summary = finish(lang, "ホスティング" if lang == "ja" else "Hosting", "<script>alert</script>",
                                 "2026-11-01", sample_rows(lang == "ja"), "sample")
                self.assertIn(f'<html lang="{lang}">', summary.html)
                self.assertNotIn("<script>alert</script>", summary.html)
                self.assertIn("<script>alert</script>", summary.text)
                self.assertTrue(render_pdf(summary).startswith(b"%PDF-"))


class ReportingTests(TestCase):
    start = date(2026, 10, 1)
    end = date(2026, 11, 1)
    scheduled = datetime(2026, 11, 3, tzinfo=utc.utc)

    def setUp(self):
        self.owner = Workspace.objects.create(name="A")
        self.other = Workspace.objects.create(name="B")
        self.contact = CustomerContact.objects.create(organization=self.owner, email="a@example.invalid")
        self.recipient = VerifiedEmailRecipient.objects.create(contact=self.contact, address=self.contact.email)
        self.cfg = ReportConfiguration.objects.create(
            organization=self.owner, kind=ReportKind.HOSTING_CHARGES, frequency="monthly",
            language="en", starts_on=self.start, active=True,
        )
        self.cfg.recipients.add(self.recipient)
        self.period = BillingPeriod.objects.create(
            organization=self.owner, start=self.start, end=self.end,
            base_charge=Decimal(3000), discount=Decimal(100), tax=Decimal(290), finalized=True,
        )
        self.run_time = timezone.now()

    def queued(self):
        enqueue(self.scheduled)
        return ReportRun.objects.get()

    def mock_delivery(self):
        self.queued()
        process(ReportRun, generate, 1)
        return ReportDelivery.objects.get()

    def test_replayed_schedule_and_mock_delivery_do_not_duplicate(self):
        with override_settings(BARA_REPORTS_LIVE_EMAIL=True):
            self.assertEqual(enqueue(self.scheduled), 1)
            self.assertEqual(enqueue(self.scheduled), 0)
            process(ReportRun, generate, 5)
            process(ReportDelivery, deliver, 5)
            process(ReportDelivery, deliver, 5)
        self.assertEqual(ReportRun.objects.get().status, JobStatus.READY)
        delivery = ReportDelivery.objects.get()
        self.assertEqual((delivery.provider, delivery.status), ("mock", JobStatus.SIMULATED))
        self.assertEqual(ReportArtifact.objects.count(), 1)
        self.assertTrue(AuditEvent.objects.filter(organization=self.owner, kind="reportdelivery.simulated").exists())

    def test_expired_claim_cannot_finish_after_takeover(self):
        self.queued()
        first = claim_next(ReportRun, timezone.now())
        self.assertIsNone(claim_next(ReportRun, timezone.now()))
        second = claim_next(ReportRun, timezone.now() + timedelta(minutes=16))
        self.assertNotEqual(first.claim, second.claim)
        complete(first, JobStatus.READY)
        self.assertEqual(ReportRun.objects.get().claim, second.claim)
        complete(second, JobStatus.READY)
        self.assertEqual(ReportRun.objects.get().status, JobStatus.READY)

    def test_cross_organization_recipients_fail_closed(self):
        other_contact = CustomerContact.objects.create(organization=self.other, email="b@example.invalid")
        other = VerifiedEmailRecipient.objects.create(contact=other_contact, address=other_contact.email)
        self.cfg.recipients.add(other)
        self.queued()
        with self.assertLogs("reporting.scheduling", level="ERROR"):
            process(ReportRun, generate, 1)
        self.assertEqual(ReportRun.objects.get().error_code, "recipient_invalid_or_mismatched")
        self.assertFalse(ReportArtifact.objects.exists())
        self.assertFalse(ReportDelivery.objects.exists())

    def test_address_change_or_revocation_blocks_an_already_queued_email(self):
        delivery = self.mock_delivery()
        self.contact.email = "new-address@example.invalid"
        self.contact.save(update_fields=["email"])
        with patch("reporting.scheduling.get_provider") as provider, self.assertLogs("reporting.scheduling", level="ERROR"):
            process(ReportDelivery, deliver, 1)
        provider.assert_not_called()
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.error_code), (JobStatus.FAILED, "recipient_revoked_or_mismatched"))

    def test_billing_import_is_idempotent_and_rejects_unowned_rows(self):
        owned = CloudResourceOwnership.objects.create(
            organization=self.owner, project_id="project-a", resource="service", starts_on=self.start,
        )
        item = CloudCost("stable", self.start, "project-a", "service", "Cloud Run", "JPY",
                         Decimal("1200"), Decimal("-100"))
        self.assertEqual(import_cloud_costs(self.period, [item], estimated=False), 1)
        import_cloud_costs(self.period, [item], estimated=False)
        self.assertEqual(UsageRecord.objects.count(), 1)
        CloudResourceOwnership.objects.create(
            organization=self.other, project_id="project-a", resource="service", starts_on=self.start,
        )
        with self.assertRaises(ValueError):
            import_cloud_costs(self.period, [item])
        run = self.queued()
        self.cfg.sample = False
        self.cfg.save(update_fields=["sample"])
        run.refresh_from_db()
        with self.assertRaises(ReportError):
            render_report(run)
        self.assertEqual(UsageRecord.objects.get().ownership, owned)

    def test_actual_report_distinguishes_financial_amounts_and_estimates(self):
        CloudResourceOwnership.objects.create(
            organization=self.owner, project_id="project-a", resource="a", starts_on=self.start,
        )
        lines = (
            CloudCost("actual", self.start, "project-a", "a", "Run", "JPY", Decimal(1200), Decimal(-100)),
            CloudCost("estimate", self.start, "project-a", "a", "Storage", "JPY", Decimal(350), Decimal(0)),
        )
        import_cloud_costs(self.period, [lines[0]], estimated=False)
        import_cloud_costs(self.period, [lines[1]])
        mapping = PaymentEvent.objects.create(period=self.period, stripe_invoice_id="in_Test", currency="JPY")
        invoice = {"id": "in_Test", "status": "open", "currency": "jpy",
                   "total": 3190, "amount_paid": 1500, "amount_remaining": 1690}
        sync_verified_stripe_invoice(self.other.pk, invoice)
        mapping.refresh_from_db()
        self.assertIsNone(mapping.synchronized_at)
        sync_verified_stripe_invoice(self.owner.pk, invoice)
        self.cfg.sample = False
        self.cfg.save(update_fields=["sample"])
        text = render_report(self.queued()).text
        for expected in ("Finalized cloud cost · Run: JPY 1,100",
                         "Estimated cloud cost · Storage: JPY 350",
                         "Customer charges including tax: JPY 3,190",
                         "Stripe invoiced: JPY 3,190", "Collected payments: JPY 1,500",
                         "Outstanding: JPY 1,690"):
            self.assertIn(expected, text)
        self.assertNotIn("Hosting margin", text)

    def test_availability_records_use_owned_resource(self):
        CloudResourceOwnership.objects.create(
            organization=self.owner, project_id="project-a", resource="a", starts_on=self.start,
        )
        import_availability(self.period, [AvailabilitySample(self.start, "project-a", "a", 4, 3)])
        self.cfg.kind, self.cfg.sample = ReportKind.HOSTING_USAGE, False
        self.cfg.save(update_fields=["kind", "sample"])
        self.assertIn("75.00% (3/4)", render_report(self.queued()).text)

    @override_settings(BARA_STRIPE_SANDBOX_ENABLED=True)
    @patch("reporting.management.commands.sync_reporting_inputs.StripeGateway")
    def test_manual_stripe_reconciliation_checks_customer_scope(self, stripe):
        BillingCustomer.objects.create(workspace=self.other, label="B", stripe_id="cus_Other")
        BillingCustomer.objects.create(workspace=self.owner, label="A", stripe_id="cus_Owned")
        snapshot = PaymentEvent.objects.create(period=self.period, stripe_invoice_id="in_Test", currency="JPY")
        invoice = {"id": "in_Test", "status": "paid", "currency": "jpy", "customer": "cus_Other",
                   "total": 2000, "amount_paid": 2000, "amount_remaining": 0}
        stripe.return_value.retrieve.return_value = invoice
        with self.assertRaises(CommandError):
            call_command("sync_reporting_inputs", self.period.pk, stripe_invoice="in_Test")
        snapshot.refresh_from_db()
        self.assertIsNone(snapshot.synchronized_at)
        invoice["customer"] = "cus_Owned"
        call_command("sync_reporting_inputs", self.period.pk, stripe_invoice="in_Test")
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.collected_minor, 2000)

    def test_retries_stop_and_preserve_status_after_body_retention(self):
        delivery = self.mock_delivery()
        with patch("reporting.scheduling.get_provider") as provider:
            provider.return_value.send.side_effect = DeliveryError("email_transport", retryable=True)
            process(ReportDelivery, deliver, 1)
            delivery.refresh_from_db()
            self.assertEqual(delivery.status, JobStatus.RETRY)
            self.assertGreater(delivery.next_attempt, timezone.now())
            ReportDelivery.objects.filter(pk=delivery.pk).update(attempts=4, next_attempt=timezone.now())
            with self.assertLogs("reporting.scheduling", level="ERROR"):
                process(ReportDelivery, deliver, 1)
        future = timezone.now() + timedelta(days=91)
        self.assertEqual(redact_expired(future), (1, 1))
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.text), (JobStatus.FAILED, ""))
        self.assertIsNone(ReportArtifact.objects.get().data)

    @override_settings(BARA_REPORTS_LIVE_EMAIL=True, BARA_REPORTS_FROM_EMAIL="reports@example.invalid",
                       BARA_REPORTS_SENDER_DOMAIN="example.invalid", BARA_RESEND_API_KEY="test-only")
    @patch("reporting.email_delivery.urlopen")
    def test_resend_keeps_snapshot_and_idempotency_key_on_retry(self, network):
        self.cfg.sample, self.cfg.allow_live = False, True
        self.cfg.save(update_fields=["sample", "allow_live"])
        delivery = self.mock_delivery()
        network.side_effect = [TimeoutError(), BytesIO(b'{"id":"provider-1"}')]
        process(ReportDelivery, deliver, 1)
        ReportDelivery.objects.filter(pk=delivery.pk).update(next_attempt=timezone.now())
        process(ReportDelivery, deliver, 1)
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.provider_id), (JobStatus.ACCEPTED, "provider-1"))
        first, second = (call.args[0] for call in network.call_args_list)
        self.assertEqual(first.data, second.data)
        self.assertEqual(first.headers["Idempotency-key"], second.headers["Idempotency-key"])

    def test_webhook_signatures_duplicates_and_event_order(self):
        delivery = self.mock_delivery()
        ReportDelivery.objects.filter(pk=delivery.pk).update(
            provider="resend", provider_id="provider-1", status=JobStatus.ACCEPTED,
        )
        key = b"fixture-signing-key"
        secret = "whsec_" + base64.b64encode(key).decode()
        url = "/ops/reporting/delivery-webhook/"
        def send(kind, identifier, corrupt=False):
            payload = json.dumps({"type": kind, "data": {"email_id": "provider-1"}}).encode()
            stamp = str(int(time.time()))
            digest = hmac.digest(key, f"{identifier}.{stamp}.".encode() + payload, "sha256")
            signature = "bad" if corrupt else base64.b64encode(digest).decode()
            return self.client.post(url, payload, content_type="application/json",
                                    HTTP_SVIX_ID=identifier, HTTP_SVIX_TIMESTAMP=stamp,
                                    HTTP_SVIX_SIGNATURE="v1," + signature).status_code
        with override_settings(BARA_RESEND_WEBHOOK_SECRET=secret):
            self.assertEqual(send("email.delivered", "msg_bad", corrupt=True), 400)
            with self.assertLogs("reporting.notifications", level="ERROR"):
                self.assertEqual(send("email.bounced", "msg_1"), 204)
            self.assertEqual(send("email.bounced", "msg_1"), 204)
            self.assertEqual(send("email.delivered", "msg_2"), 204)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, JobStatus.BOUNCED)
        self.assertEqual(EmailDeliveryEvent.objects.count(), 2)

    def test_artifacts_are_owner_only(self):
        self.mock_delivery()
        artifact = ReportArtifact.objects.get()
        url = reverse("admin:report_artifact_download", args=[artifact.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = get_user_model().objects.create_user(username="staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        owner = get_user_model().objects.create_superuser("owner", password="test")
        self.client.force_login(owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        ReportArtifact.objects.filter(pk=artifact.pk).update(expires_at=timezone.now())
        self.assertEqual(self.client.get(url).status_code, 404)


@skipUnless(connection.vendor == "postgresql", "requires PostgreSQL row-level concurrency")
class PostgresClaimTests(TransactionTestCase):
    def test_two_executions_only_claim_one_run(self):
        workspace = Workspace.objects.create(name="PostgreSQL fixture")
        config = ReportConfiguration.objects.create(
            organization=workspace, kind=ReportKind.HOSTING_USAGE, frequency="monthly",
            starts_on=date(2026, 10, 1), active=True,
        )
        run = ReportRun.objects.create(
            configuration=config, organization=workspace,
            period_start=date(2026, 10, 1), period_end=date(2026, 11, 1),
        )
        gate = Barrier(2)

        def claim():
            close_old_connections()
            try:
                gate.wait(timeout=5)
                return claim_next(ReportRun, timezone.now())
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual([item.pk for item in results if item], [run.pk])
        run.refresh_from_db()
        self.assertEqual(run.attempts, 1)
