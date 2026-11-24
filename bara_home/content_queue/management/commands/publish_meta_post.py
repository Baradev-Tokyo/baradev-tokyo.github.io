import os
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from content_queue.meta_publishing import MetaPublisher
from content_queue.models import Platform, PublicationJob
from content_queue.services import claim_due, dispatch

TOKENS = {
    Platform.FACEBOOK: "BARA_FACEBOOK_PAGE_ACCESS_TOKEN",
    Platform.INSTAGRAM: "BARA_INSTAGRAM_ACCESS_TOKEN",
}


class Command(BaseCommand):
    help = "Send one explicitly confirmed, approved and due publication to Meta."

    def add_arguments(self, parser):
        parser.add_argument("channel", choices=TOKENS)
        parser.add_argument("job", type=UUID)
        parser.add_argument("--confirm-draft", type=int, required=True)

    def handle(self, *args, **options):
        channel = options["channel"]
        token = os.getenv(TOKENS[channel], "")
        if not token:
            raise CommandError("Load the verified local Meta credential before publishing.")
        job = PublicationJob.objects.select_related("workspace", "draft").filter(
            pk=options["job"], workspace__name="Bara Development", platform=channel,
            draft_id=options["confirm_draft"],
        ).first()
        if job is None:
            raise CommandError("Choose the exact approved job and draft from the Bara Development workspace.")
        publisher = MetaPublisher(channel, token)
        try:
            publisher.check(job)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise CommandError("Meta preflight failed. Check the account, permissions and approved media.") from None
        claim = claim_due(job.workspace_id, timezone.now(), job_id=job.pk, draft_id=job.draft_id)
        if claim is None:
            raise CommandError("The selected post is not due, has changed, is paused or is already claimed.")
        if not dispatch(job.workspace_id, *claim, publisher):
            raise CommandError("Publication did not confirm. Review its status in the calendar.")
        job.refresh_from_db()
        self.stdout.write(f"Published on {channel}. Meta reference: {job.external_reference}")
