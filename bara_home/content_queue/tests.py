from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as utc_timezone
from threading import Barrier
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from operations.models import Workspace

from .models import AutomationPolicy, ContentDraft, Platform, PublicationJob, State
from .replenish import replenish
from .services import (
    MockPublisher, RetryablePublishError, TOKYO, approve_draft, change_job, claim_due, dispatch, enqueue,
    recover_interrupted, save_draft, set_channel,
)
from .views import tokyo_time


class QueueTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser("queue-owner")
        self.workspace = Workspace.objects.create(name="Queue test")
        self.wid = self.workspace.pk
        self.now = timezone.now()
        self.due = self.now + timedelta(hours=1)
        self.draft = self.make_draft("Plan the available booking windows in Tokyo.")

    def make_draft(self, text, platform=Platform.BLOG, approved=True):
        media = "bara/joey.jpg" if platform == Platform.INSTAGRAM else ""
        draft = save_draft(self.wid, platform, "Web development", text, media)
        if approved:
            approve_draft(self.wid, draft.pk, self.owner)
        return draft

    def job(self, draft=None, when=None, campaign=None):
        return enqueue(self.wid, (draft or self.draft).pk, when or self.due, self.owner, campaign)

    def change(self, job, action, **kwargs):
        return change_job(self.wid, job.pk, action, self.owner, **kwargs)

    def test_cancel_and_preserve_draft(self):
        job = self.job()
        self.change(job, "cancel")
        job.refresh_from_db()
        self.assertEqual(job.state, State.CANCELLED)
        self.assertEqual(job.history.latest("pk").actor, self.owner)
        self.assertTrue(ContentDraft.objects.filter(pk=self.draft.pk).exists())

    def test_replace_preserves_schedule_and_history_then_reschedule(self):
        job = self.job()
        replacement = self.make_draft("Document who owns each account before launch.")
        self.change(job, "replace", replacements={Platform.BLOG: replacement.pk})
        job.refresh_from_db()
        self.assertEqual(job.scheduled_at, self.due)
        self.assertEqual(job.draft_id, replacement.pk)
        self.assertEqual(job.history.earliest("pk").draft_id, self.draft.pk)
        rescheduled = self.due + timedelta(days=2)
        self.change(job, "reschedule", scheduled_at=rescheduled)
        job.refresh_from_db()
        self.assertEqual(job.scheduled_at, rescheduled)

    def test_campaign_replacement_is_atomic(self):
        blog = self.job()
        social = self.job(self.make_draft("The current social copy.", Platform.X), campaign=blog.campaign)
        blog_replacement = self.make_draft("Write the launch checklist before development starts.")
        social_replacement = self.make_draft("Choose the client’s core deliverable first.", Platform.X, approved=False)
        options = {Platform.BLOG: blog_replacement.pk, Platform.X: social_replacement.pk}
        with self.assertRaises(ValidationError):
            self.change(blog, "replace", replacements=options, entire_campaign=True)
        blog.refresh_from_db()
        self.assertEqual(blog.draft_id, self.draft.pk)
        approve_draft(self.wid, social_replacement.pk, self.owner)
        self.change(blog, "replace", replacements=options, entire_campaign=True)
        social.refresh_from_db()
        self.assertEqual(social.draft_id, social_replacement.pk)
        self.assertEqual(social.scheduled_at, self.due)

    def test_duplicate_slot_draft_and_near_duplicate_content(self):
        self.job()
        for draft, date in (
            (self.draft, self.due + timedelta(days=1)),
            (self.make_draft("A different topic using another draft for the same slot."), self.due),
            (self.make_draft("Plan the available booking windows in Tokyo!"), self.due + timedelta(days=1)),
        ):
            with self.assertRaises(ValidationError):
                self.job(draft, date)

    def test_replenishes_requested_replacement_and_skips_unapproved(self):
        job = self.job()
        self.change(job, "cancel_replace")
        self.make_draft("This note still needs to be approved.", approved=False)
        self.assertEqual(replenish(self.wid, self.now), 0)
        AutomationPolicy.objects.filter(workspace=self.workspace).update(enabled=True)
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        self.assertEqual(replenish(self.wid, self.now), 0)
        substitute = self.make_draft("Agree whether a reservation requires prepayment.")
        self.assertEqual(replenish(self.wid, self.now), 1)
        new_job = PublicationJob.objects.get(draft=substitute)
        self.assertEqual(new_job.scheduled_at, self.due)
        self.assertEqual(new_job.campaign, job.campaign)
        self.assertEqual(replenish(self.wid, self.now), 0)

    def test_replenishment_leaves_intentionally_cancelled_day_empty(self):
        planned_at = self.now + timedelta(days=1)
        job = self.job(when=planned_at)
        self.change(job, "cancel")
        self.make_draft("Agree on a useful monthly report before designing a dashboard.")
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        AutomationPolicy.objects.filter(workspace=self.workspace).update(enabled=True)
        replenish(self.wid, self.now)
        jobs_on_day = PublicationJob.objects.filter(
            workspace=self.workspace, scheduled_at__date=planned_at.astimezone(TOKYO).date(),
        ).exclude(state=State.CANCELLED)
        with timezone.override(TOKYO):
            self.assertFalse(jobs_on_day.exists())

    def test_generation_is_deduplicated_and_requires_approval(self):
        set_channel(self.wid, Platform.X, False, self.owner)
        AutomationPolicy.objects.filter(workspace=self.workspace).update(
            enabled=True, generation_enabled=True,
        )
        self.assertEqual(replenish(self.wid, self.now), 0)
        self.assertEqual(replenish(self.wid, self.now), 0)
        generated = ContentDraft.objects.get(workspace=self.workspace, platform=Platform.X)
        self.assertEqual(generated.state, State.NEEDS_APPROVAL)
        self.assertIsNone(generated.approved_by)

    def test_pause_before_dispatch_and_resume(self):
        job = self.job()
        self.assertIsNone(claim_due(self.wid, self.due))
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        claim = claim_due(self.wid, self.due)
        set_channel(self.wid, Platform.BLOG, True, self.owner)
        self.assertFalse(dispatch(self.wid, *claim, MockPublisher()))
        job.refresh_from_db()
        self.assertEqual(job.state, State.QUEUED)
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        self.assertTrue(dispatch(self.wid, *claim_due(self.wid, self.due), MockPublisher()))
        job.refresh_from_db()
        self.assertEqual(job.state, State.PUBLISHED)

    def test_owner_cancellation_after_claim_stops_dispatch(self):
        job = self.job()
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        claim = claim_due(self.wid, self.due)
        self.change(job, "cancel")
        publisher = Mock()
        self.assertFalse(dispatch(self.wid, *claim, publisher))
        publisher.publish.assert_not_called()

    def test_owner_replacement_invalidates_old_worker_claim(self):
        job = self.job()
        replacement = self.make_draft("Review required data before implementing the admin workflow.")
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        stale = claim_due(self.wid, self.due)
        self.change(job, "replace", replacements={Platform.BLOG: replacement.pk})
        current = claim_due(self.wid, self.due)
        self.assertFalse(dispatch(self.wid, *stale, MockPublisher()))
        self.assertTrue(dispatch(self.wid, *current, MockPublisher()))

    def test_cancel_during_and_after_request_is_rejected(self):
        job = self.job()
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        publisher = Mock()

        def publish(in_progress):
            with self.assertRaises(ValidationError):
                self.change(job, "cancel")
            return f"mock:{in_progress.pk}"

        publisher.publish.side_effect = publish
        self.assertTrue(dispatch(self.wid, *claim_due(self.wid, self.due), publisher))
        with self.assertRaises(ValidationError):
            self.change(job, "cancel")

    def test_retry_and_unknown_outcome(self):
        job = self.job()
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        publisher = Mock()
        publisher.publish.side_effect = [RetryablePublishError, TimeoutError]
        self.assertFalse(dispatch(self.wid, *claim_due(self.wid, self.due), publisher, self.due))
        self.assertIsNone(claim_due(self.wid, self.due))
        retry_at = self.due + timedelta(minutes=2)
        self.assertFalse(dispatch(self.wid, *claim_due(self.wid, retry_at), publisher, retry_at))
        job.refresh_from_db()
        self.assertEqual(job.state, State.FAILED)
        self.assertTrue(job.dispatch_started)
        self.assertEqual(job.attempts.count(), 2)
        self.assertIsNone(claim_due(self.wid, retry_at + timedelta(days=1)))

    def test_expired_pre_dispatch_claim_can_be_recovered(self):
        job = self.job()
        set_channel(self.wid, Platform.BLOG, False, self.owner)
        stale = claim_due(self.wid, self.due)
        recover_interrupted(self.wid, self.now + timedelta(hours=2))
        job.refresh_from_db()
        self.assertEqual(job.state, State.QUEUED)
        self.assertFalse(dispatch(self.wid, *stale, MockPublisher()))

    def test_tokyo_month_boundary_calendar_and_owner_media(self):
        when = tokyo_time("2100-02-01T00:30")
        self.assertEqual(when.astimezone(utc_timezone.utc), datetime(2100, 1, 31, 15, 30, tzinfo=utc_timezone.utc))
        instagram = self.make_draft("Booking design checklist for tours.", platform=Platform.INSTAGRAM)
        job = self.job(instagram, when)
        url = reverse("content_queue:calendar") + f"?workspace={self.wid}&job={job.pk}&mode=month&date=2100-02-01"
        media = reverse("content_queue:media", args=[self.wid, instagram.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.get(media).status_code, 302)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "2100-02-01 00:30")
        self.assertContains(response, "Booking design checklist for tours.")
        self.assertContains(response, "2100-02-01T00:30")
        self.assertEqual(self.client.get(media).content, bytes(instagram.media_bytes))
        revision = job.history.latest("pk")
        self.client.post(url, {"job": job.pk, "action": "cancel", "expected_revision": revision.pk})
        job.refresh_from_db()
        self.assertEqual(job.state, State.QUEUED)
        self.client.post(url, {"job": job.pk, "action": "cancel", "expected_revision": revision.pk, "confirm": "yes"})
        job.refresh_from_db()
        self.assertEqual(job.state, State.CANCELLED)

    def test_demo_seed_is_idempotent_and_has_14_tokyo_days(self):
        call_command("seed_content_calendar")
        call_command("seed_content_calendar")
        jobs = PublicationJob.objects.filter(workspace__name="Bara Content Calendar Demo")
        self.assertEqual(jobs.count(), 14)
        self.assertEqual(len({job.scheduled_at.astimezone(TOKYO).date() for job in jobs}), 14)


class ConcurrentClaimTests(TransactionTestCase):
    def test_two_postgres_workers_cannot_claim_same_job(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL row locking.")
        owner = get_user_model().objects.create_superuser("concurrent-owner")
        workspace = Workspace.objects.create(name="Concurrent test")
        draft = save_draft(workspace.pk, Platform.BLOG, "Test", "An original post.")
        approve_draft(workspace.pk, draft.pk, owner)
        now = timezone.now()
        enqueue(workspace.pk, draft.pk, now, owner)
        set_channel(workspace.pk, Platform.BLOG, False, owner)
        barrier = Barrier(2)

        def claim():
            close_old_connections()
            try:
                barrier.wait(5)
                return claim_due(workspace.pk, now)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
