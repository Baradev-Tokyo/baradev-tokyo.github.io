import json
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from operations.models import Workspace
from services.marketplace_catalog import draft_catalog, validate_drafts
from .models import MarketplaceReceipt, Opportunity
from .providers import LlamaCppProvider, OpenAIProvider, UnavailableProvider
from .screening import RulesProvider, Weights


class RulesTests(SimpleTestCase):
    def test_draft_detects_drift_without_inventing_prices(self):
        for platform in ("upwork", "fiverr"):
            drafts = draft_catalog(platform)
            errors, pending = validate_drafts(drafts, platform)
            self.assertEqual(errors, [])
            self.assertEqual(len(pending), 18)
            self.assertTrue(all(tier["price"] is None for draft in drafts for tier in draft["tiers"]))
            drafts[0]["canonical_snapshot"]["estimate_low"] = 1
            self.assertTrue(validate_drafts(drafts, platform)[0])

    def test_incomplete_connects_and_policy_protect_manual_decision(self):
        item = Opportunity(source="upwork", external_id="fixture", title="Fixture", skills=["Django"])
        result = RulesProvider().assess(item)
        self.assertEqual(result["recommendation"], "hold_connects")
        self.assertIn("budget", result["missing_information"])
        self.assertIsNone(result["potential_revenue_lower_bound"])
        item.off_platform_requested = True
        self.assertEqual(RulesProvider().assess(item)["recommendation"], "reject_policy_risk")

    def test_estimates_are_bounded_and_weights_are_validated(self):
        with self.assertRaises(ValueError):
            Weights(technical=0)
        item = Opportunity(source="direct", external_id="fixture", title="Fixture",
                           skills=["Django", "Python"], currency="JPY",
                           budget_low=Decimal(100), provider_fee=Decimal(10), delivery_cost=Decimal(30))
        result = RulesProvider().assess(item)
        self.assertEqual(result["estimated_profit_lower_bound_before_owner_labor_and_tax"], "60")
        self.assertEqual(result["recommendation"], "manual_review")

    @patch("acquisition.providers.shutil.which", return_value=None)
    @patch("acquisition.providers.subprocess.run")
    def test_missing_local_runtime_falls_back_without_starting_process(self, run, which):
        item = Opportunity(source="direct", external_id="fixture", title="Private customer title")
        with TemporaryDirectory() as tmp:
            model = Path(tmp) / "fixture.gguf"
            model.touch()
            result = LlamaCppProvider(model).assess(item)
        self.assertEqual(result["local_model_status"], "unavailable")
        run.assert_not_called()
        with self.assertRaises(UnavailableProvider):
            OpenAIProvider().assess(item)


