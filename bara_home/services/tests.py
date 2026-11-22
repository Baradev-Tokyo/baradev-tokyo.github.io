from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import AgreementTemplateForm
from .models import AgreementTemplate, ProjectRequest


class ProjectWorkflowTests(TestCase):
    def setUp(self):
        self.client_data = {
            "package": "automation",
            "name": "Demo Client",
            "email": "demo@example.com",
            "company": "Demo Company",
            "brief": "Sync completed orders to our spreadsheet.",
            "target_date": "2027-02-01",
        }

    def test_package_selection_and_submission(self):
        response = self.client.get(reverse("services"))
        self.assertContains(response, f'{reverse("contact")}?package=automation')
        response = self.client.get(reverse("contact"), {"package": "automation"})
        self.assertEqual(response.context["form"]["package"].value(), "automation")

        response = self.client.post(reverse("contact"), self.client_data)
        self.assertRedirects(response, reverse("request_received"))
        project = ProjectRequest.objects.get()
        self.assertEqual(project.package, "Workflow automation")
        self.assertIn("¥180,000–¥400,000", project.proposal)
        self.assertIn(self.client_data["brief"], project.proposal)
        self.assertIsNone(project.contract_created_at)

    def test_reject_invalid_package_and_missing_csrf(self):
        response = self.client.post("/contact/", {**self.client_data, "package": "unknown"})
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(ProjectRequest.objects.exists())

        csrf_client = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(csrf_client.post("/contact/", self.client_data).status_code, 403)

    def test_template_validation(self):
        form = AgreementTemplateForm({"name": "Incomplete", "body": "${client_name} ${unknown}"})
        self.assertFalse(form.is_valid())

    def test_japanese_public_pages_and_intake(self):
        english = self.client.get("/contact/?package=automation", HTTP_ACCEPT_LANGUAGE="ja")
        self.assertContains(english, 'lang="en"')
        self.assertContains(english, 'href="/ja/contact/?package=automation"')
        self.assertContains(english, 'mailto:baradev.tokyo@gmail.com')
        for path, heading in (
            ("/ja/", "ご相談からご提案まで"),
            ("/ja/services/", "「業務自動化」を選ぶ"),
            ("/ja/about/", "メールの自動返信"),
            ("/ja/contact/?package=automation", "ご希望のサービス"),
            ("/ja/contact/received/", "ご相談を受け付けました"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, 'lang="ja"')
                self.assertContains(response, heading)
                self.assertContains(response, 'mailto:baradev.tokyo@gmail.com')

        response = self.client.get("/ja/contact/?package=automation")
        self.assertContains(response, 'href="/contact/?package=automation"')
        self.assertContains(response, '<option value="automation" selected>業務自動化</option>')
        response = self.client.post("/ja/contact/", self.client_data)
        self.assertRedirects(response, "/ja/contact/received/")
        self.assertEqual(ProjectRequest.objects.get().package, "Workflow automation")

    def test_admin_contract_generation_and_download(self):
        self.client.post(reverse("contact"), self.client_data)
        project = ProjectRequest.objects.get()
        contract_url = reverse("admin:services_projectrequest_download", args=(project.pk, "contract"))
        self.assertEqual(self.client.get(contract_url).status_code, 302)

        owner = get_user_model().objects.create_superuser("owner", password="test-only")
        self.client.force_login(owner)
        self.assertEqual(self.client.get(contract_url).status_code, 404)
        admin_list = reverse("admin:services_projectrequest_changelist")
        action_data = {"action": "create_contract", "_selected_action": [project.pk], "index": "0"}
        self.client.post(admin_list, action_data)
        project.refresh_from_db()
        self.assertIsNone(project.contract_created_at)

        template = AgreementTemplate.objects.create(
            name="Sample", body="${provider_name} | ${client_name}\n\n${proposal}"
        )
        admin_edit = reverse("admin:services_projectrequest_change", args=(project.pk,))
        proposal = "Reviewed scope and agreed fee."
        response = self.client.post(admin_edit, {
            "proposal": proposal,
            "client_legal_name": "Demo Client Ltd",
            "provider_legal_name": "Bara Demo",
            "agreement_template": template.pk,
            "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.client.post(admin_list, action_data)
        project.refresh_from_db()
        self.assertEqual(project.approved_proposal, proposal)
        self.assertIn(f"Bara Demo | Demo Client Ltd\n\n{proposal}", project.contract_draft)

        self.client.post(admin_list, action_data)
        response = self.client.get(contract_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), project.contract_draft)
        self.assertIn("attachment", response.headers["Content-Disposition"])
