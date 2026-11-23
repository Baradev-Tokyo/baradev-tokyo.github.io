import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from operations.models import Workspace
from acquisition.models import Opportunity
from acquisition.providers import LlamaCppProvider
from acquisition.screening import RulesProvider

FIELDS = {
    "source", "external_id", "url", "title", "description", "skills", "currency", "budget_low", "budget_high",
    "provider_fee", "delivery_cost", "effort_hours", "target_hourly_rate", "scope_clarity",
    "repeatability", "recurring", "connects_required", "off_platform_requested",
}


class Command(BaseCommand):
    help = "Screen a locally supplied JSON opportunity. No marketplace requests."

    def add_arguments(self, parser):
        parser.add_argument("workspace", type=int)
        parser.add_argument("source_file", type=Path)
        parser.add_argument("--save", action="store_true")
        parser.add_argument("--local-model", type=Path, help="Use an existing GGUF with the local llama-cli.")
        parser.add_argument("--weights-file", type=Path)

    def handle(self, *args, **options):
        from acquisition.screening import Weights

        try:
            workspace = Workspace.objects.get(pk=options["workspace"])
            source = options["source_file"]
            if source.stat().st_size > 16384:
                raise ValueError
            payload = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) - FIELDS:
                raise ValueError
            item = Opportunity(organization=workspace, **payload)
            item.full_clean(validate_constraints=False)
            weights_file = options["weights_file"]
            if weights_file and weights_file.stat().st_size > 4096:
                raise ValueError
            rules = RulesProvider(Weights(**json.loads(weights_file.read_text(encoding="utf-8"))) if weights_file else None)
            provider = LlamaCppProvider(options["local_model"], rules) if options["local_model"] else rules
        except (Workspace.DoesNotExist, OSError, ValidationError, TypeError, ValueError) as exc:
            raise CommandError("Use an existing workspace and valid owner-entered opportunity fields.") from exc
        if options["save"]:
            try:
                with transaction.atomic():
                    _, created = Opportunity.objects.get_or_create(
                        organization=workspace, source=item.source, external_id=item.external_id,
                        defaults={field: getattr(item, field) for field in FIELDS - {"source", "external_id"}},
                    )
            except IntegrityError as exc:
                raise CommandError("Opportunity could not be stored.") from exc
            if not created:
                self.stderr.write("Already recorded. Stored fields were preserved.")
        self.stdout.write(json.dumps(provider.assess(item), ensure_ascii=False, indent=2))
