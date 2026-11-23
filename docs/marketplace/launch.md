# Bara marketplace and social launch

## Private job review

Open the local Django operations dashboard at `/admin/bara-operations/` and select a workspace. Open a job to read its description, see the screening result, and approve it for drafting. Optional scope notes personalize the starter draft. The approval is stored once and has no submission or Connects action.

An authorized Upwork client can pass normalized results as a local JSON array to `python manage.py import_upwork_batch WORKSPACE_ID jobs.json` from `bara_home`. Each job requires `external_id` and `title`. Include `description`, `url`, `skills` and known budget and Connects values where available. Keep unknown values absent and keep marketplace data outside Git. The importer does not schedule searches. OAuth and a verified discovery runner in a supported client are required before enabling recurring search.

## Profile copy for owner review

- Upwork headline: Django Developer | Booking Systems, Stripe & Automation
- Upwork overview: I build websites and web applications for small teams. I focus on Django, online booking, Stripe payments, and tools that reduce repetitive work. For Pedal Somewhere, I built a booking flow for guided cycling tours in Tokyo with Stripe payments and automated emails. I can help define the first deliverable and agree on milestones before implementation.
- Fiverr profile: I’m Joey, a Tokyo-based developer specializing in Python, Django, booking workflows, Stripe integrations, and automation for small businesses. Tell me what you need and what you already use so we can agree on a scope before work starts.
- Lead Fiverr Gig: use the landing-page draft in `dist-marketplace/fiverr.json` and `landing.png`. Confirm price, delivery, and revisions before publishing.

## Organic social drafts

From `bara_home`, run `python manage.py preview_social_posts planning-an-online-booking-flow --language ja` (or `en`). Review the generated copy and verify that the article URL is live. Use the Instagram URL in the profile link and the X URL in the post. Choose an approved image for Instagram. Once manually published, record each permalink in the article’s `social_links` in `blog/posts.py`.

Live scheduling and publishing require public Bara accounts and a verified authorized platform integration. The preview command needs no platform credentials and incurs no API usage.

The site footer and draft generator share the profiles in `blog/social.py`. Run `python manage.py preview_social_posts --language ja` (or `en`) to generate drafts for all articles. The output includes the destination profile and tracked article URL for each channel.
