from calendar import Calendar
from datetime import date, datetime, time, timedelta
from uuid import UUID
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from blog.posts import POSTS
from operations.models import Workspace

from .models import AutomationPolicy, ChannelSettings, ContentDraft, Platform, PublicationJob, QueueAudit, State
from .replenish import generate_article_draft, replenish
from .services import TOKYO, approve_draft, can_change, change_job, enqueue, save_draft, set_channel, workspace_lock


@require_safe
def draft_media(request, workspace_id, draft_id):
    if not request.user.is_superuser:
        raise PermissionDenied
    draft = get_object_or_404(ContentDraft, workspace_id=workspace_id, pk=draft_id)
    if not draft.media_bytes:
        raise Http404
    content_type = "image/png" if draft.media.endswith(".png") else "image/jpeg"
    response = HttpResponse(bytes(draft.media_bytes), content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def tokyo_time(value):
    if len(value) != 16:
        raise ValidationError("Enter a Tokyo publication date and time.")
    result = datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=TOKYO)
    if result <= timezone.now():
        raise ValidationError("Choose a future publication time.")
    return result


def process_action(request, workspace):
    data = request.POST
    actor = request.user
    action = data["action"]
    if action in {"schedule", "approve"}:
        draft_id = int(data["draft"])
        if action == "approve":
            approve_draft(workspace.pk, draft_id, actor)
            return None, draft_id
        campaign = UUID(data["campaign"]) if data.get("campaign") else None
        if campaign and not PublicationJob.objects.filter(workspace=workspace, campaign=campaign).exists():
            raise ValidationError("Choose a campaign from this workspace.")
        job = enqueue(workspace.pk, draft_id, tokyo_time(data["scheduled_at"]), actor, campaign)
        return job.pk, None
    if action == "channel":
        set_channel(workspace.pk, data["platform"], data["paused"] == "1", actor)
        return None, None
    if action == "policy":
        horizon = int(data["horizon"])
        if not 1 <= horizon <= 60:
            raise ValidationError("Choose a horizon from 1 to 60 days.")
        with workspace_lock(workspace.pk) as policy:
            policy.horizon_days = horizon
            policy.enabled = "enabled" in data
            policy.generation_enabled = "generation" in data
            policy.save(update_fields=["horizon_days", "enabled", "generation_enabled"])
            QueueAudit.objects.create(workspace=workspace, actor=actor, action="Updated queue policy")
        return None, None
    if action == "replenish":
        messages.info(request, f"Replenishment filled {replenish(workspace.pk)} slot(s).")
        return None, None
    if action == "new":
        draft = save_draft(workspace.pk, data["platform"], data["category"].strip(), data["text"],
                           data.get("media", "").strip(), actor=actor)
        return None, draft.pk

    job = PublicationJob.objects.select_related("draft").get(workspace=workspace, pk=UUID(data["job"]))
    if action in {"edit", "generate"}:
        if action == "edit":
            draft = save_draft(workspace.pk, job.platform, data["category"].strip(), data["text"],
                               data.get("media", "").strip(), actor=actor)
        else:
            draft = generate_article_draft(workspace.pk, job.platform, data["article"],
                                           data.get("media", "").strip(), actor=actor)
        messages.info(request, "Replacement draft saved. Approve it, then select it as a replacement.")
        return job.pk, draft.pk
    if action.startswith("cancel") and data.get("confirm") != "yes":
        raise ValidationError("Confirm cancellation before saving.")
    if action == "replace" and data.get("scope") == "campaign" and data.get("confirm") != "yes":
        raise ValidationError("Confirm replacement of the entire campaign.")
    change_job(
        workspace.pk, job.pk, action, actor,
        scheduled_at=tokyo_time(data["scheduled_at"]) if action == "reschedule" else None,
        replacements={platform: int(data[f"draft_{platform}"]) for platform in Platform.values
                      if data.get(f"draft_{platform}")},
        entire_campaign=data.get("scope") == "campaign",
        expected_revision=int(data["expected_revision"]),
    )
    return job.pk, None


def calendar_days(request, jobs):
    today = timezone.localdate(timezone=TOKYO)
    try:
        anchor = date.fromisoformat(request.GET.get("date", ""))
        if not 1900 <= anchor.year <= 2100:
            anchor = today
    except ValueError:
        anchor = today
    monthly = request.GET.get("mode") == "month"
    start = anchor - timedelta(days=anchor.weekday())
    if monthly:
        weeks = Calendar().monthdatescalendar(anchor.year, anchor.month)
        previous = anchor.replace(day=1) - timedelta(days=1)
        following = (anchor.replace(day=1) + timedelta(days=32)).replace(day=1)
    else:
        weeks = [[start + timedelta(days=index) for index in range(7)]]
        previous, following = start - timedelta(days=7), start + timedelta(days=7)
    days = {day: [] for week in weeks for day in week}
    for job in jobs.filter(scheduled_at__gte=datetime.combine(weeks[0][0], time.min, TOKYO),
                           scheduled_at__lt=datetime.combine(weeks[-1][-1] + timedelta(days=1), time.min, TOKYO)):
        days[job.scheduled_at.astimezone(TOKYO).date()].append(job)
    return {
        "weeks": [[(day, days[day]) for day in week] for week in weeks], "anchor": anchor,
        "mode": "month" if monthly else "week", "previous": previous, "following": following,
    }


