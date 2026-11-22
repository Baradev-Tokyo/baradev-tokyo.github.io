# Security

Public builds contain static assets, a public GA measurement ID and optional verification metadata. Keep environment files, inquiry data, agreement drafts, and access tokens out of Git. Deploy private Django independently with HTTPS, managed secrets, secure cookies, backup/restore checks, and an IAM gate for owner screens on top of Django permissions. Expose a narrow Stripe webhook route only when integration is enabled. Test keys and signing secrets stay in sandbox.

Owner-only checkout creation uses POST and Django CSRF. Verify Stripe signatures over raw bytes before accessing event data. Reject live events and isolate test customers. Use idempotency keys and atomic event receipts. Logs must omit payloads, contact data, and secrets. GA4 remains consent gated and excludes form contents and billing identifiers.

Future write actions require a scoped connection, explicit approval for external publication or money movement, bounded retry, and an audit record. No unattended destructive actions. Do not pass payment keys to AI tools or the optional worker.

Before deploying the private runtime, update Django to a supported patched release, run deployment checks, and test database lock and retry behavior against PostgreSQL. Keep these steps independent from GitHub Pages.