class OwnerDashboardTests(TestCase):
    def setUp(self):
        self.organization = Workspace.objects.create(name="Workspace A")
        self.other = Workspace.objects.create(name="Workspace B")

    def test_job_review_is_private_and_approval_is_idempotent(self):
        job = Opportunity.objects.create(
            organization=self.organization, source="upwork", external_id="sample",
            title="Booking system", description="<script>unsafe()</script>", connects_required=0,
        )
        url = reverse("bara_job_review", args=[self.organization.pk, job.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(get_user_model().objects.create_user("editor", is_staff=True))
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(get_user_model().objects.create_superuser("reviewer", password="fixture"))
        self.assertEqual(self.client.get(reverse("bara_job_review", args=[self.other.pk, job.pk])).status_code, 404)
        self.assertContains(self.client.get(url), "&lt;script&gt;")
        self.assertEqual(self.client.post(url).status_code, 302)
        job.refresh_from_db()
        self.assertIn("Booking system", job.proposal_draft)
        approved = job.proposal_approved_at
        self.assertEqual(self.client.post(url, {"focus": "replace the draft"}).status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.proposal_approved_at, approved)
        self.assertNotIn("replace the draft", job.proposal_draft)

    def test_batch_import_preserves_existing_jobs(self):
        with TemporaryDirectory() as tmp:
            data = Path(tmp) / "batch.json"
            for title in ("Original", "Changed"):
                data.write_text(json.dumps([
                    {"external_id": "batch", "title": title, "connects_required": 0},
                    {"external_id": "paid", "title": "Paid", "connects_required": 1},
                    {"external_id": "unknown", "title": "Unknown"},
                    {"external_id": "boolean", "title": "Boolean", "connects_required": False},
                ]), encoding="utf-8")
                call_command("import_upwork_batch", self.organization.pk, data, stdout=StringIO())
        self.assertEqual(Opportunity.objects.get(organization=self.organization).title, "Original")

    def test_paid_and_unknown_upwork_jobs_cannot_be_drafted(self):
        owner = get_user_model().objects.create_superuser("zero-connects-owner", password="fixture")
        self.client.force_login(owner)
        dashboard = reverse("bara_operations") + f"?workspace={self.organization.pk}"
        for cost in (None, 4):
            job = Opportunity.objects.create(
                organization=self.organization, source="upwork", external_id=f"cost-{cost}",
                title=f"Excluded job {cost}", description="Build a booking system.", connects_required=cost,
            )
            url = reverse("bara_job_review", args=[self.organization.pk, job.pk])
            self.assertNotContains(self.client.get(dashboard), job.title)
            self.assertNotContains(self.client.get(url), "Draft proposal</button>")
            self.assertEqual(self.client.post(url).status_code, 400)

    def test_fiverr_intake_and_reply_stay_in_the_workspace(self):
        owner = get_user_model().objects.create_superuser("fiverr-owner", password="fixture")
        self.client.force_login(owner)
        dashboard = self.client.get(reverse("bara_operations") + f"?workspace={self.organization.pk}")
        self.assertContains(dashboard, "Record a Fiverr opportunity")
        intake = self.client.get(reverse("admin:acquisition_opportunity_add"), {
            "source": "fiverr", "organization": self.organization.pk,
        })
        self.assertEqual(intake.context["adminform"].form.initial["source"], "fiverr")
        self.assertEqual(intake.context["adminform"].form.initial["organization"], str(self.organization.pk))
        job = Opportunity.objects.create(
            organization=self.organization, source="fiverr", external_id="mira-fixture",
            title="Booking page", description="Need a booking page for tours.",
        )
        url = reverse("bara_job_review", args=[self.organization.pk, job.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertContains(self.client.get(url), "custom offer here on Fiverr")

    def test_manual_import_preserves_existing_record_and_scopes_ids(self):
        with TemporaryDirectory() as tmp:
            data = Path(tmp) / "fixture.json"
            payload = {"source": "upwork", "external_id": "fixture", "title": "Example", "skills": ["Django"]}
            data.write_text(json.dumps(payload), encoding="utf-8")
            for workspace in (self.organization, self.organization, self.other):
                call_command("import_opportunity", workspace.pk, data, save=True, stdout=StringIO(), stderr=StringIO())
        self.assertEqual(Opportunity.objects.count(), 2)
        self.assertEqual(Opportunity.objects.get(organization=self.organization).title, "Example")

    def test_dashboard_access_and_revenue_scope(self):
        for org, external_id in ((self.organization, "visible-order"), (self.other, "private-other-order")):
            MarketplaceReceipt.objects.create(
                organization=org, source="fiverr", external_id=external_id, currency="USD",
                earned_on=date(2026, 11, 2), gross=100, fee=20, direct_cost=10,
            )
        url = reverse("bara_operations") + f"?workspace={self.organization.pk}&month=2026-11"
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = get_user_model().objects.create_user("staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        owner = get_user_model().objects.create_superuser("owner", password="fixture")
        self.client.force_login(owner)
        response = self.client.get(url)
        self.assertContains(response, "visible-order")
        self.assertNotContains(response, "private-other-order")
        self.assertEqual(response.context["marketplace"][0]["margin"], 70)
