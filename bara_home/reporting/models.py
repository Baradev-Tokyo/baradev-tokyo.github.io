import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from operations.models import Workspace


class CustomerContact(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    email = models.EmailField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.email


class VerifiedEmailRecipient(models.Model):
    contact = models.OneToOneField(CustomerContact, on_delete=models.PROTECT)
    address = models.EmailField()
    verified_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.contact_id and self.address != self.contact.email:
            raise ValidationError("Verified address must match the contact email exactly.")

    def __str__(self):
        return self.address


class ReportKind(models.TextChoices):
    HOSTING_USAGE = "hosting_usage", "Hosting usage"
    HOSTING_CHARGES = "hosting_charges", "Hosting charges"
    MARKETING = "marketing", "Marketing performance"
    SOCIAL = "social", "Social media performance"
    REVIEWS = "reviews", "Business Profile reviews"
    PAYMENT_REMINDER = "payment_reminder", "Payment reminder"
    MAINTENANCE = "maintenance", "Maintenance notice"
    SUSPENSION = "suspension", "Suspension notice"


class NotificationTemplate(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    kind = models.CharField(max_length=24, choices=ReportKind)
    language = models.CharField(max_length=2, choices=[("en", "English"), ("ja", "Japanese")])
    subject = models.CharField(max_length=180)
    introduction = models.TextField(blank=True, max_length=1200)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "kind", "language"], name="unique_report_template"),
        ]


class ReportConfiguration(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    recipients = models.ManyToManyField(VerifiedEmailRecipient, blank=True)
    kind = models.CharField(max_length=24, choices=ReportKind)
    frequency = models.CharField(max_length=7, choices=[("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")])
    timezone = models.CharField(max_length=64, default="Asia/Tokyo")
    language = models.CharField(max_length=2, choices=[("en", "English"), ("ja", "Japanese")], default="ja")
    delay_days = models.PositiveSmallIntegerField(default=2)
    starts_on = models.DateField()
    active = models.BooleanField(default=False)
    sample = models.BooleanField(default=True)
    include_pdf = models.BooleanField(default=False)
    allow_live = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.organization} / {self.get_kind_display()}"


class BillingPeriod(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    start = models.DateField()
    end = models.DateField()
    billing_currency = models.CharField(max_length=3, default="JPY")
    finalized = models.BooleanField(default=False)
    base_charge = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    discount = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    tax = models.DecimalField(max_digits=18, decimal_places=6, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "start", "end"], name="unique_billing_period"),
            models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="billing_period_positive"),
        ]


class CloudResourceOwnership(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    project_id = models.CharField(max_length=120)
    resource = models.CharField(max_length=255)
    starts_on = models.DateField()
    ends_before = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["project_id", "resource", "starts_on"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_before__isnull=True) | models.Q(ends_before__gt=models.F("starts_on")),
                name="resource_ownership_positive",
            ),
        ]


class UsageRecord(models.Model):
    period = models.ForeignKey(BillingPeriod, on_delete=models.PROTECT)
    ownership = models.ForeignKey(CloudResourceOwnership, on_delete=models.PROTECT)
    source_key = models.CharField(max_length=150)
    day = models.DateField()
    service = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)
    cost = models.DecimalField(max_digits=18, decimal_places=6)
    credits = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    estimated = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["period", "source_key"], name="unique_period_usage_source"),
        ]


class AvailabilityRecord(models.Model):
    period = models.ForeignKey(BillingPeriod, on_delete=models.PROTECT)
    ownership = models.ForeignKey(CloudResourceOwnership, on_delete=models.PROTECT)
    day = models.DateField()
    checks = models.PositiveIntegerField()
    successful_checks = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["period", "ownership", "day"], name="unique_day_availability"),
            models.CheckConstraint(condition=models.Q(successful_checks__lte=models.F("checks")),
                                   name="valid_availability_counts"),
        ]


class PaymentEvent(models.Model):
    """Current Stripe invoice snapshot, assigned to an explicit billing period."""

    period = models.ForeignKey(BillingPeriod, on_delete=models.PROTECT)
    stripe_invoice_id = models.CharField(max_length=100, unique=True)
    currency = models.CharField(max_length=3)
    invoiced_minor = models.PositiveBigIntegerField(default=0)
    collected_minor = models.PositiveBigIntegerField(default=0)
    outstanding_minor = models.PositiveBigIntegerField(default=0)
    synchronized_at = models.DateTimeField(null=True, blank=True)


class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    WORKING = "working", "Working"
    RETRY = "retry", "Retry scheduled"
    READY = "ready", "Report ready"
    FAILED = "failed", "Needs intervention"
    ACCEPTED = "accepted", "Accepted by provider"
    DELIVERED = "delivered", "Delivered"
    BOUNCED = "bounced", "Bounced"
    COMPLAINED = "complained", "Complaint"
    SIMULATED = "simulated", "Test delivery"


class Job(models.Model):
    status = models.CharField(max_length=12, choices=JobStatus, default=JobStatus.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    claim = models.UUIDField(null=True)
    error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["status", "next_attempt"])]


class ReportRun(Job):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    configuration = models.ForeignKey(ReportConfiguration, on_delete=models.PROTECT)
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(Job.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["configuration", "period_start", "period_end"], name="unique_configuration_run"
            ),
        ]


class ReportArtifact(models.Model):
    run = models.ForeignKey(ReportRun, on_delete=models.PROTECT)
    media_type = models.CharField(max_length=30)
    data = models.BinaryField(null=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "media_type"], name="unique_run_artifact_type"),
        ]


class ReportDelivery(Job):
    run = models.ForeignKey(ReportRun, on_delete=models.PROTECT)
    recipient = models.ForeignKey(VerifiedEmailRecipient, on_delete=models.PROTECT)
    message_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    address = models.EmailField()
    sender = models.EmailField()
    provider = models.CharField(max_length=12)
    subject = models.CharField(max_length=180)
    text = models.TextField()
    html = models.TextField()
    first_attempt_at = models.DateTimeField(null=True)
    provider_id = models.CharField(max_length=100, unique=True, null=True)
    expires_at = models.DateTimeField()

    class Meta(Job.Meta):
        constraints = [
            models.UniqueConstraint(fields=["run", "recipient"], name="unique_run_recipient"),
            models.UniqueConstraint(fields=["run", "address"], name="unique_run_address"),
        ]


class EmailDeliveryEvent(models.Model):
    delivery = models.ForeignKey(ReportDelivery, on_delete=models.PROTECT)
    provider_event_id = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=30)
    received_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    organization = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    kind = models.CharField(max_length=64)
    correlation = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
