from pathlib import Path

from django.core.management.base import BaseCommand

from reporting.reports import finish, render_pdf, sample_rows


class Command(BaseCommand):
    help = "Write sample HTML, plaintext and optional PDF to a local directory. Sends no email."

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--language", choices=["en", "ja"], default="ja")
        parser.add_argument("--pdf", action="store_true")

    def handle(self, *args, **options):
        folder = options["output"]
        folder.mkdir(parents=True, exist_ok=True)
        language = options["language"]
        ja = language == "ja"
        summary = finish(language, "ホスティング料金（サンプル）" if ja else "Hosting charges (sample)",
                         "", "2026-10-01 – 2026-11-01", sample_rows(ja),
                         "実際の請求額ではありません。" if ja else "This is not an invoice.")
        (folder / f"sample-{language}.html").write_text(summary.html, encoding="utf-8")
        (folder / f"sample-{language}.txt").write_text(summary.text, encoding="utf-8")
        if options["pdf"]:
            (folder / f"sample-{language}.pdf").write_bytes(render_pdf(summary))
        self.stdout.write(f"Wrote sample previews to {folder}.")
