"""Export Bara's public portfolio to dist/ for a root-hosted static site."""

import os
from pathlib import Path
from functools import partial
import shutil
import sys
from tempfile import TemporaryDirectory
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
sys.path.insert(0, str(ROOT / "bara_home"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.staticfiles import finders
from django.http import HttpRequest
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext, override

from about.views import about
from home.views import home
from services.catalog import PACKAGES
from services.views import services

PUBLIC_ASSETS = ("main.css", "bara/joey.jpg")


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
    with TemporaryDirectory(dir=ROOT) as directory:
        staging = Path(directory)
        for asset in PUBLIC_ASSETS:
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
                    response = view(request)
                    if response.status_code != 200:
                        raise RuntimeError(f"{path} returned HTTP {response.status_code}")
                    target = staging / path.strip("/") / "index.html"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(response.content)
        (staging / ".nojekyll").touch()

        if OUTPUT.exists():
            shutil.rmtree(OUTPUT)
        shutil.copytree(staging, OUTPUT)


if __name__ == "__main__":
    export()
    print(f"Exported English and Japanese portfolio pages to {OUTPUT}")
