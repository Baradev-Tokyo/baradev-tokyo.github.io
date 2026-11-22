# Cloud cost attribution and controls

Prefer client-owned projects and billing accounts. For shared accounts ingest Cloud Billing detailed export into BigQuery, using a scoped read-only identity and bounded date/bytes queries. Map project plus resource/service to a client and keep unmapped costs visible. Collect Cloud Run, database, storage, networking and logging costs. Do not infer a client from a display name alone. Preserve currency, credits, invoice month and corrections. Recompute recent days for delayed exports; keep a ledger of reconciliation runs.

Daily report: net costs after credits, unknown attribution, and budget threshold breaches. Monthly report: reconciled Stripe revenue net of refunds and fees, cloud costs, and margin per client and currency. Match on internal orders and invoice IDs, avoid combining currencies, and differentiate estimates from finalized invoices.

Cloud budgets notify and generally do not cap spend. Prefer max instances, scale-to-zero, query byte ceilings, retention and quotas. Prepaid hosting and explicit grace periods are contract decisions. An overdue invoice produces a review item. Any restriction needs an approved policy, notices, manual override, restoration plan and audit log. No automated deletion or suspension.

Sources: [Cloud Billing export](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery), [Google Cloud budgets](https://docs.cloud.google.com/docs/get-started/learn-about-billing).
