# Reporting deployment and approvals

The public portfolio and GA4 consent flow stay on GitHub Pages. Reports, email webhooks, and Django admin run only on the private backend. Start with a sandbox workspace, fake recipients, sample inputs, and mock delivery. No external resource has been provisioned by this change.

## Local acceptance

Install requirements-reporting.txt, set DJANGO_SECRET_KEY, and migrate the local Django DB. Run from the repository root:

```powershell
.venv/Scripts/python -m pip install -r requirements-reporting.txt
.venv/Scripts/python bara_home/manage.py migrate
.venv/Scripts/python bara_home/manage.py preview_report --output dist-report-preview --language ja --pdf
.venv/Scripts/python bara_home/manage.py preview_report --output dist-report-preview --language en --pdf
.venv/Scripts/python bara_home/manage.py run_reporting
```

Use a local output directory outside the GitHub Pages artifact. The preview commands never send email. The Japanese PDF uses a CID font. Check it in the PDF readers your customers use before enabling attachment distribution. The shipped email contains an HTML and text summary; artifacts stay in owner-only admin.

In Django admin, create or select the Workspace, add a contact, verify mailbox control or obtain documented customer authorization, then add the exact address with a verified timestamp. Choose the report kind, start period, timezone, lag, and recipients. New configurations are inactive and sample by default. Use **Report runs** and **Report deliveries** with the status filters to investigate terminal failures. **Report artifacts** provides expiring owner-only downloads.

Use `run_reporting --schedule-at 2026-11-03T09:00:00+09:00` to replay calendar evaluation for an older slot. The worker processes the latest closed eligible period on normal runs; replay each missing period after an outage spanning more than one cadence. Existing completed runs are not resent. An ambiguous live send after expiry needs provider-log reconciliation, then explicit owner action if replacement is warranted.

## Cloud Run Job

1. Approve the billing account, project, region, cost alert, data processor arrangements and retention. Configure encrypted PostgreSQL with backups and a restore test, separate runtime and migration roles, and TLS verification (`BARA_DB_SSLMODE=verify-full`, CA if needed via `PGSSLROOTCERT`). Apply migrations once via an authorized administrative task.
2. Build the image from tracked sources with `docker build -f Dockerfile.reporting .`. Create a single-task Cloud Run Job with bounded task timeout and low platform retry count. Set entry parameters `--limit 25`. The job refuses SQLite. Store Django and database secrets in Secret Manager and grant the job identity access only to the specific secrets. Give Cloud Scheduler a separate identity with `roles/run.invoker` on this job only.
3. Create one Cloud Scheduler job, for example every 15 minutes, using OAuth to POST to `https://run.googleapis.com/v2/projects/PROJECT/locations/REGION/jobs/JOB:run`. Use Asia/Tokyo by default. The worker checks each configuration's timezone and period. Enable a Cloud Logging alert for `bara_reporting_terminal` and job execution failures. Treat terminal delivery, bounce or complaint alerts as review work. Retries stay in the queue. [Cloud Scheduler → Cloud Run Jobs](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)
4. For an approved production network, expose only the signed email webhook and Stripe webhook as required through controlled HTTPS routing. Protect Django admin separately with owner authentication. Keep the optional GCS bucket private and defer signed customer links until there is an organization-scoped customer authentication flow.

## Supabase Free recovery

Use one Supabase Free project for reporting. For an IPv4 connection, use the Session pooler host, port and project-qualified role from the Supabase Connect dialog. Enforce TLS. Keep encrypted logical backups outside Supabase and test restoration regularly. Supabase checks for low activity over a seven-day period. Normal scheduled work can generate database activity, but pause prevention and uptime are not guaranteed. [Supabase Free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)

