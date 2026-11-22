# Bara Development architecture

## Repository audit and implementation plan

The repository uses Python 3.11, Django templates and gettext, plain CSS and JavaScript, with no frontend build framework. The static exporter is `scripts/build_pages.py`; `scripts/check_pages.py` validates its output. GitHub Actions builds `dist/` and publishes it to GitHub Pages on business-repo main. The Django app uses SQLite locally for intake, admin and drafting. The export uses email links and never reads client records. Service tests run through Django's test runner.

HTTPS responds at `https://baradev-tokyo.github.io/`. Neither `baradev.tokyo` nor `www.baradev.tokyo` resolved in this environment on 2026-11-22. Registration and owner control are unverified. Keep the existing canonical origin and DNS unchanged until the owner verifies control, GitHub Pages domain ownership, HTTPS, redirects, and Search Console. A new hostname requires coordinated canonical, sitemap, and GA4 changes.

1. Preserve the static publishing path and extend validation as SEO and tracking evolve.
2. Add a disabled-by-default private billing sandbox and schema.
3. Establish integration and reporting contracts plus mock cost attribution.
4. Validate locally and through a separate CI workflow. Onboard real accounts only after owner approval.

The existing portrait is a 300 × 400 JPEG of about 23 KB, with intrinsic dimensions and lazy loading. Keep local system font fallbacks and avoid adding a font download. The responsive grid has breakpoints for tablet and mobile. CI validates crawlable rendered HTML, viewport metadata, headings, navigation, links and assets; a device/browser visual regression pass remains a release check.

See [system overview](system-overview.md), [data model](data-model.md), [security](security.md), [integrations](integrations.md), [cost controls](cost-controls.md), [roadmap](roadmap.md), and [decision record](decisions/0001-public-and-private-boundary.md).
