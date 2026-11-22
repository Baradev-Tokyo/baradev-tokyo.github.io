# Bara

Bara is a Django freelance website. Customers choose a service package and submit a project brief. The brief and an editable proposal draft appear in Django admin.

## Development foundation

The [architecture audit and plan](docs/architecture/README.md) record verified hosting, the private/public boundary, data design, and approval gates. See the [Japanese SEO opportunities](docs/seo-keywords.md), [integration setup](docs/architecture/integrations.md), [Stripe Japan sandbox runbook](docs/stripe-onboarding.md), and [unpublished legal drafts](docs/legal-drafts.md).

The private Django app includes a Stripe test-mode module, a health probe at `/ops/health/`, and read-only reporting contracts. Apply migrations in your local Django environment before opening admin. Stripe requires explicit opt-in and a test key. The static portfolio never includes private routes. Environment variable names are in [the sample configuration](.env.example).

For scheduled multi-customer reports and transactional delivery, see the [reporting architecture](docs/architecture/reporting.md) and [local preview and deployment runbook](docs/reporting-setup.md). Install `requirements-reporting.txt` for PDF and PostgreSQL support. Sample and mock delivery are safe defaults.

Run all private validation from `bara_home/` with `python manage.py test` and `python manage.py makemigrations --check --dry-run`. From the repository root, run the static build and page checker below. The separate **Validate Bara foundation** workflow runs these checks without Stripe or Google credentials.

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

## Private analytics and search reporting

1. Sign in to [Google Analytics](https://analytics.google.com/) with `baradev.tokyo@gmail.com`. Create a GA4 property and a **Web** data stream for `https://baradev-tokyo.github.io`. In property and account access management, give access only to the owner account. Leave advertising integrations and enhanced measurement off. The site sends its own page views and selected clicks.
2. Copy the web stream’s public `G-…` measurement ID into the repository’s **Settings → Secrets and variables → Actions → Variables** as `BARA_GA_MEASUREMENT_ID`. Run **Publish Bara portfolio** on `main`. When the variable is blank, the build omits analytics entirely.
3. Open the rebuilt site, allow analytics in the footer, and check the GA4 Realtime report. Try a package link and an email link. `package_click`, `email_click`, and `portfolio_click` measure intent. An email click does not establish that a message was sent. Reports cover visitors who allow analytics and whose browsers permit it.
4. In **Admin → Custom definitions**, add event-scoped dimensions for `site_language` and `package_slug`. Use **Reports → Acquisition** for sources and campaigns, **Pages and screens** for readership, and **Events** for package and contact interest. Tag marketing links consistently with `utm_source`, `utm_medium`, and `utm_campaign`. Use short identifiers such as `instagram`, `social`, and `launch`. Keep personal information out of campaign tags.
5. Export reports to CSV for spreadsheets, or use the [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1) for authenticated integrations. [BigQuery export](https://support.google.com/analytics/answer/9358801) is available if raw events become necessary. Review its quotas and billing before enabling it. Keep API credentials and exports outside this public repository.

In [Search Console](https://search.google.com/search-console/), add a **URL prefix** property for `https://baradev-tokyo.github.io/` and select **HTML tag** verification. Copy only the tag’s `content` value to the Actions variable `BARA_GOOGLE_SITE_VERIFICATION`. Run the Pages workflow, verify ownership in Search Console, and submit `https://baradev-tokyo.github.io/sitemap.xml`. Search Console adds search impressions, clicks, and indexing reports alongside GA4’s on-site activity.

## Consultation booking

1. On a computer, sign in to your private Google account and choose **Create → Appointment schedule**. Create one shared booking page for all packages on your primary calendar. Start with 30-minute appointments, set the timezone to **Tokyo**, and leave only **Monday 12:00–20:00** and **Wednesday 15:00–20:00** open.
2. Enable **Check calendars for availability** on the booking account’s primary calendar. Existing events marked **Busy** will automatically remove overlapping consultation slots. The schedule itself keeps all other days and times closed. A free personal account can use one booking page. Google requires an eligible plan to check secondary calendars automatically. [Google Calendar availability](https://support.google.com/calendar/answer/16287054)
3. Set the meeting location to **Google Meet** and add a required booking question for the package name. Save, then copy the public link under **Booking pages**. Google adds confirmed bookings to your private calendar. Enable Google Calendar event notifications and Gmail alerts for that account in your phone’s settings. [Create a schedule](https://support.google.com/calendar/answer/10729749) · [Copy the booking link](https://support.google.com/calendar/answer/10733297)
4. Under **Sharing options → Website embed → Inline booking page**, copy only the public iframe `src` URL. Set the GitHub Actions repository variable `BARA_GOOGLE_BOOKING_URL` to that URL and run **Publish Bara portfolio** on `main`. **Discuss this package** opens the live Google scheduler. A short share link works as a direct link. The site embeds only the appointment page, which can display your Google account name and photo. Your calendar events stay private. This uses no Google API project, paid integration, or backend. [Share an appointment schedule](https://support.google.com/calendar/answer/10733297)
5. Before announcing the link, compare the public availability with an existing Busy appointment during consultation hours. Book one open slot with a test guest, confirm the Meet link and phone alert, then cancel the test booking. Analytics records clicks on the direct booking link as intent. Google does not send booking confirmations back to Bara’s static site.

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
