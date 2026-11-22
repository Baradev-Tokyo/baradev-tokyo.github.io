from string import Template

from django import forms
from django.utils.translation import gettext, gettext_lazy as _

from .catalog import PACKAGES
from .models import AgreementTemplate, ProjectRequest


class ProjectRequestForm(forms.ModelForm):
    package = forms.ChoiceField(
        label=_("Service package"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].choices = [
            ("", gettext("Choose a package")),
            *((package.slug, gettext(package.name)) for package in PACKAGES),
        ]

    class Meta:
        model = ProjectRequest
        fields = ("package", "name", "email", "company", "brief", "target_date")
        labels = {
            "name": _("Name"),
            "email": _("Email"),
            "company": _("Company"),
            "brief": _("What would you like to build?"),
            "target_date": _("Target launch date"),
        }
        widgets = {
            "brief": forms.Textarea(attrs={"rows": 5}),
            "target_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


class AgreementTemplateForm(forms.ModelForm):
    class Meta:
        model = AgreementTemplate
        fields = ("name", "body")
        help_texts = {
            "body": "Include ${client_name}, ${provider_name}, and ${proposal}. "
                    "Use $$ for a literal dollar sign."
        }

    def clean_body(self):
        body = self.cleaned_data["body"]
        template = Template(body)
        expected = {"client_name", "provider_name", "proposal"}
        if not template.is_valid() or set(template.get_identifiers()) != expected:
            raise forms.ValidationError(self.fields["body"].help_text)
        return body
