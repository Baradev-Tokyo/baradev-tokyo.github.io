from urllib.parse import urlencode

from django.urls import reverse

from blog.posts import localized_post

SITE = "https://baradev-tokyo.github.io"

SOCIAL_PROFILES = {
    "x": {"name": "X", "url": "https://x.com/BaraDev_Tokyo"},
    "instagram": {"name": "Instagram", "url": "https://www.instagram.com/baradev_tokyo/"},
}


def preview_social_post(slug):
    post = localized_post(slug)
    article = SITE + reverse("blog-details", kwargs={"slug": slug})
    previews = {}
    for platform, profile in SOCIAL_PROFILES.items():
        campaign = urlencode({
            "utm_source": platform, "utm_medium": "organic_social", "utm_campaign": post["slug"],
        })
        url = f"{article}?{campaign}"
        text = f"{post['title']}\n\n{post['summary']}"
        previews[platform] = {
            "profile": profile["url"],
            "caption": f"{text}\n\n{url}" if platform == "x" else text,
            "link": url,
        }
    return previews
