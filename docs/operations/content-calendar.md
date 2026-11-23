# Content calendar and publication queue

Open **Bara Operations → Content calendar and publication queue**. Sign in with the existing Django owner account. Keep the Django service private. This feature runs outside the public GitHub Pages build.

## Run locally

From `bara_home` with the existing Django environment configured:

```powershell
python manage.py migrate
python manage.py seed_content_calendar
python manage.py run_content_queue WORKSPACE_ID
```

The seed command creates a separate **Bara Content Calendar Demo** with one future item per Tokyo calendar day for 14 days. The demo has all channels paused. The worker command fills empty slots if the workspace policy is enabled. Add `--mock-publish` to mark due jobs on resumed channels as simulated publications. For continuous local testing, schedule the same command from Windows Task Scheduler under the account and environment that already run Bara. A scheduled task only runs while its host is available.

## Operator workflow

- Inspect scheduled and completed posts by platform, category and status. Choose an item to preview the exact text and stored image. Images are snapshotted from approved local Bara assets when the draft is created and are served only to the owner.
- Approve a draft from the preview, then queue it at a Tokyo date and time. To link it to a campaign, select that campaign’s publication and choose **Add to selected publication’s campaign** when scheduling a draft for another channel.
- Replace one channel or an entire campaign. Existing validated drafts can be selected immediately. Editing creates a new draft; generating uses the existing Bara article/social preview data. Both require approval before they replace queued material. Replacement retains the original times and the complete revision record.
- Cancellation reserves the vacant day from normal replenishment. A replacement request uses the original channel, time and campaign. It remains pending if the policy is disabled, the channel is paused or no suitable approved draft is available.
- Optional replenishment fills at most one ordinary slot per open Tokyo calendar day at 10:00 and defaults to a 14-day horizon. It favors less-used categories, skips already-used drafts, and checks text similarity within a channel. Article-derived generation is deterministic and limited to existing Bara articles. It creates reviewable drafts and never approves them. Instagram generation needs a selected JPEG asset.

## Safety and live integration boundaries

Workspace transactions serialize owner actions and worker claims. The worker rechecks the current claim, approval and channel pause immediately before dispatch. From the point dispatch begins, the owner cannot cancel or overwrite the job. A superseded pre-dispatch claim cannot send the replacement. Each dispatch has an attempt record. Confirmed pre-publication failures can retry up to three total attempts. Unknown outcomes and interrupted in-flight attempts stop and require reconciliation.

The shipped adapter is mock-only for Blog, Instagram and X. It writes references starting with `mock:` and does not modify website articles or send network requests. A live integration needs its own authorized adapter, platform-specific media and text validation, a reconciliation strategy for uncertain responses, and a zero-cost execution environment. Blog rollout must integrate with the existing GitHub Pages build. Instagram needs a verified publishing token and compliant hosting for assets. X stays in mock or draft mode under the ¥0 requirement.

## Instagram authorization

Register `https://baradev-tokyo.github.io/oauth/instagram/callback/` in Meta. The public return page only relays the short-lived authorization code and state to the fixed local HTTPS callback. It excludes analytics, strips the query from the visible page URL and is omitted from the sitemap. The Django owner checks and code exchange stay local.

Start the local HTTPS listener with `python bara_home/manage.py run_instagram_oauth --cert CERT_PATH --key KEY_PATH`. Use a locally trusted certificate and supply the Instagram app ID and secret privately through `BARA_INSTAGRAM_APP_ID` and `BARA_INSTAGRAM_APP_SECRET`. In the same browser on that computer, open `https://127.0.0.1:8443/oauth/instagram/start/` and sign in to the private Bara admin. The current OAuth flow verifies the Instagram username and discards the test token. Live publishing and credential persistence are separate setup.