The external Cloud Scheduler job is the recovery trigger. It can run even when Supabase is paused. Before reporting, the worker checks PostgreSQL. If it cannot connect, it checks the exact project's Management API status. With explicit opt-in, confirmed `INACTIVE` status triggers the provider's resume API. The worker waits for PostgreSQL to accept a SQL query before processing reports. Other connection errors receive bounded retries without a project restart. The next trigger can try again, and existing report idempotency keys protect against duplicates. [Supabase project resume API](https://supabase.com/docs/reference/api/v1-restore-a-project)

To enable this for the dedicated reporting project, set `BARA_SUPABASE_PROJECT_REF` and store `BARA_SUPABASE_MANAGEMENT_TOKEN` in Secret Manager. Use a fine-grained token limited to this project and Project Settings read/write, which covers both read and resume. The grant can also authorize other project changes. Keep the token out of the web app, GitHub Pages and repository; bind it only to the job service account. Set `BARA_SUPABASE_AUTO_RESUME=true` after verifying the configuration. Disable it before intentionally pausing the project. If the API denies restoration, inspect the dashboard and resume manually. Configure an alert for persistent job failures containing `bara_reporting_database_unavailable`. [Supabase token scopes](https://supabase.com/docs/guides/platform/personal-access-tokens)

## Cloud inputs

Install requirements-reporting-gcp.txt in an approved import runtime with Application Default Credentials. Create billing periods explicitly or feed them from an approved billing-calendar job. Run the import before the first report eligible date, with enough delay for billing-export corrections. There is no automatic cloud import or service restriction until that job is configured.

- Enable Cloud Billing detailed export and create an authorized view with `source_key STRING, day DATE, project STRING, resource STRING, service STRING, currency STRING, cost NUMERIC, credits NUMERIC`. The source key must uniquely represent the aggregating dimensions and remain stable across corrected exports. Pre-allocate approved shared-resource shares in the view to distinct mapped resources. Avoid double counting from unnesting repeated credits. Grant BigQuery job execution and view read access to the import identity only. The query bounds days, projects, rows and billed bytes.
- Use `python bara_home/manage.py sync_reporting_inputs PERIOD_ID --billing-view PROJECT.DATASET.VIEW`. Imports are estimated unless a reviewed finalized import uses `--finalized-costs`. Define currency, taxes and charges separately on the billing period. A zero or missing import is not proof of a zero bill. Projection margin excludes payment fees; reconciled net profitability needs fees and refunds from a future settlement import.
- For Cloud Monitoring, grant the role needed to read time series. Verify that the configured uptime check really targets the specified owned resource before using `sync_reporting_inputs PERIOD_ID --ownership-id ID --uptime-check CHECK_ID`. Use one approved check per owned resource. Cross-workspace records are rejected. Availability is the percentage of successful observed probes, not a contractual SLA.
- Before a Stripe invoice webhook is received, map its invoice ID and currency to the correct workspace billing period in admin. Only a verified Stripe invoice for that workspace refreshes its snapshot. If the mapping was added late, run `sync_reporting_inputs PERIOD_ID --stripe-invoice INVOICE_ID` with the Stripe sandbox explicitly enabled. It checks the current provider customer against the workspace before importing. Keep Stripe's test-only gate until live billing is separately approved.

## Enable Resend only after authorization

1. Verify ownership of the sender domain or subdomain, register it in Resend, and configure DKIM/SPF and an appropriate DMARC policy. An unverified Gmail address cannot act as the custom sender. Domain control is pending. Configure a restricted sending key and a signed webhook destination at `/ops/reporting/delivery-webhook/` for delivered, bounced and complained events. Use a dedicated sending account or scoped destination to avoid callbacks from unrelated apps.
2. Verify recipient consent or routing with the customer. Use the provider's test-email addresses with a dedicated test configuration before production. Confirm exactly one email, one provider correlation ID, and delivery and bounce state changes. Disable unneeded provider tracking features.
3. After explicit owner approval, set `BARA_REPORTS_LIVE_EMAIL=true` and a verified sender match, and approve each non-sample configuration by ticking **Allow live**. Old mock messages stay simulated. Pause by removing per-configuration approval or disabling the global flag. Do not reuse a provider idempotency key past its safe retry window. [Resend idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys) · [Resend signatures](https://resend.com/docs/webhooks/verify-webhooks-requests)

## Recurring cost estimate

Local preview and mock fixture use add no hosted cost. For an illustrative low-volume pilot with one Scheduler trigger, jobs at 15-minute intervals, one vCPU and 0.5 GiB, a 60-second billed execution implies about 172,800 vCPU-seconds and 86,400 GiB-seconds per 30 days. Cloud Run job free allowances are based on US pricing, shared at billing-account level and affected by region and actual runtime. Scheduler has three free jobs per billing account and charges USD 0.10 per job per 31 days beyond that allowance. [Scheduler pricing](https://cloud.google.com/scheduler/pricing) · [Cloud Run pricing](https://cloud.google.com/run/pricing)

Use Supabase Free only. The PostgreSQL subscription cost is ¥0. Local/mock use incurs no hosted charges. A small hosted pilot can stay within free allowances, though Secret Manager, registry, network, observability and overages can add costs. Low-volume Resend may fit its free quotas. BigQuery may fit 10 GiB storage and 1 TiB query processing per month, depending on partition pruning and shared usage. [Resend pricing](https://resend.com/pricing) · [BigQuery pricing](https://cloud.google.com/bigquery/pricing) · [Supabase database pricing](https://supabase.com/kb/faqs/platform/database-only-cost)
