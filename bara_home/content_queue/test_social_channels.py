from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blog.social import preview_social_post
from operations.models import Workspace

from .models import Platform
from .services import approve_draft, enqueue, save_draft, set_channel


class SocialChannelTests(TestCase):
    def test_blog_content_reaches_every_enabled_draft_channel(self):
        drafts = preview_social_post("planning-an-online-booking-flow")
        self.assertEqual(set(drafts), {"x", "instagram", "facebook", "tiktok", "youtube"})
        for platform, draft in drafts.items():
            self.assertIn(f"utm_source={platform}", draft["link"])
        self.assertIn("script", drafts["tiktok"])
        self.assertIn("script", drafts["youtube"])
        self.assertEqual(drafts["facebook"]["profile"], "https://www.facebook.com/profile.php?id=61596766684598")
        self.assertEqual(drafts["youtube"]["profile"], "https://www.youtube.com/channel/UCAfavGir3_KLhu5pc_0luIw")

    def test_x_compose_requires_resumed_channel_and_linkedin_stays_paused(self):
        owner = get_user_model().objects.create_superuser("social-owner")
        workspace = Workspace.objects.create(name="Social")
        draft = save_draft(workspace.pk, Platform.X, "Booking", "Plan bookings & payment together.")
        approve_draft(workspace.pk, draft.pk, owner)
        post = enqueue(workspace.pk, draft.pk, timezone.now(), owner)
        url = reverse("content_queue:calendar") + f"?workspace={workspace.pk}&job={post.pk}"
        self.client.force_login(owner)
        self.assertNotContains(self.client.get(url), "Open draft in X composer")
        set_channel(workspace.pk, Platform.X, False, owner)
        self.assertContains(self.client.get(url), "Open draft in X composer")
        self.assertContains(self.client.get(url), "%26")
        with self.assertRaises(ValidationError):
            set_channel(workspace.pk, Platform.LINKEDIN, False, owner)

    @patch.dict("os.environ", {"BARA_INSTAGRAM_ACCESS_TOKEN": "fixture-token"})
    @patch("content_queue.management.commands.check_social_connection.fetch_json")
    def test_api_probe_checks_expected_account_and_never_prints_credential(self, fetch):
        output = StringIO()
        fetch.return_value = {"username": "baradev_tokyo"}
        call_command("check_social_connection", "instagram", stdout=output)
        request = fetch.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertNotIn("fixture-token", request.full_url)
        self.assertNotIn("fixture-token", output.getvalue())
        fetch.return_value = {"username": "another-account"}
        with self.assertRaises(CommandError):
            call_command("check_social_connection", "instagram", stdout=output)
