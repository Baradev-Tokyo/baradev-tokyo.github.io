"""Provider-compatible import boundaries. Nothing is fetched on startup."""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, AvailabilityRecord, BillingPeriod, CloudResourceOwnership, PaymentEvent, UsageRecord


@dataclass(frozen=True)
class CloudCost:
    source_key: str
    day: date
    project: str
    resource: str
    service: str
    currency: str
    cost: Decimal
    credits: Decimal


class CloudBillingSource(Protocol):
    def rows(self, start: date, end: date, projects: tuple[str, ...]) -> Iterable[CloudCost]: ...


@dataclass(frozen=True)
class AvailabilitySample:
    day: date
    project: str
    resource: str
    checks: int
    successful_checks: int


class MonitoringSource(Protocol):
    def availability(self, start: date, end: date, projects: tuple[str, ...]) -> Iterable[AvailabilitySample]: ...


def read_uptime(client, project, check_id, resource, start, end, zone="Asia/Tokyo"):
    """Read one explicitly configured Cloud Monitoring uptime check using ADC."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,150}", check_id) or (end - start).days not in range(1, 33):
        raise ValueError("Use a valid uptime check ID and bounded range.")
    tz = ZoneInfo(zone)
    interval = {
        "start_time": datetime.combine(start, time.min, tz),
        "end_time": datetime.combine(end, time.min, tz),
    }
    checks = defaultdict(lambda: [0, 0])
    series = client.list_time_series(request={
        "name": f"projects/{project}",
        "filter": f'metric.type="monitoring.googleapis.com/uptime_check/check_passed" AND metric.labels.check_id="{check_id}"',
        "interval": interval,
        "view": "FULL",
    }, timeout=60)
    for timeseries in series:
        for point in timeseries.points:
            day = point.interval.end_time.astimezone(tz).date()
            if start <= day < end:
                checks[day][0] += 1
                checks[day][1] += bool(point.value.bool_value)
    return [AvailabilitySample(day, project, resource, count, passed)
            for day, (count, passed) in sorted(checks.items())]


def effective_owners(project, resource, day):
    return CloudResourceOwnership.objects.filter(
        project_id=project, resource=resource, starts_on__lte=day,
    ).exclude(ends_before__lte=day)


def resolve_owner(period, project, resource, day):
    matches = list(effective_owners(project, resource, day).select_for_update()[:2])
    if len(matches) != 1 or matches[0].organization_id != period.organization_id or not period.start <= day < period.end:
        raise ValueError("Ambiguous or out-of-scope cloud resource.")
    return matches[0]


@transaction.atomic
def import_availability(period, samples):
    period = BillingPeriod.objects.select_for_update().get(pk=period.pk)
    seen = set()
    for sample in samples:
        owner = resolve_owner(period, sample.project, sample.resource, sample.day)
        key = (owner.pk, sample.day)
        if key in seen or not 0 <= sample.successful_checks <= sample.checks:
            raise ValueError("Duplicate or invalid availability sample.")
        seen.add(key)
        AvailabilityRecord.objects.update_or_create(
            period=period, ownership=owner, day=sample.day, defaults={
                "checks": sample.checks, "successful_checks": sample.successful_checks,
            }
        )
    AuditEvent.objects.create(
        organization_id=period.organization_id, kind="availability.imported", correlation=str(period.pk),
    )
    return len(seen)


class BigQueryBillingSource:
    """Read a pre-aggregated, day-partitioned authorized view using ADC."""

    def __init__(self, client, view, *, maximum_bytes_billed=100_000_000):
        if not re.fullmatch(r"[a-z][a-z0-9-]*\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", view):
            raise ValueError("Use a fully qualified BigQuery view name.")
        if maximum_bytes_billed <= 0:
            raise ValueError("A positive BigQuery byte ceiling is required.")
        self.client = client
        self.view = view
        self.maximum_bytes_billed = maximum_bytes_billed

    def rows(self, start, end, projects):
        from google.cloud import bigquery

        if not projects or (end - start).days not in range(1, 33):
            raise ValueError("Use a bounded range and explicit projects.")
        query = f"""
            SELECT source_key, day, project, resource, service, currency, cost, credits
            FROM `{self.view}`
            WHERE day >= @start AND day < @end AND project IN UNNEST(@projects)
            LIMIT 10001
        """
        config = bigquery.QueryJobConfig(
            maximum_bytes_billed=self.maximum_bytes_billed,
            query_parameters=[
                bigquery.ScalarQueryParameter("start", "DATE", start),
                bigquery.ScalarQueryParameter("end", "DATE", end),
                bigquery.ArrayQueryParameter("projects", "STRING", list(projects)),
            ],
        )
        rows = list(self.client.query(query, job_config=config).result(timeout=60))
        if len(rows) > 10000:
            raise ValueError("Billing rows exceed the configured import limit.")
        for row in rows:
            yield CloudCost(*(row[key] for key in
                              ("source_key", "day", "project", "resource", "service", "currency", "cost", "credits")))


@transaction.atomic
def import_cloud_costs(period, rows, *, estimated=True):
    """Replace stable source rows after checking the workspace and effective ownership."""
    period = BillingPeriod.objects.select_for_update().get(pk=period.pk)
    seen = set()
    count = 0
    for row in rows:
        owner = resolve_owner(period, row.project, row.resource, row.day)
        if not row.source_key or row.source_key in seen:
            raise ValueError("Missing or duplicate billing source key.")
        seen.add(row.source_key)
        UsageRecord.objects.update_or_create(period=period, source_key=row.source_key, defaults={
            "ownership": owner, "day": row.day, "service": row.service,
            "currency": row.currency.upper(), "cost": row.cost, "credits": row.credits, "estimated": estimated,
        })
        count += 1
    AuditEvent.objects.create(
        organization_id=period.organization_id, kind="usage.imported", correlation=str(period.pk),
    )
    return count


@transaction.atomic
def sync_verified_stripe_invoice(workspace_id, invoice):
    mapping = PaymentEvent.objects.select_for_update().filter(
        stripe_invoice_id=invoice["id"], period__organization_id=workspace_id,
    ).first()
    if not mapping or invoice["status"] == "draft":
        return False
    if mapping.currency.upper() != invoice["currency"].upper():
        return False
    if invoice["status"] == "void":
        invoiced, collected, outstanding = 0, 0, 0
    else:
        invoiced, collected, outstanding = (invoice.get(key) for key in ("total", "amount_paid", "amount_remaining"))
        if not all(type(value) is int and value >= 0 for value in (invoiced, collected, outstanding)):
            return False
    mapping.invoiced_minor = invoiced
    mapping.collected_minor = collected
    mapping.outstanding_minor = outstanding
    mapping.synchronized_at = timezone.now()
    mapping.save(update_fields=["invoiced_minor", "collected_minor", "outstanding_minor", "synchronized_at"])
    return True
