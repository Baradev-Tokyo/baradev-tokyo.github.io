"""Export Bara's public portfolio to dist/ for a root-hosted static site."""

import os
import re
from pathlib import Path
from functools import partial
import shutil
import sys
from tempfile import TemporaryDirectory
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, tostring

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
sys.path.insert(0, str(ROOT / "bara_home"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.staticfiles import finders
from django.http import HttpRequest
from django.shortcuts import render
from django.urls import reverse, translate_url
from django.utils.translation import gettext, override

from about.views import about
from home.views import home
from services.catalog import PACKAGES
from services.views import services

PUBLIC_ASSETS = ("main.css", "bara/joey.jpg")
SITE_URL = "https://baradev-tokyo.github.io"
DESCRIPTIONS = {
    "home": ("Tokyo-based freelance Python and Django development for websites, web apps, dashboards and workflow automation.",
             "東京を拠点に、Python・Djangoを使ったWebサイト、Webアプリ、業務ダッシュボードの開発や業務自動化を行うBaraです。"),
    "services": ("Compare Bara’s freelance website, dashboard, and automation packages, with project scopes and estimates in Japanese yen.",
                 "Webサイト制作、業務ダッシュボード、業務自動化など、Baraのサービス内容と費用の目安をご覧いただけます。"),
    "about": ("Explore Bara’s case studies, including Pedal Somewhere’s tour booking site, receipt automation, and private file sharing.",
              "Pedal Somewhereの予約サイト、レシート入力の自動化、非公開ファイル共有など、Baraの制作事例をご紹介します。"),
    "contact": ("Email Bara to discuss a freelance software or website project, including your goals, preferred package, and timing.",
                "Webサイト制作や業務ツール開発のご相談はBaraへ。ご希望のサービス、目的、希望時期をメールでお知らせください。"),
}


def contact(request):
    links = [
        (package.slug, gettext(package.name), "mailto:baradev.tokyo@gmail.com?subject="
         + quote(f"{gettext('Project inquiry')} — {gettext(package.name)}"))
        for package in PACKAGES
    ]
    return render(request, "contact.html", {"email_packages": links})


def export():
    # Render into a fresh sibling folder before replacing the generated export.
    if OUTPUT.resolve() != OUTPUT:
        raise RuntimeError("The dist output must be a directory inside the repository.")
    measurement_id = os.getenv("BARA_GA_MEASUREMENT_ID", "").strip()
    verification = os.getenv("BARA_GOOGLE_SITE_VERIFICATION", "").strip()
    if measurement_id and not re.fullmatch(r"G-[A-Z0-9]{5,20}", measurement_id):
        raise ValueError("BARA_GA_MEASUREMENT_ID must be a GA4 web measurement ID.")
    sitemap = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    with TemporaryDirectory(dir=ROOT) as directory:
        staging = Path(directory)
        assets = (*PUBLIC_ASSETS, "analytics.js") if measurement_id else PUBLIC_ASSETS
        for asset in assets:
            source = finders.find(asset)
            if not source:
                raise FileNotFoundError(asset)
            target = staging / "static" / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

        for language in ("en", "ja"):
            with override(language):
                for route, view in (
                    ("home", home), ("services", partial(services, static_export=True)),
                    ("about", about), ("contact", contact),
                ):
                    path = reverse(route)
                    request = HttpRequest()
                    request.method = "GET"
                    request.path = request.path_info = path
                    request.site_metadata = {
                        "canonical": SITE_URL + path,
                        "english": SITE_URL + translate_url(path, "en"),
                        "japanese": SITE_URL + translate_url(path, "ja"),
                        "description": DESCRIPTIONS[route][language == "ja"],
                        "measurement_id": measurement_id,
                        "verification": verification,
                    }
                    SubElement(SubElement(sitemap, "url"), "loc").text = SITE_URL + path
                    response = view(request)
                    if response.status_code != 200:
                        raise RuntimeError(f"{path} returned HTTP {response.status_code}")
                    target = staging / path.strip("/") / "index.html"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(response.content)
        (staging / ".nojekyll").touch()
        (staging / "sitemap.xml").write_bytes(tostring(sitemap, encoding="utf-8", xml_declaration=True))
        (staging / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8"
        )

        if OUTPUT.exists():
            shutil.rmtree(OUTPUT)
        shutil.copytree(staging, OUTPUT)


if __name__ == "__main__":
    export()
    print(f"Exported English and Japanese portfolio pages to {OUTPUT}")
