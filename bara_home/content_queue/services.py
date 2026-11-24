import re
from contextlib import contextmanager
from datetime import timedelta
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import (
    AutomationPolicy, ChannelSettings, ContentDraft, Platform, PublicationJob,
    PublicationRevision, PublishingAttempt, QueueAudit, State,
)

TOKYO = ZoneInfo("Asia/Tokyo")
MAX_ATTEMPTS = 3


@contextmanager
def workspace_lock(workspace_id):
    AutomationPolicy.objects.get_or_create(workspace_id=workspace_id)
    with transaction.atomic():
        # A write first serializes workspace changes on PostgreSQL and SQLite.
        AutomationPolicy.objects.filter(workspace_id=workspace_id).update(revision=F("revision") + 1)
        yield AutomationPolicy.objects.get(workspace_id=workspace_id)


def validate_content(draft):
    if not draft.text.strip() or not draft.category.strip():
        raise ValidationError("Enter publication text and a category.")
    if draft.platform not in Platform.values:
        raise ValidationError("Choose a supported channel.")
    text = re.sub(r"https?://\S+", "x" * 23, draft.text) if draft.platform == Platform.X else draft.text
    limits = {Platform.X: 280, Platform.INSTAGRAM: 2200, Platform.YOUTUBE: 5000, Platform.TIKTOK: 2200}
    limit = limits.get(draft.platform, 20000)
    length = sum(2 if ord(char) > 0x10FF else 1 for char in text) if draft.platform == Platform.X else len(text)
    if length > limit:
        raise ValidationError(f"Publication text exceeds the {limit}-character limit.")
    if draft.media and not draft.media_bytes:
        raise ValidationError("This draft is missing its saved media. Create a replacement.")
    if draft.platform == Platform.INSTAGRAM and not bytes(draft.media_bytes).startswith(b"\xff\xd8\xff"):
        raise ValidationError("Instagram image drafts require a JPEG asset.")


def snapshot_media(media):
    if not media:
        return b""
    path = finders.find(media) if re.fullmatch(r"bara/[\w-]+\.(?:jpg|jpeg|png)", media, re.ASCII) else None
    if not path:
        raise ValidationError("Choose an existing Bara JPG or PNG asset.")
    with open(path, "rb") as image:
        data = image.read(8 * 1024 * 1024 + 1)
    signature = b"\x89PNG\r\n\x1a\n" if media.endswith(".png") else b"\xff\xd8\xff"
    if len(data) > 8 * 1024 * 1024 or not data.startswith(signature):
        raise ValidationError("Choose a valid image of at most 8 MiB.")
    return data


@transaction.atomic
def save_draft(workspace_id, platform, category, text, media="", *, actor=None):
    draft = ContentDraft(workspace_id=workspace_id, platform=platform, category=category,
                         text=text, media=media, media_bytes=snapshot_media(media), state=State.NEEDS_APPROVAL)
    draft.full_clean(exclude=["approved_by"])
    validate_content(draft)
    draft.save()
    QueueAudit.objects.create(workspace_id=workspace_id, actor=actor, action=f"Created draft {draft.pk}")
    return draft


def approve_draft(workspace_id, draft_id, actor):
    if not actor.is_superuser:
        raise ValidationError("Owner approval is required.")
    with workspace_lock(workspace_id):
        draft = ContentDraft.objects.get(workspace_id=workspace_id, pk=draft_id)
        validate_content(draft)
        draft.state = State.VALIDATED
        draft.approved_by = actor
        draft.save(update_fields=["state", "approved_by"])
        QueueAudit.objects.create(workspace_id=workspace_id, actor=actor, action=f"Approved draft {draft.pk}")


def record(job, action, actor=None):
    return PublicationRevision.objects.create(job=job, draft=job.draft, scheduled_at=job.scheduled_at,
                                              action=action, actor=actor)


def approved_draft(workspace_id, draft_id, platform=None):
    draft = ContentDraft.objects.get(workspace_id=workspace_id, pk=draft_id)
    if draft.state != State.VALIDATED or not draft.approved_by_id:
        raise ValidationError("Approve this draft before scheduling it.")
    if platform and draft.platform != platform:
        raise ValidationError("A replacement must match the publication channel.")
    validate_content(draft)
    return draft


