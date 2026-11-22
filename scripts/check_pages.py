"""Validate the generated portfolio without starting Django."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree.ElementTree import parse

ROOT = Path(__file__).resolve().parents[1] / "dist"
ORIGIN = "https://baradev-tokyo.github.io"
LANGUAGES = {"": "en", "ja/": "ja"}
PAGES = ("", "services/", "about/", "contact/", "privacy/")


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids = set()
        self.links = []
        self.language = None
        self.has_form = False
        self.canonical = None
        self.alternates = {}
        self.description = None
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "html":
            self.language = attrs.get("lang")
        if tag == "form":
            self.has_form = True
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "link" and attrs.get("rel") == "alternate":
            self.alternates[attrs.get("hreflang")] = attrs.get("href")
        if tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content")
        for attribute in ("href", "src"):
            if attrs.get(attribute):
                self.links.append(attrs[attribute])


def check():
    pages = {}
    errors = []
    for prefix, language in LANGUAGES.items():
        for route in PAGES:
            url = f"/{prefix}{route}"
            page = Page((ROOT / url.strip("/") / "index.html").read_text(encoding="utf-8"))
            pages[url] = page
            if page.language != language or page.has_form:
                errors.append(f"{url}: expected {language} HTML with no form")
            if "mailto:baradev.tokyo@gmail.com" not in page.links:
                errors.append(f"{url}: missing contact address")
            alternate = f"/{'ja/' if language == 'en' else ''}{route}"
            if alternate not in page.links:
                errors.append(f"{url}: missing language switch to {alternate}")
            expected_alternates = {
                "en": f"{ORIGIN}/{route}",
                "ja": f"{ORIGIN}/ja/{route}",
                "x-default": f"{ORIGIN}/{route}",
            }
            if page.canonical != ORIGIN + url or page.alternates != expected_alternates:
                errors.append(f"{url}: invalid canonical or language alternatives")
            if not page.description:
                errors.append(f"{url}: missing search description")

    sitemap_urls = {node.text for node in parse(ROOT / "sitemap.xml").iterfind(".//{*}loc")}
    if sitemap_urls != {ORIGIN + url for url in pages}:
        errors.append("Sitemap does not match the exported pages")
    if f"Sitemap: {ORIGIN}/sitemap.xml" not in (ROOT / "robots.txt").read_text():
        errors.append("robots.txt does not advertise the sitemap")

    for url, page in pages.items():
        for link in page.links:
            target = urlsplit(link)
            if target.scheme == "http":
                errors.append(f"{url}: insecure link {link}")
            if target.scheme or target.netloc:
                continue
            path = unquote(target.path) or url
            if target.fragment and path in pages:
                if unquote(target.fragment) not in pages[path].ids:
                    errors.append(f"{url}: missing fragment {link}")
            if path not in pages and not (
                path.startswith("/static/") and (ROOT / path.lstrip("/")).is_file()
            ):
                errors.append(f"{url}: missing local link {link}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Verified {len(pages)} pages, language switches, local links, and assets.")


if __name__ == "__main__":
    check()
