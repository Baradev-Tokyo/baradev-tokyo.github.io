import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .email_delivery import DeliveryError, verify_resend
from .models import AuditEvent, EmailDeliveryEvent, JobStatus, ReportDelivery

logger = logging.getLogger(__name__)

OUTCOMES = {
    "email.delivered": JobStatus.DELIVERED,
    "email.bounced": JobStatus.BOUNCED,
    "email.complained": JobStatus.COMPLAINED,
}
PRIORITY = {JobStatus.DELIVERED: 1, JobStatus.BOUNCED: 2, JobStatus.COMPLAINED: 3}


@transaction.atomic
def record_outcome(event_id, kind, provider_id):
    message = ReportDelivery.objects.select_for_update().filter(provider="resend", provider_id=provider_id).first()
    if message is None:
        # A fast webhook may arrive before the sending process stores the provider ID.
        return False
    _, created = EmailDeliveryEvent.objects.get_or_create(
        provider_event_id=event_id, defaults={"delivery": message, "kind": kind}
    )
    status = OUTCOMES[kind]
    if created and PRIORITY[status] > PRIORITY.get(message.status, 0):
        message.status = status
        message.save(update_fields=["status"])
        AuditEvent.objects.create(
            organization_id=message.run.organization_id,
            kind=kind, correlation=str(message.message_id),
        )
        if status in (JobStatus.BOUNCED, JobStatus.COMPLAINED):
            logger.error("bara_reporting_terminal model=reportdelivery job=%s code=%s", message.pk, status)
    return True


@csrf_exempt
@require_POST
def delivery_webhook(request):
    if not settings.BARA_RESEND_WEBHOOK_SECRET:
        raise Http404
    try:
        event_id = verify_resend(request.body, request.headers, settings.BARA_RESEND_WEBHOOK_SECRET)
        event = json.loads(request.body)
        kind = event["type"]
        if not isinstance(kind, str):
            raise ValueError
        if kind not in OUTCOMES:
            return HttpResponse(status=204)
        identifier = event["data"]["email_id"]
        if not isinstance(identifier, str) or not identifier:
            raise ValueError
    except (DeliveryError, UnicodeError, ValueError, TypeError, KeyError):
        return HttpResponse(status=400)
    return HttpResponse(status=204 if record_outcome(event_id, kind, identifier) else 503)
