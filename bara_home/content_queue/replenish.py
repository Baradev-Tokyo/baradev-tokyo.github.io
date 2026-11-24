from collections import Counter
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import override

from blog.posts import POSTS, localized_post
from blog.social import SOCIAL_CHANNELS, preview_social_post

from .models import ChannelSettings, ContentDraft, Platform, PublicationJob, State
from .services import TOKYO, _enqueue, record, save_draft, similar_content, workspace_lock


def article_content(slug, platform):
    with override("ja"):
        if platform == Platform.BLOG:
            article = localized_post(slug)
            return "\n\n".join((article["title"], *article["paragraphs"]))
        preview = preview_social_post(slug)[platform]
        text = preview["caption"]
        if platform == Platform.INSTAGRAM:
            text += "\n\n" + preview["link"]
        return text


def generate_article_draft(workspace_id, platform, slug, media="", actor=None):
    if slug not in POSTS or (platform != Platform.BLOG and platform not in SOCIAL_CHANNELS):
        raise ValidationError("Choose an existing Bara article and supported channel.")
    text = article_content(slug, platform)
    existing = ContentDraft.objects.filter(workspace_id=workspace_id, platform=platform, text=text, media=media).first()
    return existing or save_draft(workspace_id, platform, "Bara articles", text, media, actor=actor)


def _fill(policy, channels, scheduled_at, counts, cancelled=None):
    drafts = ContentDraft.objects.filter(workspace_id=policy.workspace_id, platform__in=channels,
                                         state=State.VALIDATED, approved_by__isnull=False).exclude(
        publicationrevision__isnull=False,
    )
    ordered = sorted(drafts, key=lambda draft: (counts[draft.category], draft.pk))
    for draft in ordered:
        if cancelled and similar_content(draft.text, cancelled.draft.text):
            continue
        if PublicationJob.objects.filter(workspace_id=policy.workspace_id, platform=draft.platform,
                scheduled_at=scheduled_at, state=State.CANCELLED, history__action="cancel").exists():
            continue
        try:
            with transaction.atomic():
                job = _enqueue(draft, scheduled_at, campaign=cancelled.campaign if cancelled else None)
        except ValidationError:
            continue
        counts[draft.category] += 1
        return job
    if policy.generation_enabled:
        for channel in channels:
            if channel in {Platform.BLOG, Platform.FACEBOOK, Platform.X}:
                for slug in POSTS:
                    try:
                        generate_article_draft(policy.workspace_id, channel, slug)
                    except ValidationError:
                        continue


def replenish(workspace_id, now=None):
    now = now or timezone.now()
    with workspace_lock(workspace_id) as policy:
        if not policy.enabled:
            return 0
        jobs = PublicationJob.objects.filter(workspace_id=workspace_id)
        channels = list(ChannelSettings.objects.filter(workspace_id=workspace_id, paused=False)
                        .values_list("platform", flat=True))
        counts = Counter(jobs.exclude(state=State.CANCELLED).values_list("draft__category", flat=True))
        filled = 0
        for cancelled in jobs.select_related("draft").filter(
            state=State.CANCELLED, replace_requested=True, scheduled_at__gt=now,
        ):
            if cancelled.platform not in channels:
                continue
            if _fill(policy, [cancelled.platform], cancelled.scheduled_at, counts, cancelled):
                cancelled.replace_requested = False
                cancelled.save(update_fields=["replace_requested"])
                record(cancelled, "replacement_scheduled")
                filled += 1
        today = now.astimezone(TOKYO).date()
        last = today + timedelta(days=policy.horizon_days)
        start_at = datetime.combine(today, time.min, TOKYO)
        end_at = datetime.combine(last, time.min, TOKYO)
        occupied = {
            item.astimezone(TOKYO).date()
            for item in jobs.filter(scheduled_at__gte=start_at, scheduled_at__lt=end_at)
            .values_list("scheduled_at", flat=True)
        }
        while today < last and channels:
            scheduled_at = datetime.combine(today, time(10), TOKYO)
            if scheduled_at > now and today not in occupied and _fill(policy, channels, scheduled_at, counts):
                filled += 1
            today += timedelta(days=1)
        return filled
