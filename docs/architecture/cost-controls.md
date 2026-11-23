# Cloud cost attribution and controls

## v0.5 zero-additional-cost gate

No paid plans, Connects, promotion, API calls or infrastructure are authorized. Existing subscriptions confer no additional spending authority. Keep optional integrations off and use local/mock fallbacks when a hard zero-cost guarantee cannot be verified. Recheck quota and account settings before activation.

| Dependency | Japan availability and billing | Quota, overage and stop control | Fallback |
| --- | --- | --- | --- |
| Existing GitHub Pages and Actions | Already accessible in Japan; public repo, standard runners | Pages limits apply; standard runners for public repositories are included. Keep only existing public CI and stop by disabling a workflow. No additional paid runners or storage. [Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage) | Local static export |
| Cloud Run, Scheduler, BigQuery | Japan regions available; billed production project needed | Allowances are shared and metered; region, quotas and overage rates vary. Budget alerts do not cap costs. Keep deploy and exports off. [Cloud Run pricing](https://cloud.google.com/run/pricing) · [BigQuery pricing](https://cloud.google.com/bigquery/pricing) | Local commands and fixture data |
| Supabase Free | Existing Free-only preference; confirm region and free account before connection | Free quota and pause rules apply. No upgrade or new paid database. Leave provisioning and auto-resume disabled here. [Free pausing](https://supabase.com/docs/guides/platform/free-project-pausing) | SQLite for development; local PostgreSQL for realistic testing |
| Resend | Account/domain eligibility and region processing must be confirmed | Published free tier 3,000 monthly and 100 daily at verification; no guaranteed approved production billing configuration. Live delivery off. [Resend pricing](https://resend.com/pricing) | Mock email or local catcher |
| GA4 and Search Console | Existing owner account; standard browser tools | No paid export or connector. Property access and GA consent gate can be revoked. [Search Console](https://search.google.com/search-console/) | Existing public site works without analytics |
| Calendar appointment page | Existing public Google booking schedule | Personal account supports one booking page; no API billing. Remove embed configuration or unpublish at Google if needed. [Google Calendar schedules](https://support.google.com/calendar/answer/11608416) | Existing package email inquiry |
| Upwork and Fiverr | Existing accounts. Verify owner tax/payout and feature eligibility | No spending, purchases, subscriptions, Connects use or promotions. Revenue fees are recorded separately. Disconnect OAuth or use offline intake. [Marketplace matrix](../compliance/platform-policy-matrix.md) | Local files and manual UI |
| OpenAI, X, Instagram, LINE, Business Profile | Paid/approval exposure or account-specific limits not verified | Provider writes off. API budgets and plan availability are not assumed; do not connect until verified. [Marketplace matrix](../compliance/platform-policy-matrix.md) | Local rules, captions, previews and manual review |
| Local tools and hardware | Existing Python and laptop | No extra software or model subscription. Power and wear still apply. Stop local workers or leave them unscheduled. No public ports. | Manual workflow |

Prefer client-owned projects and billing accounts. For shared accounts ingest Cloud Billing detailed export into BigQuery, using a scoped read-only identity and bounded date/bytes queries. Map project plus resource/service to a client and keep unmapped costs visible. Collect Cloud Run, database, storage, networking and logging costs. Do not infer a client from a display name alone. Preserve currency, credits, invoice month and corrections. Recompute recent days for delayed exports; keep a ledger of reconciliation runs.

Daily report: net costs after credits, unknown attribution, and budget threshold breaches. Monthly report: reconciled Stripe revenue net of refunds and fees, cloud costs, and margin per client and currency. Match on internal orders and invoice IDs, avoid combining currencies, and differentiate estimates from finalized invoices.

Cloud budgets notify and generally do not cap spend. Prefer max instances, scale-to-zero, query byte ceilings, retention and quotas. Prepaid hosting and explicit grace periods are contract decisions. An overdue invoice produces a review item. Any restriction needs an approved policy, notices, manual override, restoration plan and audit log. No automated deletion or suspension.

Sources: [Cloud Billing export](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery), [Google Cloud budgets](https://docs.cloud.google.com/docs/get-started/learn-about-billing).
