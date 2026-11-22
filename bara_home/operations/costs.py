"""Deterministic reporting contracts for billing imports. No cloud side effects."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol


@dataclass(frozen=True)
class CostLine:
    day: date
    invoice_month: str
    project: str
    service: str
    resource: str
    currency: str
    cost: Decimal
    credits: Decimal = Decimal(0)  # Signed export amount, normally negative.


class BillingExport(Protocol):
    def lines(self, start: date, end: date) -> Iterable[CostLine]:
        """Read a bounded inclusive usage range."""


@dataclass(frozen=True)
class SampleExport:
    entries: tuple[CostLine, ...]

    def lines(self, start, end):
        return (entry for entry in self.entries if start <= entry.day <= end)


@dataclass(frozen=True)
class ResourceMapping:
    project: str
    client: str
    starts: date
    ends: date | None = None
    service: str = ""
    resource: str = ""

    @property
    def specificity(self):
        return (bool(self.resource), bool(self.service))

    def matches(self, line):
        return (
            self.project == line.project and self.starts <= line.day
            and (self.ends is None or self.ends >= line.day)
            and (not self.service or self.service == line.service)
            and (not self.resource or self.resource == line.resource)
        )


@dataclass(frozen=True)
class Settlement:
    client: str
    invoice_month: str
    currency: str
    received: Decimal
    refunds: Decimal
    fees: Decimal


def summarize(export: BillingExport, start: date, end: date, mappings, settlements=()):
    daily = defaultdict(Decimal)
    monthly = defaultdict(Decimal)
    revenue = defaultdict(Decimal)
    mappings = tuple(mappings)
    for line in export.lines(start, end):
        eligible = [mapping for mapping in mappings if mapping.matches(line)]
        eligible.sort(key=lambda mapping: mapping.specificity, reverse=True)
        if len(eligible) > 1 and eligible[0].specificity == eligible[1].specificity:
            raise ValueError("Ambiguous effective billing resource mapping.")
        client = eligible[0].client if eligible else None
        net = line.cost + line.credits
        daily[line.day, client, line.currency] += net
        monthly[line.invoice_month, client, line.currency] += net
    for item in settlements:
        revenue[item.invoice_month, item.client, item.currency] += item.received - item.refunds - item.fees
    margin = {
        key: revenue.get(key, Decimal(0)) - monthly.get(key, Decimal(0))
        for key in monthly.keys() | revenue.keys() if key[1] is not None
    }
    return dict(daily), dict(monthly), margin


def budget_thresholds(net_cost: Decimal, budget: Decimal, fractions=(Decimal(".5"), Decimal(".9"), Decimal("1"))):
    if budget <= 0:
        raise ValueError("Budget must be positive.")
    return tuple(fraction for fraction in fractions if net_cost >= budget * fraction)


@dataclass(frozen=True)
class Receivable:
    invoice_id: str
    status: str
    due: date | None
    grace_ends: date | None


def overdue_for_review(invoices, today: date):
    return [
        item.invoice_id for item in invoices
        if item.status == "open" and (deadline := item.grace_ends or item.due) and deadline < today
    ]
