"""Export Bara's public portfolio to dist/ for a root-hosted static site."""

import os
import re
from pathlib import Path
from functools import partial
import shutil
import sys
from tempfile import TemporaryDirectory
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
from home.views import home, privacy
from blog.posts import POSTS, localized_post
from blog.views import blog, blog_details
from services.catalog import PACKAGES, PACKAGE_BY_SLUG
from services.briefs import package_briefs
from services.views import package_detail, services
from services.workflows import WORKFLOWS

PUBLIC_ASSETS = ("main.css", "project-brief.js", "bara/joey.jpg")
SITE_URL = "https://baradev-tokyo.github.io"
TITLES = {
    "home": ("Tokyo Python & Django Developer | Bara Development", "東京のPython・Django開発 | Bara Development"),
    "services": ("Web Development Services and Pricing | Bara", "Web開発のサービス・料金 | Bara"),
    "about": ("Development Case Studies | Bara", "Web開発の制作実績 | Bara"),
    "contact": ("Contact for a Development Project | Bara", "Web開発のご相談 | Bara"),
    "privacy": ("Privacy Policy | Bara", "プライバシーポリシー | Bara"),
}
DESCRIPTIONS = {
    "home": ("Tokyo-based freelance Python and Django development for websites, web apps, dashboards and workflow automation.",
             "東京を拠点に、Python・Djangoを使ったWebサイト、Webアプリ、業務ダッシュボードの開発や業務自動化を行うBaraです。"),
    "services": ("Compare Bara’s freelance website, dashboard, and automation packages, with project scopes and estimates in Japanese yen.",
                 "Webサイト制作、業務ダッシュボード、業務自動化など、Baraのサービス内容と費用の目安をご覧いただけます。"),
    "about": ("Explore Bara’s case studies, including Pedal Somewhere’s tour booking site, receipt automation, and private file sharing.",
              "Pedal Somewhereの予約サイト、レシート入力の自動化、非公開ファイル共有など、Baraの制作事例をご紹介します。"),
    "contact": ("Choose a Bara development package, outline the features and design you need, and book a consultation.",
                "Baraの開発サービスを選び、ご希望の機能やデザインを整理してから、相談をご予約ください。"),
    "privacy": ("Read how Bara handles project inquiries, website analytics, and cookie preferences.",
                "Baraのお問い合わせ情報、アクセス解析、Cookie設定の取り扱いをご案内します。"),
}


def contact(request):
    return render(request, "project_start.html", {"briefs": package_briefs()})


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
                pages = [(route, {}, view) for route, view in (
                    ("home", home), ("services", services), ("about", about),
                    ("contact", contact), ("privacy", privacy),
                    ("blog", blog),
                )]
                pages.extend(("blog-details", {"slug": slug}, blog_details) for slug in POSTS)
                pages.extend(
                    ("package_detail", {"slug": package.slug}, partial(package_detail, static_export=True))
                    for package in PACKAGES
                )
                for route, kwargs, view in pages:
                    path = reverse(route, kwargs=kwargs)
                    request = HttpRequest()
                    request.method = "GET"
                    request.path = request.path_info = path
                    japanese = language == "ja"
                    if route == "package_detail":
                        package = PACKAGE_BY_SLUG[kwargs["slug"]]
                        title = f"{gettext(package.name)} | Bara"
                        description = WORKFLOWS[package.slug].description[japanese]
                    elif route == "blog-details":
                        post = localized_post(kwargs["slug"])
                        title = f"{post['title']} | Bara"
                        description = post["summary"]
                    elif route == "blog":
                        title = "Baraブログ" if japanese else "Bara Blog"
                        description = (
                            "Baraが予約システムやウェブ開発の実例と設計のヒントを紹介します。"
                            if japanese else "Practical notes from Bara on websites, booking systems, and software development."
                        )
                    else:
                        title = TITLES[route][japanese]
                        description = DESCRIPTIONS[route][japanese]
                    request.site_metadata = {
                        "canonical": SITE_URL + path,
                        "english": SITE_URL + translate_url(path, "en"),
                        "japanese": SITE_URL + translate_url(path, "ja"),
                        "description": description,
                        "title": title,
                        "image": SITE_URL + "/static/bara/joey.jpg",
                        "profile_alt": "Baraの開発者、ジョーイ" if japanese else "Joey, the developer behind Bara",
                        "business_schema": route == "home",
                        "measurement_id": measurement_id,
                        "verification": verification,
                    }
                    SubElement(SubElement(sitemap, "url"), "loc").text = SITE_URL + path
                    response = view(request, **kwargs)
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
