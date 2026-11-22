# System overview

- Public surface: GitHub Pages serves bilingual information, consent-gated GA4, email links, and case studies. It stays independent from private hosting availability. Review GitHub Pages' commercial limits before expanding the site beyond a portfolio.
- Private surface: an owner-operated Django monolith. Existing inquiries, proposals and contracts stay in services; billing and orchestration belong in operations. PostgreSQL is the planned production store. Supabase and Cloud Run are candidates pending region, backup, IAM and budget decisions. Production settings and hosting are deliberately deferred.
- Stripe handles card entry and payment processing. Opt-in test routes are mounted only in the private app. Stripe events are authoritative for payment state.
- Reporting and marketing use provider adapters. A future durable job runner processes approved jobs and reports back. No provider publishing is enabled.
- Optional worker runs CPU batch jobs on the Lenovo. It pulls low-priority jobs outbound over private authentication. Use Docker resource limits, bounded scratch space and timeouts. Start with FFmpeg and small CPU-friendly models; benchmark Ryzen 3 2200U throughput before promising turnaround. Treat worker input as untrusted and keep customer data off experimental jobs. Billing, access and payments run independently of the laptop.
