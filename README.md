# Bara

Bara is a Django freelance website. Customers choose a service package and submit a project brief. The brief and an editable proposal draft appear in Django admin.

## Hosting the public portfolio

The same Django templates can generate English and Japanese static pages for a root-hosted URL. The export includes the homepage, service packages, case studies, and an email contact page. Package links take visitors to a prefilled email subject. The export needs Python 3.11 and the existing requirements. It reads no inquiry data and needs no database migration, Django secret key, third-party API, or Node build.

```powershell
.venv/Scripts/python scripts/build_pages.py
.venv/Scripts/python scripts/check_pages.py
.venv/Scripts/python -m http.server --bind 127.0.0.1 --directory dist 8001
```

Open `http://127.0.0.1:8001/` or `http://127.0.0.1:8001/ja/`. Each build replaces the generated, Git-ignored `dist/` directory. To update translations, edit `bara_home/locale/ja/LC_MESSAGES/django.po` and regenerate the tracked `.mo` with `django-admin compilemessages -l ja` from `bara_home/` with GNU gettext installed.

### Publish under the business account

Read [GitHub Pages usage limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) before publishing. The export is for an informational portfolio. Keep online intake, agreements, payments, and other business operations off Pages. If the public site will primarily facilitate freelance sales, use a host that supports that use. [Cloudflare Pages](https://developers.cloudflare.com/pages/) can publish the same `dist/` output on a free `pages.dev` address.

1. Sign in to GitHub as `baradev-tokyo` and create an empty public repository named `baradev-tokyo.github.io` if it is missing. Leave README, license, and gitignore initialization unchecked so the push can carry the existing history.
2. Authenticate Git as the business account. With [GitHub CLI](https://cli.github.com/), run `gh auth login --hostname github.com --git-protocol https --web --scopes workflow`, choose the business account in the browser, and verify `gh api user --jq .login` returns `baradev-tokyo`. If both accounts are already configured in the CLI, use `gh auth switch --hostname github.com --user baradev-tokyo` and grant workflow access with `gh auth refresh --hostname github.com --scopes workflow` if needed. Run `gh auth setup-git --hostname github.com` to let Git use that login.
3. From the Bara repository, review and commit the local changes, then add and push only the business remote.

   ```powershell
   git status --short
   git add -- .github/workflows/pages.yml scripts/build_pages.py scripts/check_pages.py README.md bara_home front-end
   git diff --cached --stat
   git diff --cached --check
   git commit -m "Prepare bilingual Bara portfolio for GitHub Pages"
   git remote add bara https://github.com/baradev-tokyo/baradev-tokyo.github.io.git
   git remote -v
   git push bara HEAD:main
   ```

4. In the business repository, open **Settings → Pages → Build and deployment** and select **GitHub Actions** as the source. Open **Actions → Publish Bara portfolio**, run it on `main`, and check the deployment URL. If the first push ran before Pages was enabled, this manual run publishes it. Confirm **Enforce HTTPS** in Pages settings and open `https://baradev-tokyo.github.io`.

Future pushes to the business repository’s `main` build and validate `dist/`, then deploy that artifact. The workflow is scoped to `baradev-tokyo/baradev-tokyo.github.io`. The original repository stays on the existing `origin` remote.

### Where the Django workflow runs

The public export uses email for inquiries. The original Django site still saves submissions, creates proposal drafts, and generates private agreement drafts in admin. Keep it local for ¥0 hosting costs. An online version would need separate HTTPS-capable Python hosting, persistent storage, and production settings for the Django secret, allowed hosts, and secure cookies. One low-traffic option to evaluate is Render free compute with a separate durable PostgreSQL provider such as Neon. Render’s free filesystem is ephemeral, and Render’s own free PostgreSQL expires after 30 days. That setup requires a database configuration change and depends on both providers’ quotas. [Render free limits](https://render.com/docs/free) · [Neon free plan](https://neon.com/pricing)

## Run locally

Use Python 3.11+ and run these commands from the repository root in PowerShell.

```powershell
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
$env:DJANGO_SECRET_KEY = 'local-development-only'
$env:DEBUG = 'True'
$env:ALLOWED_HOSTS = 'localhost,127.0.0.1'
.venv/Scripts/python bara_home/manage.py migrate
.venv/Scripts/python bara_home/manage.py createsuperuser
.venv/Scripts/python bara_home/manage.py runserver
```

Open `http://127.0.0.1:8000/` for the site or `http://127.0.0.1:8000/admin/` for the owner dashboard. Check **Project requests** for submissions. The form saves requests to the database.

The homepage portrait is stored at `front-end/static/bara/joey.jpg`. The static portfolio build includes this file.

## Proposal and contract workflow

1. Open a project request in Django admin. Edit the draft to reflect the agreed scope, deliverables, dates, fee, and payment schedule. Download the proposal from the request page for review.
2. In **Agreement templates**, create a reusable template from your reviewed contract wording. Replace client-specific terms with `${client_name}`, `${provider_name}`, and `${proposal}` where the names and agreed scope belong. Write a literal dollar sign as `$$`.
3. Enter both parties’ legal names on the request, select the agreement template, and save.
4. In **Project requests**, select that request and run **Approve saved proposal and create contract draft**. The approved proposal and generated contract are stored together. Reopen the request to download both as UTF-8 text files.

Paste the approved PedalSomewhere contract into the agreement template when available, removing project-specific details before reuse. Match the initial proposal structure in `bara_home/services/views.py` to the PedalSomewhere proposal when that document is available.

## Pricing basis

The package definitions and JPY planning ranges live in `bara_home/services/catalog.py`. These are suggested prices for the listed scope. Confirm taxes, recurring costs, and final fees in each proposal.

| Package | Range | Reference |
| --- | ---: | --- |
| Landing page | ¥100,000–¥160,000 | [Doers](https://doers-tokyo.jp/service-web) lists landing pages from ¥100,000. |
| Small business website | ¥220,000–¥380,000 | [JAJAAN](https://jajaaan.co.jp/service/web/) lists small sites at ¥100,000–¥500,000. |
| Japanese / English website | ¥250,000–¥500,000 | [LUMA](https://studio-lumadesign.com/service-web) lists ¥242,000 for a bilingual landing page and ¥550,000 for a bilingual five-page site with copywriting. Bara assumes supplied copy. |
| Operations dashboard | ¥300,000–¥550,000 | [Kobe Soft](https://kobesoft.co.jp/business-system/pricing/) prices external integration from ¥200,000 per connection. Bara adds charting, filtering and access around one source. |
| Workflow automation | ¥180,000–¥400,000 | [NODE](https://nodelabs.co.jp/price.html) starts automation at ¥100,000. Bara’s estimate includes validation and handling failures across up to two systems. |
| Custom internal tool | ¥500,000–¥950,000 | [TIFFIN](https://www.tiffin.one/price) lists small systems for one business workflow from ¥500,000. |

Run the workflow tests with `.venv/Scripts/python bara_home/manage.py test services`.
