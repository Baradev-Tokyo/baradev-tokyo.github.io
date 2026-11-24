import os
from urllib.request import Request

from django.core.management.base import BaseCommand, CommandError

from blog.social import FACEBOOK_PAGE_ID, YOUTUBE_CHANNEL_ID
from content_queue.instagram_oauth import PROFILE_URL, fetch_json


# Fixed endpoints avoid sending credentials to addresses supplied by operators.
CHECKS = {
    "instagram": ("BARA_INSTAGRAM_ACCESS_TOKEN", PROFILE_URL),
    "facebook": ("BARA_FACEBOOK_PAGE_ACCESS_TOKEN", "https://graph.facebook.com/v27.0/me?fields=id%2Cname"),
    "tiktok": ("BARA_TIKTOK_ACCESS_TOKEN", "https://open.tiktokapis.com/v2/user/info/?fields=open_id%2Cdisplay_name"),
    "youtube": ("BARA_YOUTUBE_ACCESS_TOKEN", "https://www.googleapis.com/youtube/v3/channels?part=id%2Csnippet&mine=true"),
}
EXPECTED_IDS = {"instagram": "baradev_tokyo", "facebook": FACEBOOK_PAGE_ID, "youtube": YOUTUBE_CHANNEL_ID}


def account_ids(channel, result):
    if channel == "instagram":
        return {result["username"].casefold()}
    if channel == "facebook":
        return {result["id"]}
    if channel == "tiktok":
        return {result["data"]["user"]["open_id"]}
    return {item["id"] for item in result["items"]}


class Command(BaseCommand):
    help = "Verify an authorized social account with one official read-only API request."

    def add_arguments(self, parser):
        parser.add_argument("channel", choices=CHECKS)
        parser.add_argument("--expected-id", help="Expected TikTok open ID. Other channels are pinned to Bara.")

    def handle(self, *args, **options):
        channel = options["channel"]
        variable, endpoint = CHECKS[channel]
        token = os.getenv(variable, "")
        expected = EXPECTED_IDS.get(channel) or options["expected_id"]
        if not token or not expected:
            raise CommandError(f"Set {variable} privately and specify the expected account identifier if required.")
        try:
            result = fetch_json(Request(endpoint, headers={"Authorization": f"Bearer {token}"}))
            actual = account_ids(channel, result)
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise CommandError("The channel API rejected the connection or did not return an account.") from None
        if expected not in actual:
            raise CommandError("The credential belongs to a different account than expected.")
        self.stdout.write(self.style.SUCCESS(f"{channel}: verified account identity. No publication requested."))
