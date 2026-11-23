from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from operations.models import Workspace
from services.catalog import PACKAGE_BY_SLUG


def valid_source_url(value, source):
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
    except ValueError:
        return False
    platform = {"upwork": "upwork.com", "fiverr": "fiverr.com"}.get(source)
    return bool(host and parsed.scheme == "https" and not parsed.username
                and (not platform or host in (platform, "www." + platform)))


class Opportunity(models.Model):
    class Source(models.TextChoices):
        UPWORK = "upwork", "Upwork"
        FIVERR = "fiverr", "Fiverr"
        DIRECT = "direct", "Direct"

    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    source = models.CharField(max_length=10, choices=Source)
    external_id = models.CharField(max_length=150)
    url = models.URLField(blank=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True, max_length=4000)
    skills = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=[
        ("new", "New"), ("review", "Review"), ("accepted", "Accepted"), ("declined", "Declined"),
    ], default="new")
    currency = models.CharField(max_length=3, blank=True)
    budget_low = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                     validators=[MinValueValidator(0)])
    budget_high = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                      validators=[MinValueValidator(0)])
    provider_fee = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                       validators=[MinValueValidator(0)])
    delivery_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(0)])
    effort_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                      validators=[MinValueValidator(0.01)])
    target_hourly_rate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                             validators=[MinValueValidator(0.01)])
    scope_clarity = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    repeatability = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    recurring = models.BooleanField(null=True, blank=True)
    connects_required = models.PositiveSmallIntegerField(null=True, blank=True)
    off_platform_requested = models.BooleanField(default=False)
    proposal_draft = models.TextField(blank=True, editable=False)
    proposal_approved_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "source", "external_id"],
                                               name="unique_workspace_opportunity")]

    def clean(self):
        if not isinstance(self.skills, list) or any(not isinstance(skill, str) for skill in self.skills):
            raise ValidationError({"skills": "Use a list of required skills."})
        if self.url and not valid_source_url(self.url, self.source):
            raise ValidationError({"url": "Use an HTTPS link on the selected platform."})
        if self.budget_low is not None and self.budget_high is not None and self.budget_high < self.budget_low:
            raise ValidationError({"budget_high": "Budget maximum cannot be below the minimum."})
        currency = self.currency or ""
        if any(value is not None for value in (
            self.budget_low, self.budget_high, self.provider_fee, self.delivery_cost, self.target_hourly_rate,
        )) and not (len(currency) == 3 and currency.isascii() and currency.isalpha()):
            raise ValidationError({"currency": "Specify the currency for monetary inputs."})
        self.currency = currency.upper()

    def __str__(self):
        return self.title


class MarketplaceListing(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    source = models.CharField(max_length=10, choices=Opportunity.Source.choices[:2])
    external_id = models.CharField(max_length=150)
    service_slug = models.SlugField()
    url = models.URLField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "source", "external_id"],
                                               name="unique_workspace_marketplace_listing")]

    def clean(self):
        if self.service_slug not in PACKAGE_BY_SLUG:
            raise ValidationError({"service_slug": "Use a canonical Bara package slug."})
        if self.url and not valid_source_url(self.url, self.source):
            raise ValidationError({"url": "Use an HTTPS link on the selected platform."})


class MarketplaceReceipt(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    source = models.CharField(max_length=10, choices=Opportunity.Source.choices[:2])
    external_id = models.CharField(max_length=150)
    order_url = models.URLField(blank=True)
    earned_on = models.DateField()
    currency = models.CharField(max_length=3)
    gross = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    fee = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    direct_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                      validators=[MinValueValidator(0)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "source", "external_id"],
                                               name="unique_workspace_marketplace_receipt")]

    def clean(self):
        self.currency = (self.currency or "").upper()
        if len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isalpha():
            raise ValidationError({"currency": "Use a three-letter currency code."})
        if self.gross is not None and self.fee is not None and self.fee > self.gross:
            raise ValidationError({"fee": "Use a fee no greater than gross earnings."})
        if self.order_url and not valid_source_url(self.order_url, self.source):
            raise ValidationError({"order_url": "Use an HTTPS link on the selected platform."})
