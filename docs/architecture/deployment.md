# Deployment inventory

Audit date: 2026-11-22. Repository main tracked bara/main at e0c807c and was clean before this change. The 131 tracked files use Python 3.11, Django templates/gettext, CSS and small JavaScript. No Node runtime is required. GitHub Actions pages.yml runs the static build and validator on the business repo main; validate.yml checks migrations and Django tests on SQLite and PostgreSQL, plus the static builds. The private modules run only with Django.

HTTPS was verified at https://baradev-tokyo.github.io/. The proposed baradev.tokyo name did not resolve and no CNAME was tracked. Keep the github.io canonical, language links and sitemap until DNS ownership, GitHub Pages redirect and TLS are verified. Do not expose two self-canonical sites. Existing site packages are in services/catalog.py; workflows, bilingual page text, portrait, GA4 with opt-in, Search Console metadata and appointment-page configuration are reusable.

The current laptop reports AMD Ryzen 3 2200U with Vega graphics, 19.6 GiB RAM and about 25 GiB free on the workspace drive at audit time. Docker, Ollama, llama.cpp and FFmpeg were not found on PATH. Thermals, power use and unattended reliability are unverified. Use installed Python and local SQLite for development. Treat inference and video throughput as unbenchmarked. No public listener, tunnel, scheduler or model download was installed.

Risks before private production: Django patch level, PostgreSQL concurrency, backup recovery, personal-data lifecycle, callback security, and verification of recurring costs. Package ranges are estimates; delivery days and revision commitments still need approval. Payment sandbox, live email flags, managed database automatic recovery, and production OAuth stay off in this milestone.

## Dependency inventory

- Static and local server: Python 3.11, Django 5.2.7, asgiref 3.10.0, sqlparse 0.5.3; compiled gettext messages; local CSS and JS.
- Private reporting: psycopg 3.3.9 for optional PostgreSQL, ReportLab 4.5.1 and Pillow for PDF and original draft scope cards, and Stripe Python 17.1.0 for the test-mode API. SQLite is the local default.
- Cloud libraries remain optional and unprovisioned. llama.cpp with an existing GGUF is an optional local advisory provider. Rules require only installed Python and Django. OpenAI, external publishing and live email stay off.
