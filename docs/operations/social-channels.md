# Bara social profiles and connections

Use **Bara Development** as the display name and `https://baradev-tokyo.github.io/` in each platform’s website or links field. These bios are approved-ready drafts. Update the profiles in the platform’s signed-in editor.

| Platform | Bio |
| --- | --- |
| X | Tokyo-based Python & Django development. Booking, Stripe payments and workflow automation for small businesses. 日本語 / EN |
| Instagram | 東京のWeb開発。予約・決済・業務自動化を小さなチーム向けに。Python / Django · 日本語 / EN |
| Facebook | 東京を拠点に、小規模事業者向けのWebサイト、予約・Stripe決済、業務自動化を開発しています。日本語・英語でご相談いただけます。 |
| TikTok | 東京のWeb開発｜予約・決済・業務自動化を短い動画で |
| YouTube | Bara Development is a Tokyo-based freelance software development business. We share practical guides on websites, booking systems, Stripe payments and workflow automation for small teams. Web制作・予約・決済・業務自動化のヒントを日本語と英語でお届けします。 |

## Connection checklist

From the repository root on Windows, run these commands in your own PowerShell:

```powershell
& .\scripts\check-meta-connection.ps1 -Channel instagram -Save
& .\scripts\check-meta-connection.ps1 -Channel facebook -Save
```

Paste each token only into its hidden prompt. After verifying the expected account, the script stores the token encrypted with Windows DPAPI in `%LOCALAPPDATA%\Bara\Credentials`. It can be reopened by the same Windows user on the same machine. Run the command again without `-Save` to recheck an existing credential. These credentials are for the local backend and stay out of the GitHub repository and Pages deployment.

- **Instagram**. Use the existing Business account and Instagram Login token. Run `python manage.py check_social_connection instagram` from `bara_home`. Set `BARA_INSTAGRAM_ACCESS_TOKEN` in the private process environment from the existing secret store. The command checks ownership and prints no credentials.
- **Facebook**. The Bara Page ID is configured. Obtain a separate Page token from an account with the appropriate Page tasks and permissions. Check with `python manage.py check_social_connection facebook` and `BARA_FACEBOOK_PAGE_ACCESS_TOKEN`. [Publishing requirements](https://developers.facebook.com/docs/graph-api/reference/page/feed/)
- **YouTube**. The Bara channel ID is configured. Authorize an OAuth client in a Google project with YouTube Data API access. Check with `python manage.py check_social_connection youtube` and `BARA_YOUTUBE_ACCESS_TOKEN`. A video uploader, media workflow and explicit publication settings are still needed. [YouTube API quotas](https://developers.google.com/youtube/data/guides/quota_and_compliance_audits)
- **TikTok**. If an approved app with Login Kit and basic user-info scope is available, check with `python manage.py check_social_connection tiktok --expected-id OPEN_ID` and `BARA_TIKTOK_ACCESS_TOKEN`. The queue can prepare captions and the blog preview command also returns a video script. The current owner-only queue is ineligible for Direct Post under TikTok's intended-use rules. Publish manually. [TikTok content-sharing guidelines](https://developers.tiktok.com/docs/en/content-sharing-guidelines)
- **X**. Resume X in Bara, review a scheduled draft and choose **Open draft in X composer**. A person finishes posting on X. Leave API calls disabled under the ¥0 policy. [X API pricing](https://docs.x.com/x-api/getting-started/pricing)
- **LinkedIn**. Paused. No account or verification action is needed.

Never put credentials in this document, chat, or Git. The identity checks make one read-only request. They do not establish automatic renewal or posting permissions. The recurring calendar worker still uses the mock publisher.

## Publish one approved Meta post

In the **Bara Development** calendar, approve the exact text and asset, queue the draft, and resume its channel. Facebook currently supports text with URLs in the message. Instagram requires an approved JPEG already served by the Bara site at its static asset URL. The publisher checks the live image bytes against the saved draft snapshot.

When the post is due, copy its publication ID and draft ID from the preview. Run this from the repository root, substituting the channel and both IDs. This command sends the post live:

```powershell
& .\scripts\check-meta-connection.ps1 -Channel facebook -PublicationId 'PUBLICATION_UUID' -ConfirmDraft 123
```

The command verifies account identity, claims just that one approved job and records Meta's returned reference. If the outcome of a final request is uncertain, check the public channel before taking any action. The queue will not resend an ambiguous request automatically.
