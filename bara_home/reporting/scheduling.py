import logging
import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .email_delivery import DeliveryError, get_provider
from .models import AuditEvent, JobStatus, ReportArtifact, ReportConfiguration, ReportDelivery, ReportRun
from .reports import ReportError, render_pdf, render_report

logger = logging.getLogger(__name__)
LEASE = timedelta(minutes=15)
ATTEMPTS = 5
RETENTION = timedelta(days=90)


def closed_period(now, zone, frequency, delay_days):
    if timezone.is_naive(now):
        raise ValueError("Expected aware scheduler time.")
    local = now.astimezone(ZoneInfo(zone)).date() - timedelta(days=delay_days)
    if frequency == "weekly":
        end = local - timedelta(days=local.weekday())
        return end - timedelta(days=7), end
    if frequency == "monthly":
        end = local.replace(day=1)
        return (end - timedelta(days=1)).replace(day=1), end
    raise ValueError("Unknown report frequency.")


def enqueue(schedule_time):
    created_count = 0
    for cfg in ReportConfiguration.objects.filter(active=True).iterator():
        try:
            start, end = closed_period(schedule_time, cfg.timezone, cfg.frequency, cfg.delay_days)
        except (ValueError, ZoneInfoNotFoundError):
            logger.error("bara_reporting_terminal configuration=%s code=invalid_schedule", cfg.pk)
            continue
        if start < cfg.starts_on:
            continue
        _, created = ReportRun.objects.get_or_create(
            configuration=cfg, period_start=start, period_end=end,
            defaults={"organization_id": cfg.organization_id},
        )
        created_count += created
    return created_count


def eligible(now):
    return Q(status__in=(JobStatus.QUEUED, JobStatus.RETRY), next_attempt__lte=now) | Q(
        status=JobStatus.WORKING, lease_until__lte=now
    )


def claim_next(model, now):
    candidate = model.objects.filter(eligible(now)).order_by("next_attempt", "pk").values_list("pk", flat=True).first()
    if candidate is None:
        return None
    token = uuid.uuid4()
    if not model.objects.filter(pk=candidate).filter(eligible(now)).update(
        status=JobStatus.WORKING, claim=token, lease_until=now + LEASE, attempts=F("attempts") + 1,
    ):
        return None
    return model.objects.get(pk=candidate, claim=token)


def recipient_valid(recipient, organization_id, address, now):
    contact = recipient.contact
    return (
        contact.organization_id == organization_id and contact.active
        and recipient.revoked_at is None and recipient.verified_at <= now
        and recipient.address == contact.email == address
    )


def audit(job, kind):
    if isinstance(job, ReportRun):
        organization_id, correlation = job.organization_id, str(job.pk)
    else:
        organization_id, correlation = job.run.organization_id, str(job.message_id)
    AuditEvent.objects.create(organization_id=organization_id, kind=kind, correlation=correlation)


def complete(job, status, **fields):
    updated = type(job).objects.filter(pk=job.pk, claim=job.claim).update(
        status=status, claim=None, lease_until=None, error_code="", **fields
    )
    if updated:
        audit(job, f"{job._meta.model_name}.{status}")


@transaction.atomic
def fail(job, code, retryable):
    retry = retryable and job.attempts < ATTEMPTS
    delay = timedelta(minutes=2 ** job.attempts)
    updated = type(job).objects.filter(pk=job.pk, claim=job.claim).update(
        status=JobStatus.RETRY if retry else JobStatus.FAILED,
        claim=None, lease_until=None, next_attempt=timezone.now() + delay, error_code=code,
    )
    if not updated:
        return
    audit(job, f"{job._meta.model_name}.{'retry' if retry else 'failed'}")
    if not retry:
        logger.error("bara_reporting_terminal model=%s job=%s code=%s", job._meta.model_name, job.pk, code)


