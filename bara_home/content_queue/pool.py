from urllib.parse import urlsplit, urlunsplit

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from operations.models import Workspace

from .models import ContentPoolEntry, Platform, QueueAudit
from .services import save_draft


class LinkForm(forms.Form):
    url = forms.URLField(label="Source link", max_length=1000, assume_scheme="https")
    note = forms.CharField(label="Private note", max_length=2000, required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean_url(self):
        parsed = urlsplit(self.cleaned_data["url"])
        if parsed.scheme != "https" or parsed.username is not None:
            raise ValidationError("Enter an HTTPS link without credentials.")
        return urlunsplit(parsed._replace(netloc=parsed.netloc.lower(), fragment=""))


class ShareForm(forms.Form):
    platform = forms.ChoiceField(choices=[(key, label) for key, label in Platform.choices if key != Platform.LINKEDIN])
    commentary = forms.CharField(label="Your caption or commentary", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    media = forms.CharField(label="Optional rights-cleared Bara image path (JPEG required for Instagram)",
                            max_length=150, required=False)


@require_http_methods(["GET", "HEAD", "POST"])
def content_pool(request, workspace_id):
    if not request.user.is_superuser:
        raise PermissionDenied
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    entries = ContentPoolEntry.objects.filter(workspace=workspace).order_by("-pk")
    selected_id = request.GET.get("entry", "")
    selected = get_object_or_404(entries, pk=int(selected_id)) if (
        selected_id.isascii() and selected_id.isdecimal() and len(selected_id) < 19
    ) else None
    action = request.POST.get("action")
    link_form = LinkForm(request.POST if action == "add" else None)
    share_form = ShareForm(request.POST if action == "draft" else None)
    if action == "add" and link_form.is_valid():
        with transaction.atomic():
            entry, created = entries.get_or_create(
                workspace=workspace, url=link_form.cleaned_data["url"],
                defaults={"created_by": request.user, "note": link_form.cleaned_data["note"]},
            )
            if created:
                QueueAudit.objects.create(workspace=workspace, actor=request.user, action=f"Added pool link {entry.pk}")
        messages.success(request, "Source saved." if created else "This source is already in the pool.")
        return redirect(f"{reverse('content_queue:pool', args=[workspace_id])}?entry={entry.pk}")
    if action == "draft" and selected and share_form.is_valid():
        data = share_form.cleaned_data
        try:
            draft = save_draft(workspace_id, data["platform"], "Link shares",
                               f"{data['commentary']}\n\nSource: {selected.url}", data["media"], actor=request.user)
        except ValidationError as exc:
            share_form.add_error(None, exc)
        else:
            return redirect(f"{reverse('content_queue:calendar')}?workspace={workspace_id}&draft={draft.pk}#drafts")
    return render(request, "content_queue/pool.html", {
        **admin.site.each_context(request), "title": "Content pool", "workspace": workspace,
        "entries": entries[:100], "selected": selected, "link_form": link_form, "share_form": share_form,
    })