@require_http_methods(["GET", "HEAD", "POST"])
def calendar_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    workspaces = Workspace.objects.order_by("name", "pk")
    selected = request.GET.get("workspace")
    workspace = get_object_or_404(workspaces, pk=selected) if selected and selected.isascii() and selected.isdecimal() and len(selected) < 19 else workspaces.first()
    context = {**admin.site.each_context(request), "title": "Content calendar", "workspaces": workspaces,
               "workspace": workspace, "platforms": Platform.choices, "states": State.choices}
    if not workspace:
        return render(request, "content_queue/calendar.html", context)

    if request.method == "POST":
        try:
            job_id, draft_id = process_action(request, workspace)
        except (ValidationError, ValueError, KeyError, ObjectDoesNotExist) as exc:
            messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Check the publication details and try again.")
            return redirect(request.get_full_path())
        messages.success(request, "Content queue updated.")
        query = f"?workspace={workspace.pk}"
        if job_id:
            query += f"&job={job_id}"
        if draft_id:
            query += f"&draft={draft_id}"
        return redirect(reverse("content_queue:calendar") + query)

    jobs = PublicationJob.objects.filter(workspace=workspace).select_related("draft")
    drafts = ContentDraft.objects.filter(workspace=workspace).order_by("-pk")
    filtered = jobs
    for parameter, field in (("platform", "platform"), ("status", "state"), ("category", "draft__category")):
        if request.GET.get(parameter):
            filtered = filtered.filter(**{field: request.GET[parameter]})
    order = {"latest": "-scheduled_at", "platform": "platform", "category": "draft__category",
             "status": "state"}.get(request.GET.get("sort"), "scheduled_at")
    filtered = filtered.order_by(order, "scheduled_at", "pk")
    policy = AutomationPolicy.objects.filter(workspace=workspace).first() or AutomationPolicy()
    settings = {channel.platform: channel.paused for channel in ChannelSettings.objects.filter(workspace=workspace)}
    params = request.GET.copy()
    for field in ("job", "draft", "date", "mode"):
        params.pop(field, None)
    params["workspace"] = workspace.pk
    context.update(
        calendar_days(request, filtered), filters=request.GET, query=params.urlencode(), policy=policy,
        channels=[(slug, label, settings.get(slug, True)) for slug, label in Platform.choices],
        categories=drafts.order_by("category").values_list("category", flat=True).distinct(),
        upcoming=filtered.filter(state__in=[State.QUEUED, State.PUBLISHING])[:100],
        history=filtered.filter(state__in=[State.PUBLISHED, State.FAILED, State.CANCELLED]).order_by("-scheduled_at")[:50],
        drafts=drafts.exclude(publicationjob__state__in=[State.PUBLISHED, State.PUBLISHING, State.QUEUED, State.FAILED])[:50],
        audits=QueueAudit.objects.filter(workspace=workspace).select_related("actor").order_by("-pk")[:15],
        articles=POSTS,
    )
    if request.GET.get("job"):
        try:
            job = get_object_or_404(jobs, pk=UUID(request.GET["job"]))
        except ValueError:
            raise Http404("Invalid publication.")
        campaign = jobs.filter(campaign=job.campaign).exclude(state=State.CANCELLED)
        approved = drafts.filter(state=State.VALIDATED, approved_by__isnull=False).exclude(
            publicationjob__state__in=[State.PUBLISHED, State.PUBLISHING, State.QUEUED, State.FAILED],
        )
        context.update(job=job, mutable=can_change(job), revisions=job.history.select_related("draft", "actor").order_by("-pk"),
                       attempts=job.attempts.order_by("-pk"), replacements=approved.filter(platform=job.platform),
                       campaign_channels=[(item, approved.filter(platform=item.platform)) for item in campaign],
                       campaign_mutable=all(can_change(item) for item in campaign),
                       edit_revision=job.history.filter(action__in=["scheduled", "replace", "reschedule", "cancel",
                                                                    "cancel_replace"]).order_by("-pk").first())
        if job.platform == Platform.X and not settings.get(Platform.X, True) and can_change(job):
            context["x_compose_url"] = "https://x.com/intent/tweet?" + urlencode({"text": job.draft.text})
    if request.GET.get("draft", "").isascii() and request.GET.get("draft", "").isdecimal() and len(request.GET["draft"]) < 19:
        context["draft_preview"] = get_object_or_404(drafts, pk=int(request.GET["draft"]))
    return render(request, "content_queue/calendar.html", context)
