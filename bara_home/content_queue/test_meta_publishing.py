from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from blog.social import FACEBOOK_PAGE_ID
from operations.models import Workspace

from .meta_publishing import MetaPublisher
from .models import Platform, State
from .services import approve_draft, enqueue, save_draft, set_channel


class MetaPublishingTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser("meta-owner")
        self.workspace = Workspace.objects.create(name="Bara Development")

    def queue(self, platform, media=""):
        draft = save_draft(self.workspace.pk, platform, "Booking", "Bara booking workflow.", media)
        approve_draft(self.workspace.pk, draft.pk, self.owner)
        set_channel(self.workspace.pk, platform, False, self.owner)
        return enqueue(self.workspace.pk, draft.pk, timezone.now(), self.owner)

    @patch.dict("os.environ", {"BARA_FACEBOOK_PAGE_ACCESS_TOKEN": "test-token"})
    @patch("content_queue.meta_publishing.fetch_json")
    def test_facebook_publishes_exact_draft_as_page_only_once(self, api):
        job = self.queue(Platform.FACEBOOK)
        api.side_effect = [{"id": FACEBOOK_PAGE_ID}, {"id": f"{FACEBOOK_PAGE_ID}_123"}, {"id": FACEBOOK_PAGE_ID}]
        with self.assertRaises(CommandError):
            call_command("publish_meta_post", "facebook", str(job.pk), confirm_draft=job.draft_id + 1)
        api.assert_not_called()
        call_command("publish_meta_post", "facebook", str(job.pk), confirm_draft=job.draft_id, stdout=StringIO())
        job.refresh_from_db()
        self.assertEqual(job.state, State.PUBLISHED)
        post = api.call_args_list[1].args[0]
        self.assertTrue(post.full_url.endswith(f"/{FACEBOOK_PAGE_ID}/feed"))
        self.assertEqual(parse_qs(post.data.decode()), {"message": [job.draft.text]})
        with self.assertRaises(CommandError):
            call_command("publish_meta_post", "facebook", str(job.pk), confirm_draft=job.draft_id)
        self.assertEqual(sum(call.args[0].get_method() == "POST" for call in api.call_args_list), 1)

    @patch("content_queue.meta_publishing.build_opener")
    @patch("content_queue.meta_publishing.fetch_json")
    @patch("content_queue.meta_publishing.sleep")
    def test_instagram_checks_live_media_then_uses_ready_container(self, wait, api, opener):
        job = self.queue(Platform.INSTAGRAM, "bara/joey.jpg")
        file = opener.return_value.open.return_value.__enter__.return_value
        file.read.return_value = bytes(job.draft.media_bytes)
        api.side_effect = [
            {"username": "baradev_tokyo", "user_id": "100"}, {"id": "200"},
            {"status_code": "IN_PROGRESS"}, {"status_code": "FINISHED"}, {"id": "300"},
        ]
        publisher = MetaPublisher(Platform.INSTAGRAM, "test-token")
        publisher.check(job)
        self.assertEqual(publisher.publish(job), "300")
        wait.assert_called_once_with(2)
        self.assertEqual(parse_qs(api.call_args.args[0].data.decode()), {"creation_id": ["200"]})
