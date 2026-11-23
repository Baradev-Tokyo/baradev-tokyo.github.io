import json

from django.core.management.base import BaseCommand
from django.utils.translation import override

from blog.posts import POSTS
from blog.social import preview_social_post


class Command(BaseCommand):
    help = "Generate X and Instagram copy from an existing Bara article for owner review."

    def add_arguments(self, parser):
        parser.add_argument("slug", nargs="?", choices=POSTS)
        parser.add_argument("--language", choices=["en", "ja"], default="ja")

    def handle(self, *args, **options):
        slug = options["slug"]
        language = options["language"]
        with override(language):
            if slug:
                copy = preview_social_post(slug)
            else:
                copy = {post_slug: preview_social_post(post_slug) for post_slug in POSTS}
        # ASCII-safe JSON also works when Windows redirects stdout to a legacy code page.
        self.stdout.write(json.dumps(copy, indent=2))
