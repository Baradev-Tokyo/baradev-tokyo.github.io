from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    AuditEvent, AvailabilityRecord, BillingPeriod, CloudResourceOwnership, CustomerContact, EmailDeliveryEvent,
    NotificationTemplate, PaymentEvent, ReportArtifact, ReportConfiguration, ReportDelivery,
    ReportRun, UsageRecord, VerifiedEmailRecipient,
)


class OwnerAdmin(admin.ModelAdmin):
    immutable = ()

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), *(self.immutable if obj else ()))


class HistoryAdmin(OwnerAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = ReportConfiguration
        fields = "__all__"

    def clean_timezone(self):
        value = self.cleaned_data["timezone"]
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise forms.ValidationError("Enter an IANA timezone such as Asia/Tokyo.") from exc
        return value

    def clean(self):
        data = super().clean()
        organization = data.get("organization") or (self.instance.organization if self.instance.pk else None)
        recipients = data.get("recipients")
        if organization and recipients is not None and recipients.exclude(contact__organization=organization).exists():
            self.add_error("recipients", "Choose only recipients in this organization.")
        return data


@admin.register(ReportConfiguration)
class ConfigurationAdmin(OwnerAdmin):
    form = ConfigurationForm
    immutable = ("organization", "kind", "frequency", "timezone", "sample")
    list_display = ("organization", "kind", "frequency", "sample", "allow_live", "active")


@admin.register(CustomerContact, NotificationTemplate, BillingPeriod, CloudResourceOwnership)
class ScopedAdmin(OwnerAdmin):
    immutable = ("organization",)


@admin.register(VerifiedEmailRecipient)
class VerificationAdmin(OwnerAdmin):
    list_display = ("contact", "address", "verified_at", "revoked_at")
    immutable = ("contact", "address", "verified_at")


@admin.register(PaymentEvent)
class PaymentEventAdmin(OwnerAdmin):
    immutable = ("period", "stripe_invoice_id", "currency")
    readonly_fields = ("synchronized_at", "invoiced_minor", "collected_minor", "outstanding_minor")
    list_display = ("stripe_invoice_id", "period", "currency", "synchronized_at")


@admin.register(ReportRun)
class RunAdmin(HistoryAdmin):
    list_display = ("id", "organization", "period_start", "status", "attempts", "next_attempt", "error_code")
    list_filter = ("status", "organization")


@admin.register(ReportDelivery)
class DeliveryAdmin(HistoryAdmin):
    list_display = ("message_id", "run", "provider", "status", "attempts", "error_code")
    list_filter = ("status", "provider")
    exclude = ("html", "text")


@admin.register(ReportArtifact)
class ArtifactAdmin(HistoryAdmin):
    list_display = ("run", "media_type", "expires_at", "download_link")
    exclude = ("data",)

    @admin.display(description="Download")
    def download_link(self, artifact):
        if artifact.expires_at <= timezone.now():
            return "Expired"
        return format_html('<a href="{}">Download</a>',
                           reverse("admin:report_artifact_download", args=[artifact.pk]))

    def get_urls(self):
        return [
            path("<int:pk>/download/", self.admin_site.admin_view(self.download), name="report_artifact_download"),
        ] + super().get_urls()

    def download(self, request, pk):
        if not request.user.is_superuser:
            raise PermissionDenied
        artifact = ReportArtifact.objects.filter(pk=pk, expires_at__gt=timezone.now()).first()
        if not artifact or artifact.data is None:
            raise Http404
        extension = "pdf" if artifact.media_type == "application/pdf" else "html"
        response = HttpResponse(bytes(artifact.data), content_type=artifact.media_type)
        response["Content-Disposition"] = f'attachment; filename="bara-report-{artifact.run_id}.{extension}"'
        return response


admin.site.register((EmailDeliveryEvent, AuditEvent, UsageRecord, AvailabilityRecord), HistoryAdmin)
