from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from operations.models import Invoice, Subscription, Workspace
from reporting.models import PaymentEvent, UsageRecord
from services.models import ProjectRequest
from .models import MarketplaceListing, MarketplaceReceipt, Opportunity
from .screening import RulesProvider


@require_http_methods(["GET", "POST"])
def review_opportunity(request, workspace_id, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    jobs = Opportunity.objects.filter(organization_id=workspace_id)
    job = get_object_or_404(jobs, pk=pk)
    can_draft = not job.off_platform_requested and bool(job.description.strip()) and (
        job.source != Opportunity.Source.UPWORK or job.connects_required == 0
    )
    context = {
        **admin.site.each_context(request), "job": job, "can_draft": can_draft,
        "result": RulesProvider().assess(job), "title": job.title,
    }
    if request.method == "POST":
        focus = request.POST.get("focus", "").strip()
        if len(focus) > 500 or not can_draft:
            return render(request, "acquisition/job.html", {
                **context, "error": "Drafting requires an eligible opportunity and notes of at most 500 characters.",
            }, status=400)
        first_step = f"My proposed starting point is to {focus.rstrip('.')}." if focus else (
            "I’d start by reviewing your existing setup and confirming the first deliverable."
        )
        closing = (
            "Could you share what you already use and which deliverable should come first? "
            "Once we agree on scope, I can prepare a custom offer here on Fiverr."
            if job.source == Opportunity.Source.FIVERR else
            "Could you share what is already in place and which outcome matters most for the first release?"
        )
        draft = (
            f"Hello,\n\nI’d like to help with {job.title}. "
            f"{first_step}\n\n"
            "I would first confirm the deliverables and acceptance criteria, then agree on milestones "
            "before implementation.\n\n"
            f"{closing}\n\n"
            "Joey | Bara Development"
        )
        eligible_jobs = jobs.filter(pk=pk, proposal_approved_at__isnull=True, off_platform_requested=False)
        if job.source == Opportunity.Source.UPWORK:
            eligible_jobs = eligible_jobs.filter(connects_required=0)
        eligible_jobs.update(
            proposal_draft=draft, proposal_approved_at=timezone.now(),
        )
        return redirect("bara_job_review", workspace_id=workspace_id, pk=pk)
    return render(request, "acquisition/job.html", context)


@require_safe
def dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    workspaces = Workspace.objects.order_by("name", "pk")
    selected = request.GET.get("workspace", "")
    workspace = get_object_or_404(workspaces, pk=int(selected)) if selected.isdecimal() and len(selected) <= 18 else workspaces.first()

    today = timezone.now().astimezone(ZoneInfo("Asia/Tokyo")).date()
    month_input = request.GET.get("month", "")
    try:
        month = date.fromisoformat(month_input + "-01") if month_input else today.replace(day=1)
        if month.year >= 9999:
            raise ValueError
    except ValueError:
        month = today.replace(day=1)
    end = (month + timedelta(days=32)).replace(day=1)
    context = {
        **admin.site.each_context(request), "title": "Bara operations",
        "workspaces": workspaces, "workspace": workspace, "month": month.strftime("%Y-%m"),
        "inquiries": ProjectRequest.objects.count(),
        "proposal_drafts": ProjectRequest.objects.exclude(proposal="").count(),
    }
    if workspace:
        opportunity = Opportunity.objects.filter(organization=workspace)
        shortlist = opportunity.exclude(
            Q(source=Opportunity.Source.UPWORK) &
            (Q(connects_required__isnull=True) | Q(connects_required__gt=0))
        )
        receipts = MarketplaceReceipt.objects.filter(organization=workspace, earned_on__gte=month, earned_on__lt=end)
        marketplace = list(receipts.values("source", "currency").annotate(
            gross_total=Sum("gross"), fees=Sum("fee"), net=Sum(F("gross") - F("fee")),
            direct_costs=Sum("direct_cost"), count=Count("pk"),
            unknown_costs=Count("pk", filter=Q(direct_cost__isnull=True)),
        ).order_by("source", "currency"))
        for row in marketplace:
            row["margin"] = None if row["unknown_costs"] else row["net"] - (row["direct_costs"] or Decimal(0))
        context.update({
            "opportunities": [(item, RulesProvider().assess(item)) for item in shortlist.order_by("-pk")[:20]],
            "orders": receipts.order_by("-earned_on", "-pk")[:20],
            "marketplace": marketplace,
            "listings": MarketplaceListing.objects.filter(organization=workspace).order_by("source", "pk")[:20],
            "direct_customers": workspace.billingcustomer_set.count(),
            "accepted": opportunity.filter(status="accepted").count(),
            "subscriptions": Subscription.objects.filter(customer__workspace=workspace, status="active").count(),
            "open_invoices": Invoice.objects.filter(customer__workspace=workspace, status="open").count(),
            "stripe_payments": PaymentEvent.objects.filter(
                period__organization=workspace, period__start__gte=month, period__start__lt=end,
                synchronized_at__isnull=False,
            ).values("currency").annotate(collected=Sum("collected_minor"), outstanding=Sum("outstanding_minor")),
            "hosting": UsageRecord.objects.filter(
                period__organization=workspace, ownership__organization=workspace,
                period__start=month, period__end=end, day__gte=month, day__lt=end,
            ).values("currency", "estimated").annotate(net=Sum(F("cost") + F("credits"))),
        })
    return render(request, "acquisition/dashboard.html", context)
