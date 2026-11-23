from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from content_queue.replenish import replenish
from content_queue.services import MockPublisher, claim_due, dispatch, recover_interrupted
from operations.models import Workspace


class Command(BaseCommand):
    help = "Replenish the local queue and process due publications in mock mode."

    def add_arguments(self, parser):
        parser.add_argument("workspace", type=int)
        parser.add_argument("--mock-publish", action="store_true", help="Record simulated publications locally.")

    def handle(self, *args, **options):
        workspace = options["workspace"]
        if not Workspace.objects.filter(pk=workspace).exists():
            raise CommandError("Select an existing workspace.")
        now = timezone.now()
        self.stdout.write(f"Filled {replenish(workspace, now)} publication slot(s).")
        if options["mock_publish"]:
            recover_interrupted(workspace, now)
            publisher = MockPublisher()
            published = 0
            for _ in range(50):
                claim = claim_due(workspace, now)
                if claim is None:
                    break
                published += dispatch(workspace, *claim, publisher, now=now)
            self.stdout.write(f"Recorded {published} simulated publication(s).")
