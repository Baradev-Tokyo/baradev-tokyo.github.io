from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from operations.models import Workspace

from .models import ContentDraft, ContentPoolEntry, PublicationJob, State


class ContentPoolTests(TestCase):
    def test_saved_link_requires_owner_and_only_creates_an_unapproved_draft(self):
        users = get_user_model().objects
        workspace = Workspace.objects.create(name="Bara")
        other = Workspace.objects.create(name="Other")
        url = reverse("content_queue:pool", args=[workspace.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(users.create_user("staff", is_staff=True))
        self.assertEqual(self.client.post(url, {"action": "add"}).status_code, 403)
        self.client.force_login(users.create_superuser("owner"))
        for suffix in ("#one", "#two"):
            self.assertEqual(self.client.post(url, {
                "action": "add", "url": "https://example.com/meme" + suffix, "note": "Keep this private.",
            }).status_code, 302)
        entry = ContentPoolEntry.objects.get(workspace=workspace)
        draft_url = f"{url}?entry={entry.pk}"
        wrong_url = reverse("content_queue:pool", args=[other.pk]) + f"?entry={entry.pk}"
        self.assertEqual(self.client.get(wrong_url).status_code, 404)
        self.assertContains(self.client.get(draft_url), "Open original source")
        self.assertEqual(self.client.post(draft_url, {
            "action": "draft", "platform": "facebook", "commentary": "My take on this example.",
        }).status_code, 302)
        draft = ContentDraft.objects.get(workspace=workspace)
        self.assertIn("https://example.com/meme", draft.text)
        self.assertNotIn("Keep this private.", draft.text)
        self.assertEqual(draft.state, State.NEEDS_APPROVAL)
        self.assertFalse(PublicationJob.objects.exists())