def generate(run):
    cfg = run.configuration
    if cfg.organization_id != run.organization_id or not cfg.active:
        raise ReportError("configuration_inactive_or_mismatched")
    now = timezone.now()
    recipients = list(cfg.recipients.select_related("contact").order_by("pk"))
    if any(not recipient_valid(item, run.organization_id, item.address, now) for item in recipients):
        raise ReportError("recipient_invalid_or_mismatched")
    if not recipients and not cfg.sample:
        raise ReportError("no_verified_recipients")
    report = render_report(run)
    artifacts = [("text/html", report.html.encode("utf-8"))]
    if cfg.include_pdf:
        try:
            artifacts.append(("application/pdf", render_pdf(report)))
        except ImportError as exc:
            raise ReportError("pdf_dependency_unavailable") from exc
    # A recovered job cannot overwrite artifacts or create a second message.
    with transaction.atomic():
        owner = ReportRun.objects.select_for_update().filter(
            pk=run.pk, claim=run.claim, status=JobStatus.WORKING
        ).first()
        if not owner:
            return
        expires = now + RETENTION
        for media_type, data in artifacts:
            ReportArtifact.objects.create(run=owner, media_type=media_type, data=data, expires_at=expires)
        addresses = set()
        for item in recipients:
            if item.address in addresses:
                continue
            addresses.add(item.address)
            live = settings.BARA_REPORTS_LIVE_EMAIL and cfg.allow_live and not cfg.sample
            ReportDelivery.objects.create(
                run=owner, recipient=item, address=item.address,
                sender=settings.BARA_REPORTS_FROM_EMAIL if live else "reports@example.invalid",
                provider="resend" if live else "mock", subject=report.title,
                text=report.text, html=report.html, expires_at=expires,
            )
        complete(run, JobStatus.READY)


def deliver(message):
    now = timezone.now()
    if message.expires_at <= now or not message.text or not message.html:
        raise DeliveryError("rendered_message_expired")
    current_recipient = type(message.recipient).objects.select_related("contact").get(pk=message.recipient_id)
    if (
        message.run.organization_id != message.run.configuration.organization_id
        or not message.run.configuration.active
        or not recipient_valid(current_recipient, message.run.organization_id, message.address, now)
    ):
        raise DeliveryError("recipient_revoked_or_mismatched")
    if message.first_attempt_at and message.first_attempt_at < now - timedelta(hours=23):
        raise DeliveryError("provider_idempotency_window_expired")
    if message.provider != "mock" and not message.run.configuration.allow_live:
        raise DeliveryError("configuration_live_approval_revoked")
    if not ReportDelivery.objects.filter(pk=message.pk, claim=message.claim).update(
        first_attempt_at=message.first_attempt_at or now
    ):
        return
    provider_id = get_provider(message.provider).send(message)
    with transaction.atomic():
        complete(message, JobStatus.SIMULATED if message.provider == "mock" else JobStatus.ACCEPTED,
                 provider_id=provider_id)


def process(model, handler, limit):
    processed = 0
    for _ in range(limit):
        job = claim_next(model, timezone.now())
        if job is None:
            break
        if job.attempts > ATTEMPTS:
            fail(job, "attempt_limit_after_lease", False)
        else:
            try:
                handler(job)
            except DeliveryError as exc:
                fail(job, str(exc), exc.retryable)
            except ReportError as exc:
                fail(job, str(exc), False)
            except Exception:
                # Provider and customer data must not be logged with unexpected failures.
                fail(job, "unexpected_worker_failure", True)
        processed += 1
    return processed


def redact_expired(now):
    artifacts = ReportArtifact.objects.filter(expires_at__lte=now, data__isnull=False).update(data=None)
    messages = ReportDelivery.objects.filter(
        expires_at__lte=now,
        status__in=(JobStatus.FAILED, JobStatus.ACCEPTED, JobStatus.DELIVERED,
                    JobStatus.BOUNCED, JobStatus.COMPLAINED, JobStatus.SIMULATED),
    ).exclude(text="", html="").update(text="", html="")
    return artifacts, messages