def similar_content(first, second):
    candidate = " ".join(first.casefold().split())
    previous = " ".join(second.casefold().split())
    return candidate == previous or SequenceMatcher(None, candidate[:2000], previous[:2000]).ratio() >= 0.88


def ensure_available(draft, scheduled_at, exclude=None):
    jobs = PublicationJob.objects.filter(workspace_id=draft.workspace_id, platform=draft.platform).exclude(
        state=State.CANCELLED
    ).exclude(pk=exclude)
    if jobs.filter(scheduled_at=scheduled_at).exists():
        raise ValidationError("This channel already has a publication at that time.")
    if jobs.filter(draft=draft).exists():
        raise ValidationError("This draft is already scheduled or published.")
    for text in jobs.values_list("draft__text", flat=True):
        if similar_content(draft.text, text):
            raise ValidationError("Similar content is already scheduled or published on this channel.")


def _enqueue(draft, scheduled_at, actor=None, campaign=None):
    if timezone.is_naive(scheduled_at):
        raise ValidationError("The publication time needs a timezone.")
    ensure_available(draft, scheduled_at)
    if campaign and PublicationJob.objects.filter(
        workspace_id=draft.workspace_id, campaign=campaign, platform=draft.platform,
    ).exclude(state=State.CANCELLED).exists():
        raise ValidationError("This campaign already has a publication on that channel.")
    job = PublicationJob.objects.create(workspace_id=draft.workspace_id, draft=draft, platform=draft.platform,
                                        scheduled_at=scheduled_at, **({"campaign": campaign} if campaign else {}))
    record(job, "scheduled", actor)
    return job


def enqueue(workspace_id, draft_id, scheduled_at, actor, campaign=None):
    with workspace_lock(workspace_id):
        return _enqueue(approved_draft(workspace_id, draft_id), scheduled_at, actor, campaign)


def can_change(job):
    return not job.dispatch_started and job.state in {State.QUEUED, State.PUBLISHING, State.FAILED}


def change_job(workspace_id, job_id, action, actor, *, scheduled_at=None, replacements=None,
               entire_campaign=False, expected_revision=None):
    with workspace_lock(workspace_id):
        jobs = PublicationJob.objects.filter(workspace_id=workspace_id).select_related("draft")
        job = jobs.get(pk=job_id)
        if expected_revision is not None and job.history.filter(
            action__in=["scheduled", "replace", "reschedule", "cancel", "cancel_replace"],
        ).latest("pk").pk != expected_revision:
            raise ValidationError("This publication changed. Reload it before saving.")
        targets = list(jobs.filter(campaign=job.campaign).exclude(state=State.CANCELLED)) if entire_campaign else [job]
        if not targets or any(not can_change(item) for item in targets):
            raise ValidationError("This publication has already dispatched, finished, or been cancelled.")
        if action == "replace" and set(replacements or {}) != {item.platform for item in targets}:
            raise ValidationError("Select one approved replacement for every affected channel.")
        for item in targets:
            if action == "replace":
                draft = approved_draft(workspace_id, replacements[item.platform], item.platform)
                if draft.pk == item.draft_id:
                    raise ValidationError("Select a different draft.")
                ensure_available(draft, item.scheduled_at, item.pk)
                item.draft = draft
            elif action == "reschedule":
                if scheduled_at is None or timezone.is_naive(scheduled_at):
                    raise ValidationError("Enter a Tokyo publication date and time.")
                ensure_available(item.draft, scheduled_at, item.pk)
                item.scheduled_at = scheduled_at
            elif action not in {"cancel", "cancel_replace"}:
                raise ValidationError("Unknown publication action.")
            item.state = State.CANCELLED if action.startswith("cancel") else State.QUEUED
            item.replace_requested = action == "cancel_replace"
            item.retry_at = None
            item.last_error = ""
            item.save()
            record(item, action, actor)


