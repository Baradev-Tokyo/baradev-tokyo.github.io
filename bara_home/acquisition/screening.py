"""Offline owner-assisted opportunity screening."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol


SKILLS = {
    "python", "django", "postgresql", "google cloud run", "docker", "stripe",
    "rest api", "rest apis", "web application", "web applications", "booking system",
    "booking systems", "automation", "workflow automation",
}


@dataclass(frozen=True)
class Weights:
    technical: int = 25
    budget: int = 20
    clarity: int = 15
    profitability: int = 15
    repeatability: int = 15
    recurring: int = 10

    def __post_init__(self):
        values = vars(self).values()
        if any(type(value) is not int or value < 0 for value in values) or sum(values) != 100:
            raise ValueError("Screening weights must be nonnegative integers that add to 100.")


class ScreeningProvider(Protocol):
    def assess(self, opportunity) -> dict: ...


def integer(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class RulesProvider:
    def __init__(self, weights=None):
        self.weights = weights or Weights()

    def assess(self, item):
        skills = {skill.strip().lower() for skill in item.skills if skill.strip()}
        missing = []
        risks = []
        priority = None
        if item.off_platform_requested:
            priority = "reject_policy_risk"
            risks.append("Off-platform workflow requested. Review marketplace rules.")
        if item.source == "upwork" and item.connects_required != 0:
            priority = priority or "hold_connects"
            if item.connects_required is None:
                missing.append("connects_required")
            risks.append("Zero-Connect submission is not confirmed. Owner review required.")

        fees_known = item.provider_fee is not None and item.delivery_cost is not None
        revenue = item.budget_low
        estimate = None
        if revenue is not None and fees_known:
            estimate = revenue - item.provider_fee - item.delivery_cost

        scores = {
            "technical": Decimal(100) * len(skills & SKILLS) / len(skills) if skills else None,
            "budget": min(Decimal(100), Decimal(100) * revenue / (item.effort_hours * item.target_hourly_rate))
            if revenue is not None and item.effort_hours and item.target_hourly_rate else None,
            "clarity": item.scope_clarity,
            "profitability": max(Decimal(0), min(Decimal(100), Decimal(100) * estimate / revenue))
            if estimate is not None and revenue else None,
            "repeatability": item.repeatability,
            "recurring": None if item.recurring is None else 100 if item.recurring else 0,
        }
        unknown = {
            "skills": not skills, "budget": revenue is None, "currency": not item.currency,
            "original_url": item.source in {"upwork", "fiverr"} and not item.url,
            "effort_hours": item.effort_hours is None, "target_hourly_rate": item.target_hourly_rate is None,
            "provider_fee": item.provider_fee is None, "delivery_cost": item.delivery_cost is None,
            "scope_clarity": item.scope_clarity is None, "repeatability": item.repeatability is None,
            "recurring": item.recurring is None,
        }
        missing.extend(key for key, value in unknown.items() if value)
        if skills - SKILLS:
            risks.append("Some required skills are outside the documented screening skill set.")
        if estimate is not None and estimate < 0:
            priority = priority or "decline_unprofitable"
            risks.append("Conservative estimate is below zero.")
        weights = vars(self.weights)
        evidence = sum(weights[key] for key, value in scores.items() if value is not None)
        fit = integer(sum(value * weights[key] for key, value in scores.items() if value is not None) / evidence) if evidence else None
        recommendation = priority or ("manual_review" if missing else "shortlist" if fit is not None and fit >= 70 else "deprioritize")
        return {
            "opportunity_id": item.external_id, "source": item.source, "url": item.url,
            "title": item.title, "required_skills": item.skills, "currency": item.currency or None,
            "budget": {"low": str(revenue) if revenue is not None else None,
                       "high": str(item.budget_high) if item.budget_high is not None else None},
            "fit_score": fit, "evidence_weight": evidence,
            "effort_hours_estimate": str(item.effort_hours) if item.effort_hours is not None else None,
            "potential_revenue_lower_bound": str(revenue) if revenue is not None else None,
            "estimated_profit_lower_bound_before_owner_labor_and_tax": str(estimate) if estimate is not None else None,
            "risks": risks, "recommendation": recommendation,
            "explanation": "Weighted available evidence. Profit estimate subtracts only supplied fees and delivery costs.",
            "missing_information": missing,
        }
