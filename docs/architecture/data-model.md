# Data model

- Existing ProjectRequest and AgreementTemplate retain existing behavior and are outside customer-facing tenancy.
- Workspace groups billing customers. BillingCustomer carries the Stripe customer ID. BillingOrder links to a customer and a Stripe test Price, distinguishes one-time, deposit, milestone, maintenance, or future SaaS billing, and stores Checkout and settlement state.
- StripeEvent records a unique event ID and type only, supporting atomic webhook deduplication. Subscription and Invoice mirror provider state. Billing orders retain confirmed Checkout, payment intent, invoice and subscription identifiers for reconciliation. Renewal invoices are linked to the subscription. Invoice state is separate from payment-link clicks.
- Planned: extend membership and client/project links before enabling customer accounts. Define agreements and approved grace-period policies per project. Keep resource mappings effective dated. Daily costs and monthly summaries are derived from versioned imports.
- Future integration entities: provider connection (secret reference), scheduled job (workspace, approval, budget, state, attempt), and append-only audit event (actor, action, target, outcome). Introduce these when the first write integration is approved.