def set_channel(workspace_id, platform, paused, actor):
    if platform not in Platform.values:
        raise ValidationError("Unknown channel.")
    if platform == Platform.LINKEDIN and not paused:
        raise ValidationError("LinkedIn is disabled at the owner's request.")
    with workspace_lock(workspace_id):
        ChannelSettings.objects.update_or_create(workspace_id=workspace_id, platform=platform,
                                                 defaults={"paused": paused})
        action = "Paused" if paused else "Resumed"
        QueueAudit.objects.create(workspace_id=workspace_id, actor=actor, action=f"{action} {platform}")


class RetryablePublishError(Exception):
    """Adapter confirms the request did not create a publication."""


class MockPublisher:
    def publish(self, job):
        return f"mock:{job.pk}"


def claim_due(workspace_id, now):
    with workspace_lock(workspace_id):
        enabled = ChannelSettings.objects.filter(workspace_id=workspace_id, paused=False).values("platform")
        job = PublicationJob.objects.filter(
            workspace_id=workspace_id, platform__in=enabled, state=State.QUEUED, scheduled_at__lte=now,
        ).filter(Q(retry_at__isnull=True) | Q(retry_at__lte=now)).order_by("scheduled_at", "pk").first()
        if job:
            job.state = State.PUBLISHING
            job.save(update_fields=["state"])
            claim = record(job, "claimed")
            return job.pk, claim.pk


def dispatch(workspace_id, job_id, claim_id, publisher, now=None):
    now = now or timezone.now()
    with workspace_lock(workspace_id):
        job = PublicationJob.objects.select_related("draft").get(pk=job_id, workspace_id=workspace_id)
        if (job.state != State.PUBLISHING or job.dispatch_started
                or not job.history.filter(pk=claim_id, action="claimed").exists()
                or job.history.filter(pk__gt=claim_id).exists()):
            return False
        active = ChannelSettings.objects.filter(workspace_id=workspace_id, platform=job.platform, paused=False)
        if not active.exists():
            job.state = State.QUEUED
            job.save(update_fields=["state"])
            record(job, "channel_paused")
            return False
        try:
            approved_draft(workspace_id, job.draft_id, job.platform)
        except ValidationError:
            job.state, job.last_error = State.FAILED, "The selected draft no longer passes approval or validation."
            job.save(update_fields=["state", "last_error"])
            record(job, "validation_failed")
            return False
        job.dispatch_started = True
        job.save(update_fields=["dispatch_started"])
        attempt = PublishingAttempt.objects.create(job=job)
        record(job, "dispatch_started")

    reference, error, safe_retry = "", "", False
    try:
        reference = publisher.publish(job)
        if not isinstance(reference, str) or not reference or len(reference) > 150:
            raise ValueError("Publisher did not confirm a valid reference.")
    except RetryablePublishError:
        error, safe_retry = "Temporary failure before publication.", True
    except Exception:
        error = "Publication outcome is unknown. Review the channel before taking action."

    with workspace_lock(workspace_id):
        job.refresh_from_db()
        count = job.attempts.count()
        job.last_error = error
        if error:
            job.state = State.QUEUED if safe_retry and count < MAX_ATTEMPTS else State.FAILED
            job.retry_at = now + timedelta(minutes=2 ** count) if job.state == State.QUEUED else None
            job.dispatch_started = not safe_retry
        else:
            job.state, job.external_reference, job.retry_at = State.PUBLISHED, reference, None
        job.save()
        attempt.outcome = "published" if not error else ("safe_failure" if safe_retry else "unknown")
        attempt.finished_at = timezone.now()
        attempt.save(update_fields=["outcome", "finished_at"])
        record(job, f"dispatch_{attempt.outcome}")
        return not error


def recover_interrupted(workspace_id, now):
    with workspace_lock(workspace_id):
        jobs = PublicationJob.objects.filter(workspace_id=workspace_id, state=State.PUBLISHING)
        for job in jobs:
            last = job.history.order_by("-pk").first()
            if last is None or last.created_at > now - timedelta(minutes=30):
                continue
            if job.dispatch_started:
                job.state = State.FAILED
                job.last_error = "The worker stopped after dispatch. Check the external outcome before taking action."
                job.attempts.filter(finished_at__isnull=True).update(outcome="unknown", finished_at=now)
            else:
                job.state = State.QUEUED
            job.save(update_fields=["state", "last_error"])
            record(job, "recovered_interruption")
