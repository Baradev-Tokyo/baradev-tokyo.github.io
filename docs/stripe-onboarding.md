# Stripe Japan onboarding and sandbox

## Owner checklist

- Open the Stripe Dashboard with baradev.tokyo@gmail.com. Select Japan and Individual / Sole proprietor (個人事業主) as applicable. Use your actual personal legal name, with Bara Development as the trade name where requested. Do not enter a corporate registration number.
- Owner completes identity, legal acceptance, phone, address, business details, and Japanese payout account verification directly in Stripe. Enable MFA and verify access. No sensitive details belong in this repo.
- Owner reviews the service descriptions and actual prices, legal disclosures, contact details, refund/cancellation policy, billing name, and statement descriptor before requesting activation. Review the [legal drafts](legal-drafts.md).
- Official sources: [Stripe Japan onboarding](https://support.stripe.com/questions/getting-started-with-stripe-a-guide-for-users-in-japan?locale=ja-JP), [Stripe webhooks](https://docs.stripe.com/webhooks), [checkout testing](https://docs.stripe.com/testing).

## Sandbox smoke test

1. In a Stripe sandbox, create a fictitious test customer and test prices for one-time and recurring JPY charges. The owner sets the private environment variables documented in .env.example, enabling the sandbox only. Set the webhook secret printed by the Stripe CLI.
2. Run Django migrations locally and create an owner superuser. From Django admin add a Workspace, Billing customer (cus_… from the sandbox), and Billing order with the matching price_… and order kind. One-time service, deposit, and milestone use payment mode. Maintenance and SaaS use subscription mode.
3. Run Django locally, then run `stripe listen --forward-to http://127.0.0.1:8000/ops/billing/webhook/`. In the order admin page click Open Stripe test Checkout. Use a Stripe test card, then verify order status and the linked invoice/subscription in admin. Repeat with a failed payment and close a separate session to check cancellation. The browser return page never marks an order paid.
4. Confirm duplicate delivery leaves a single receipt and fresh state. A sandbox network error can be retried with the same order within 23 hours. After that, inspect the Stripe Dashboard before creating a replacement order. The integration uses snapshot event destinations and a pinned API version.
5. For sandbox-only APIs, use constrained Stripe test credentials where possible, granting Checkout Sessions write and the required object read access. Never paste keys into chat or commit them.

The automated suite signs sandbox event fixtures and mocks Stripe HTTP calls. Real Stripe sandbox network delivery remains an owner-authorized acceptance test. The published portfolio contains no payment endpoints. Production routing, refund processing, invoice creation, and activation require a separate approval and integration review.
