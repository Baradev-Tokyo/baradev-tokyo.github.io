from urllib.parse import urlencode

from django.urls import reverse

from blog.posts import localized_post

SITE = "https://baradev-tokyo.github.io"
FACEBOOK_PAGE_ID = "61596766684598"
YOUTUBE_CHANNEL_ID = "UCAfavGir3_KLhu5pc_0luIw"

SOCIAL_PROFILES = {
    "x": {"name": "X", "url": "https://x.com/BaraDev_Tokyo"},
    "instagram": {"name": "Instagram", "url": "https://www.instagram.com/baradev_tokyo/"},
    "facebook": {"name": "Facebook", "url": f"https://www.facebook.com/profile.php?id={FACEBOOK_PAGE_ID}"},
    "youtube": {"name": "YouTube", "url": f"https://www.youtube.com/channel/{YOUTUBE_CHANNEL_ID}"},
}

SOCIAL_CHANNELS = (*SOCIAL_PROFILES, "tiktok")


def preview_social_post(slug):
    post = localized_post(slug)
    article = SITE + reverse("blog-details", kwargs={"slug": slug})
    previews = {}
    for platform in SOCIAL_CHANNELS:
        campaign = urlencode({
            "utm_source": platform, "utm_medium": "organic_social", "utm_campaign": post["slug"],
        })
        url = f"{article}?{campaign}"
        text = f"{post['title']}\n\n{post['summary']}"
        previews[platform] = {
            "profile": SOCIAL_PROFILES.get(platform, {}).get("url"),
            "caption": f"{text}\n\n{url}" if platform in {"x", "facebook", "youtube"} else text,
            "link": url,
        }
        if platform in {"tiktok", "youtube"}:
            previews[platform]["script"] = "\n\n".join((post["title"], *post["paragraphs"]))
    return previews
