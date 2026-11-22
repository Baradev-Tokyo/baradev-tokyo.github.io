# Integrations and owner setup

| Integration | Owner action and initial scope |
| --- | --- |
| GA4 | Create/retain the Bara Web stream and confirm account/property access. Set Actions variable BARA_GA_MEASUREMENT_ID. Keep enhanced measurement disabled and check Realtime with consent. Register site_language and package_slug as event dimensions. For reports via Data API, grant a dedicated identity Viewer access to the numeric GA4 property. |
| Search Console | Add and verify the existing HTTPS URL-prefix property. Set BARA_GOOGLE_SITE_VERIFICATION to the HTML tag content, redeploy and submit sitemap.xml. Grant read access for API reporting only when needed. |
| Cloud Monitoring | After private Cloud Run approval, use [Cloud Run metrics](https://docs.cloud.google.com/run/docs/monitoring), an uptime check for the health endpoint, alerts for 5xx/latency, and an owner notification channel. Use Monitoring Viewer for reads. Check webhook failure/retry separately from public uptime. An IAM-gated probe needs an authorized check rather than anonymous access. |
| X | Owner connects a developer project and approves account scopes and access plan. Keep publishing disabled until permission and costs are verified. |
| Instagram | Owner provides an eligible professional account and Meta app. Verify current permissions and App Review for chosen login flow before publishing. |
| LINE | Owner creates/links a LINE Official Account and Messaging API channel. Validate message quotas and webhook signatures. |
| Business Profile | Owner verifies the business and account access. Confirm profile eligibility, then request API access as needed. Reviews are read-only until an owner approves responses. |
| Stripe | See [sandbox and onboarding guide](../stripe-onboarding.md). |

Proposal analytics vocabulary: service_selected = package choice; consultation_requested = an actual booked/requested consultation, not a click; contact_form_submitted = persisted valid inquiry; checkout_started = first successful hosted session creation; payment_completed = first confirmed settlement. The public site measures service choices, portfolio clicks, and email intent only. Do not emit speculative conversion events. Future server analytics needs explicit consent provenance and a transactional outbox with stable event keys. Never send customer names, inbox contents or provider billing IDs. GA IDs used in public HTML are not authentication keys.

For existing reports, map service_selected to the current public package_click event. Continue emitting one event per click to preserve historical reporting. The owner can mark email_click as a key event for inquiry intent only. Keep actual inquiry and payment counts as private operational reports until a consent-aware bridge is approved.
