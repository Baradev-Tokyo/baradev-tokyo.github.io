# ADR 0001 · Keep public publishing and private operations separate

Accepted for the foundation.

Keep GitHub Pages and the current hostname, render the same templates at build time, and extend the private Django monolith. Use owner-only controls and a Workspace foreign key on billing customers to create an ownership boundary now. Future organization isolation requires membership, scoped querysets and integration isolation before customer logins.

Use Stripe-hosted Checkout, local order IDs as references, and webhook reconciliation. Prices come from the owner-maintained billing order. Browser redirects are informational. Keep financial operations in test mode. Consider managed PostgreSQL and Cloud Run once authorized. No DNS flip, live billing products, external publishing, persistent cloud provisioning, or changes to customer service availability are approved in this iteration.
