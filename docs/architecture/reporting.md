# Multi-customer reports and transactional delivery

## Boundaries and relationships

Reporting is a private Django app. The existing operations Workspace is the organization root; it is shared with Stripe billing, so no second customer directory is needed. Contacts, configurations, ownership and billing periods reference a workspace. A verified recipient belongs to exactly one contact. Runs belong to one configuration, artifacts and deliveries belong to one run, and delivery events belong to one outbound message. Usage is linked through an effective-dated ownership record and a billing period. Payment snapshots link through an explicitly assigned billing period. Audit rows use a workspace and safe correlation identifiers. Before a report or email is generated, the service validates relationships that cross these paths. Django admin is owner-only for these models and no customer-facing URLs are added.

One Cloud Scheduler trigger invokes a Cloud Run Job via OAuth. It runs the Django management command on PostgreSQL, independently of the owner's laptop. Each configuration uses a local calendar in its timezone (Asia/Tokyo by default); weekly periods start Monday and monthly periods start on the first. Periods are half-open and closed before generating. A per-configuration lag allows exports time to settle. Recovery repeats the same run ID for the same period. Use a bounded owner replay for older missed periods.

Use Supabase Free for the reporting database. The Cloud Run Job can check PostgreSQL and, with owner opt-in, resume a confirmed paused project via the Management API before processing work. The management identity runs outside the database. Keep dashboard access and encrypted logical backups for recovery cases beyond an ordinary pause.

The database is the job ledger and outbound queue. A conditional claim with a lease and token serializes workers. A result is committed only by the current claim holder. Failures retry with bounded exponential backoff and terminal failures are surfaced in admin and structured logs for Cloud Logging alerting. Outbound requests use stable provider idempotency keys and identical content on retry. Do not retry at the provider after the key window has expired. Review ambiguous submissions manually. Delivery, bounce and complaint are asynchronous and do not trigger an automatic resend. Mock delivery has its own terminal status.

## Data, security and retention

Cloud Billing detailed-export rows enter an owner-approved BigQuery view, with effective project/resource ownership and a bounded partition query. Cloud Monitoring enters through read-only scoped aggregates. Incomplete imports must be flagged; reports separate finalized actual costs, estimates, billable charges, taxes, credits, discounts, Stripe invoices, collections and remaining balances. An estimate never generates an invoice. Payments reconcile through verified Stripe events and an explicit invoice-to-period mapping. Unowned or ambiguous resources are excluded from ingestion and their exceptions go to owner review. Shared-resource allocations need an approved allocation rule before import.

Reports use scoped snapshots and escaped bilingual HTML/plain-text rendering. Artifacts are kept in PostgreSQL initially; access is private, with encrypted managed disks/backups in production. A future GCS artifact adapter would use a private bucket, public-access prevention, scoped service identity and short-lived signed URLs issued only after authorization. No public report downloads are enabled. Default retention is 90 days for rendered reports and email bodies, with message metadata and audit records retained for operational review. Confirm retention and backup deletion windows before deployment.

Recipient verification is a documented owner check of mailbox control or customer-authorized routing. The owner records the verified address. An edit or revocation invalidates the match. Delivery rechecks the exact address, active status and organization. No user or provider sends live email until explicitly approved. Sender domain and credentials remain server-side.

## Initial scope

Hosting usage and charges use mock data or explicitly recorded usage and payment snapshots. Other report categories have configurable templates and a named extension point; no integration fabricates live metrics. Preview generates local samples. Production setup, IAM, cost estimates, and approvals are in the reporting runbook.
