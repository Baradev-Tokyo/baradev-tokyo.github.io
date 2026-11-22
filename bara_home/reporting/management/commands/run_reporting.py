from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from reporting.database_recovery import RecoveryError, SupabaseProject, ensure_database_ready
from reporting.models import ReportDelivery, ReportRun
from reporting.scheduling import deliver, enqueue, generate, process, redact_expired


class Command(BaseCommand):
    help = "Enqueue due reports and drain bounded reporting and email batches."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--require-postgres", action="store_true")
        parser.add_argument("--schedule-at", help="Replay calendar evaluation at an ISO-8601 timestamp with offset.")

    def handle(self, *args, **options):
        limit = options["limit"]
        if options["require_postgres"] and connection.vendor != "postgresql":
            raise CommandError("Scheduled reporting requires PostgreSQL.")
        if not 1 <= limit <= 200:
            raise CommandError("--limit must be between 1 and 200.")
        now = timezone.now()
        stamp = options["schedule_at"]
        if stamp:
            try:
                scheduled = datetime.fromisoformat(stamp)
                if timezone.is_naive(scheduled) or scheduled > now:
                    raise ValueError
            except ValueError as exc:
                raise CommandError("--schedule-at must be a past timestamp with an offset.") from exc
        else:
            scheduled = now

        if connection.vendor == "postgresql":
            try:
                project = None
                if settings.BARA_SUPABASE_PROJECT_REF or settings.BARA_SUPABASE_AUTO_RESUME:
                    project = SupabaseProject(
                        settings.BARA_SUPABASE_PROJECT_REF, settings.BARA_SUPABASE_MANAGEMENT_TOKEN,
                    )
                resumed = ensure_database_ready(
                    connection, project, auto_resume=settings.BARA_SUPABASE_AUTO_RESUME,
                )
            except RecoveryError as exc:
                raise CommandError(f"bara_reporting_database_unavailable: {exc}") from None
            if resumed:
                self.stdout.write("Supabase project resumed and PostgreSQL is reachable.")
        queued = enqueue(scheduled)
        runs = process(ReportRun, generate, limit)
        deliveries = process(ReportDelivery, deliver, limit)
        artifacts, bodies = redact_expired(now)
        self.stdout.write(
            f"Enqueued {queued}; processed {runs} runs and {deliveries} deliveries; "
            f"redacted {artifacts} artifacts and {bodies} message bodies."
        )
