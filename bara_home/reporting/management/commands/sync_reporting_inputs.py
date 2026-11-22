from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from operations.models import BillingCustomer
from operations.stripe_gateway import InvalidEvent, StripeError, StripeGateway
from reporting.integrations import (
    BigQueryBillingSource, import_availability, import_cloud_costs, read_uptime, sync_verified_stripe_invoice,
)
from reporting.models import BillingPeriod, CloudResourceOwnership, PaymentEvent


class Command(BaseCommand):
    help = "Import approved cloud inputs or reconcile a mapped Stripe test invoice."

    def add_arguments(self, parser):
        parser.add_argument("period_id", type=int)
        parser.add_argument("--billing-view")
        parser.add_argument("--finalized-costs", action="store_true")
        parser.add_argument("--ownership-id", type=int)
        parser.add_argument("--uptime-check")
        parser.add_argument("--timezone", default="Asia/Tokyo")
        parser.add_argument("--stripe-invoice")

    def handle(self, *args, **options):
        try:
            period = BillingPeriod.objects.get(pk=options["period_id"])
        except BillingPeriod.DoesNotExist as exc:
            raise CommandError("Unknown reporting period.") from exc

        ownership = CloudResourceOwnership.objects.filter(
            organization=period.organization, starts_on__lt=period.end,
        ).exclude(ends_before__lte=period.start)
        sources = sum(bool(options[name]) for name in ("billing_view", "uptime_check", "stripe_invoice"))
        if sources != 1:
            raise CommandError("Choose exactly one reporting input.")
        if options["billing_view"] and not options["ownership_id"]:
            self.import_billing(period, ownership, options)
        elif options["uptime_check"] and options["ownership_id"]:
            self.import_uptime(period, ownership, options)
        elif options["stripe_invoice"] and not options["ownership_id"]:
            self.sync_invoice(period, options["stripe_invoice"])
        else:
            raise CommandError("Supply an approved ownership ID only for the uptime check.")

    def sync_invoice(self, period, invoice_id):
        if not settings.BARA_STRIPE_SANDBOX_ENABLED:
            raise CommandError("Stripe sandbox is disabled.")
        if not PaymentEvent.objects.filter(period=period, stripe_invoice_id=invoice_id).exists():
            raise CommandError("Invoice is not mapped to this exact reporting period.")
        try:
            invoice = StripeGateway().retrieve("invoices", invoice_id)
        except (InvalidEvent, StripeError) as exc:
            raise CommandError("Unable to read the Stripe test invoice.") from exc
        if invoice.get("id") != invoice_id or not BillingCustomer.objects.filter(
            workspace=period.organization, stripe_id=invoice.get("customer"),
        ).exists():
            raise CommandError("Invoice is outside this reporting workspace.")
        if not sync_verified_stripe_invoice(period.organization_id, invoice):
            raise CommandError("Stripe returned an unsupported or mismatched invoice.")
        self.stdout.write("Synchronized the mapped Stripe test invoice.")

    def import_billing(self, period, ownership, options):
        from google.cloud import bigquery

        projects = tuple(sorted(set(ownership.values_list("project_id", flat=True))))
        if not projects:
            raise CommandError("The period has no owned projects.")
        source = BigQueryBillingSource(bigquery.Client(), options["billing_view"])
        rows = list(source.rows(period.start, period.end, projects))
        self.stdout.write(f"Imported {import_cloud_costs(period, rows, estimated=not options['finalized_costs'])} cost rows.")

    def import_uptime(self, period, ownership, options):
        from google.cloud.monitoring_v3 import MetricServiceClient

        resource = ownership.filter(pk=options["ownership_id"]).first()
        if not resource:
            raise CommandError("The resource is outside this organization's period.")
        samples = read_uptime(
            MetricServiceClient(), resource.project_id, options["uptime_check"], resource.resource,
            period.start, period.end, options["timezone"],
        )
        self.stdout.write(f"Imported {import_availability(period, samples)} availability rows.")
