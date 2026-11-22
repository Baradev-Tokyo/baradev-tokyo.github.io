from string import Template

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import AgreementTemplateForm
from .models import AgreementTemplate, ProjectRequest


@admin.register(AgreementTemplate)
class AgreementTemplateAdmin(admin.ModelAdmin):
    form = AgreementTemplateForm


@admin.register(ProjectRequest)
class ProjectRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "package", "received_at", "contract_created_at")
    list_filter = ("package", "contract_created_at")
    search_fields = ("name", "company", "email")
    ordering = ("-received_at",)
    readonly_fields = (
        "received_at", "name", "email", "company", "brief", "target_date",
        "package", "estimate", "approved_proposal", "contract_draft", "contract_created_at",
        "documents",
    )
    actions = ("create_contract",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return not (obj and obj.contract_created_at) and super().has_change_permission(request, obj)

    def save_model(self, request, obj, form, change):
        # Limit writes to the editable fields so a concurrent review cannot erase a draft.
        updated = ProjectRequest.objects.filter(
            pk=obj.pk, contract_created_at__isnull=True
        ).update(**{field: getattr(obj, field) for field in form.changed_data})
        if not updated and form.changed_data:
            raise PermissionDenied("This request already has a contract draft.")

    @admin.action(description="Approve saved proposal and create contract draft", permissions=["change"])
    def create_contract(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select one reviewed request at a time.", messages.ERROR)
            return

        project = queryset.select_related("agreement_template").first()
        if not project or project.contract_created_at:
            self.message_user(request, "No pending request selected.", messages.INFO)
            return
        if not self.has_change_permission(request, project):
            raise PermissionDenied
        if not all((project.client_legal_name.strip(), project.provider_legal_name.strip(),
                    project.agreement_template, project.proposal.strip())):
            self.message_user(
                request, "Save the reviewed proposal, both legal names, and an agreement template first.",
                messages.ERROR,
            )
            return

        try:
            contract = Template(project.agreement_template.body).substitute(
                client_name=project.client_legal_name,
                provider_name=project.provider_legal_name,
                proposal=project.proposal,
            )
        except (KeyError, ValueError):
            self.message_user(request, "Correct the agreement template placeholders.", messages.ERROR)
            return

        if ProjectRequest.objects.filter(
            pk=project.pk, contract_created_at__isnull=True, proposal=project.proposal,
            client_legal_name=project.client_legal_name,
            provider_legal_name=project.provider_legal_name,
            agreement_template=project.agreement_template,
        ).update(
            approved_proposal=project.proposal,
            contract_draft=f"DRAFT FOR REVIEW\n\n{contract}",
            contract_created_at=timezone.now(),
        ):
            self.message_user(request, "Contract draft created.")
        else:
            self.message_user(request, "The request changed. Review it and try again.", messages.WARNING)

    @admin.display(description="Download documents")
    def documents(self, project):
        url = reverse("admin:services_projectrequest_download", args=(project.pk, "proposal"))
        if project.contract_created_at:
            contract_url = reverse(
                "admin:services_projectrequest_download", args=(project.pk, "contract")
            )
            return format_html('<a href="{}">Proposal</a> · <a href="{}">Contract draft</a>',
                               url, contract_url)
        return format_html('<a href="{}">Proposal draft</a>', url)

    def get_urls(self):
        return [
            path("<int:object_id>/download/<slug:kind>/",
                 self.admin_site.admin_view(self.download),
                 name="services_projectrequest_download"),
        ] + super().get_urls()

    def download(self, request, object_id, kind):
        project = self.get_object(request, str(object_id))
        if project is None:
            raise Http404
        if not self.has_view_or_change_permission(request, project):
            raise PermissionDenied
        if kind == "proposal":
            document = project.approved_proposal or project.proposal
        elif kind == "contract" and project.contract_created_at:
            document = project.contract_draft
        else:
            raise Http404
        response = HttpResponse(document, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="bara-{kind}-{project.pk}.txt"'
        return response
