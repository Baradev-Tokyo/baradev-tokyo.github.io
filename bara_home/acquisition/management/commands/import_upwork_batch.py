import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from acquisition.models import Opportunity
from operations.models import Workspace


FIELDS = {
    "external_id", "title", "url", "description", "skills", "currency",
    "budget_low", "budget_high", "connects_required",
}


class Command(BaseCommand):
    help = "Import authorized Upwork results with a verified zero-Connects application cost."

    def add_arguments(self, parser):
        parser.add_argument("workspace", type=int)
        parser.add_argument("file", type=Path)

    def handle(self, *args, **options):
        try:
            workspace = Workspace.objects.get(pk=options["workspace"])
            with options["file"].open("rb") as source:
                data = source.read(1_048_577)
            if len(data) > 1_048_576:
                raise ValueError("File must be at most 1 MiB.")
            records = json.loads(data.decode("utf-8-sig"))
            if not isinstance(records, list) or len(records) > 100:
                raise ValueError("Expected an array of at most 100 jobs.")
            jobs = []
            for record in records:
                if not isinstance(record, dict) or record.keys() - FIELDS:
                    raise ValueError("Unexpected job fields.")
                job = Opportunity(organization=workspace, source=Opportunity.Source.UPWORK, **record)
                job.full_clean(validate_constraints=False)
                if type(record.get("connects_required")) is int and record["connects_required"] == 0:
                    jobs.append(job)
        except (OSError, ValueError, ValidationError, Workspace.DoesNotExist) as exc:
            raise CommandError("Use an existing workspace and valid normalized Upwork results.") from exc

        created_count = 0
        with transaction.atomic():
            for job in jobs:
                existing, created = Opportunity.objects.get_or_create(
                    organization=workspace, source=job.source, external_id=job.external_id,
                    defaults={field: getattr(job, field) for field in FIELDS - {"external_id"}},
                )
                if not created and existing.connects_required != 0:
                    Opportunity.objects.filter(pk=existing.pk).update(connects_required=0)
                created_count += created
        self.stdout.write(
            f"Imported {created_count}; preserved {len(jobs) - created_count} existing jobs; "
            f"skipped {len(records) - len(jobs)} with paid or unverified Connects costs."
        )
