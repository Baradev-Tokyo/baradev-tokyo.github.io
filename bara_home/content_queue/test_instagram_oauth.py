from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .instagram_oauth import REDIRECT_URI


class InstagramOAuthTests(TestCase):
    def setUp(self):
        self.start = reverse("instagram_oauth_start")
        self.callback = reverse("instagram_oauth_callback")

    def test_callback_requires_secure_owner_session(self):
        self.assertEqual(self.client.get(self.callback, secure=True).status_code, 302)
        self.client.force_login(get_user_model().objects.create_user("staff", is_staff=True))
        self.assertEqual(self.client.get(self.callback, secure=True).status_code, 403)
        self.client.force_login(get_user_model().objects.create_superuser("owner"))
        self.assertEqual(self.client.get(self.callback).status_code, 403)
        self.assertEqual(self.client.get(self.callback, secure=True).status_code, 400)

    @patch.dict("os.environ", {"BARA_INSTAGRAM_APP_ID": "123", "BARA_INSTAGRAM_APP_SECRET": "fixture"})
    @patch("content_queue.instagram_oauth.fetch_json")
    def test_code_exchange_verifies_account_without_exposing_token(self, fetch):
        self.client.force_login(get_user_model().objects.create_superuser("owner"))
        response = self.client.post(self.start, secure=True)
        params = parse_qs(urlsplit(response["Location"]).query)
        self.assertEqual(params["redirect_uri"], [REDIRECT_URI])
        callback = {"state": params["state"][0], "code": "fixture-code"}
        fetch.side_effect = [{"access_token": "private-token"}, {"username": "baradev_tokyo"}]
        response = self.client.get(self.callback, callback, secure=True)
        self.assertContains(response, "Verified @baradev_tokyo")
        self.assertNotContains(response, "private-token")
        self.assertEqual(self.client.get(self.callback, callback, secure=True).status_code, 400)
        self.assertEqual(fetch.call_count, 2)
