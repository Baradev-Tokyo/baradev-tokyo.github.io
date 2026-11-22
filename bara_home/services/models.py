from django.db import models


class AgreementTemplate(models.Model):
    name = models.CharField(max_length=120, unique=True)
    body = models.TextField(help_text="Paste the reviewed terms with the required placeholders.")

    def __str__(self):
        return self.name


class ProjectRequest(models.Model):
    received_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=150, blank=True)
    brief = models.TextField(max_length=4000)
    target_date = models.DateField(null=True, blank=True)
    package = models.CharField(max_length=100)
    estimate = models.CharField(max_length=60)
    proposal = models.TextField(
        help_text="Replace provisional scope, timeline and pricing with the agreed details."
    )
    client_legal_name = models.CharField(max_length=200, blank=True)
    provider_legal_name = models.CharField(max_length=200, blank=True)
    agreement_template = models.ForeignKey(
        AgreementTemplate, on_delete=models.PROTECT, null=True, blank=True
    )
    approved_proposal = models.TextField(blank=True, editable=False)
    contract_draft = models.TextField(blank=True, editable=False)
    contract_created_at = models.DateTimeField(null=True, editable=False)

    def __str__(self):
        return f"{self.name} / {self.package}"
