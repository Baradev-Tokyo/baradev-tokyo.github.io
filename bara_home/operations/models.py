import uuid

from django.db import models


class Workspace(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.name


class BillingCustomer(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    label = models.CharField(max_length=120)
    stripe_id = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.label


class BillingOrder(models.Model):
    class Kind(models.TextChoices):
        SERVICE = "service", "One-time service"
        DEPOSIT = "deposit", "Deposit"
        MILESTONE = "milestone", "Milestone"
        MAINTENANCE = "maintenance", "Maintenance subscription"
        SAAS = "saas", "SaaS subscription"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(BillingCustomer, on_delete=models.PROTECT)
    kind = models.CharField(max_length=16, choices=Kind)
    stripe_price = models.CharField(max_length=100)
    attempt_started = models.DateTimeField(null=True, editable=False)
    session_id = models.CharField(max_length=100, unique=True, null=True, editable=False)
    checkout_url = models.URLField(max_length=2048, blank=True, editable=False)
    status = models.CharField(max_length=20, default="pending", editable=False)
    payment_intent_id = models.CharField(max_length=100, blank=True, editable=False)
    invoice_id = models.CharField(max_length=100, blank=True, editable=False)
    subscription_id = models.CharField(max_length=100, blank=True, editable=False)

    @property
    def mode(self):
        return "subscription" if self.kind in (self.Kind.MAINTENANCE, self.Kind.SAAS) else "payment"


class Subscription(models.Model):
    customer = models.ForeignKey(BillingCustomer, on_delete=models.PROTECT)
    stripe_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=30)
    cancel_at_period_end = models.BooleanField()


class Invoice(models.Model):
    customer = models.ForeignKey(BillingCustomer, on_delete=models.PROTECT)
    stripe_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=30)
    currency = models.CharField(max_length=3)
    amount_due = models.PositiveBigIntegerField()
    amount_paid = models.PositiveBigIntegerField()
    attempt_count = models.PositiveIntegerField()
    payment_failed = models.BooleanField(default=False)
    subscription_id = models.CharField(max_length=100, blank=True)


class StripeEvent(models.Model):
    stripe_id = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)
