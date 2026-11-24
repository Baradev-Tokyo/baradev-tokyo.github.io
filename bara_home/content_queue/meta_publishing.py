import re
from hashlib import sha256
from time import sleep
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from blog.social import FACEBOOK_PAGE_ID, SITE

from .instagram_oauth import NoRedirect, PROFILE_URL, fetch_json
from .models import Platform
from .services import RetryablePublishError

FACEBOOK = "https://graph.facebook.com/v27.0"
INSTAGRAM = "https://graph.instagram.com/v27.0"


def publication_id(response):
    identifier = response["id"]
    if not isinstance(identifier, str) or not re.fullmatch(r"[0-9]+(?:_[0-9]+)?", identifier):
        raise ValueError("Meta did not return a valid publication ID.")
    return identifier


class MetaPublisher:
    def __init__(self, platform, token):
        self.platform = platform
        self.token = token
        self.account_id = None
        self.image_url = None

    def request(self, url, **fields):
        body = urlencode(fields).encode("utf-8") if fields else None
        return fetch_json(Request(url, data=body, headers={"Authorization": f"Bearer {self.token}"}))

    def check(self, job):
        if self.platform == Platform.FACEBOOK:
            profile = self.request(f"{FACEBOOK}/me?fields=id")
            if profile.get("id") != FACEBOOK_PAGE_ID or job.draft.media:
                raise ValueError("Facebook needs the Bara Page token and a text-only draft.")
            return
        if self.platform != Platform.INSTAGRAM:
            raise ValueError("Unsupported channel.")
        profile = self.request(PROFILE_URL)
        account_id = str(profile.get("user_id", ""))
        if profile.get("username", "").casefold() != "baradev_tokyo" or not re.fullmatch(r"[0-9]+", account_id):
            raise ValueError("Instagram token does not identify Bara.")
        media = job.draft.media
        if not re.fullmatch(r"bara/[A-Za-z0-9_-]+\.jpe?g", media):
            raise ValueError("Instagram needs an approved public JPEG asset.")
        image_url = f"{SITE}/static/{media}"
        with build_opener(NoRedirect()).open(image_url, timeout=12) as response:
            image = response.read(8 * 1024 * 1024 + 1)
        if len(image) > 8 * 1024 * 1024 or sha256(image).digest() != sha256(job.draft.media_bytes).digest():
            raise ValueError("The live JPEG does not match the approved draft image.")
        self.account_id, self.image_url = account_id, image_url

    def publish(self, job):
        if job.platform != self.platform:
            raise ValueError("Unexpected channel.")
        if self.platform == Platform.FACEBOOK:
            return publication_id(self.request(f"{FACEBOOK}/{FACEBOOK_PAGE_ID}/feed", message=job.draft.text))
        if not self.account_id or not self.image_url:
            raise ValueError("Instagram preflight is required.")
        try:
            container = str(self.request(f"{INSTAGRAM}/{self.account_id}/media",
                                         image_url=self.image_url, caption=job.draft.text)["id"])
            if not re.fullmatch(r"[0-9]+", container):
                raise ValueError("Invalid media container.")
            for attempt in range(3):
                if attempt:
                    sleep(2)
                status = self.request(f"{INSTAGRAM}/{container}?fields=status_code")["status_code"]
                if status != "IN_PROGRESS":
                    break
            if status != "FINISHED":
                raise ValueError("Media is not ready.")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Media creation alone does not put a post on the account.
            raise RetryablePublishError from exc
        return publication_id(self.request(f"{INSTAGRAM}/{self.account_id}/media_publish", creation_id=container))
