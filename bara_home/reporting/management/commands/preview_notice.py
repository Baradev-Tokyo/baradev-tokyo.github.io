from pathlib import Path

from django.core.management.base import BaseCommand

from reporting.notice_templates import NOTICES, preview_notice


class Command(BaseCommand):
    help = "Write an offline transactional email preview without sending it."

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=sorted(NOTICES))
        parser.add_argument("--language", choices=("en", "ja"), default="ja")
        parser.add_argument("--output", type=Path, required=True)

    def handle(self, *args, **options):
        kind, language, folder = options["kind"], options["language"], options["output"]
        notice = preview_notice(kind, language)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{kind}-{language}.html").write_text(notice.html, encoding="utf-8")
        (folder / f"{kind}-{language}.txt").write_text(notice.text, encoding="utf-8")
