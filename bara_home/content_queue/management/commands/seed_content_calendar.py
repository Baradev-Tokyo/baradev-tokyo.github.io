from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from content_queue.models import ChannelSettings, Platform, State
from content_queue.services import TOKYO, _enqueue, save_draft, workspace_lock
from operations.models import Workspace


SAMPLES = (
    ("Web design", "A landing page should give visitors one clear next step. Decide what it is before making the first wireframe."),
    ("Booking", "Build the booking rules around capacity. A one-to-one consultation and a cycling tour need different availability checks."),
    ("Payments", "When taking deposits online, explain the balance, deadlines, and refund terms before checkout."),
    ("Operations", "A spreadsheet becomes a bottleneck when staff repeatedly wait for the same person to update it. Map the handoff before building an app."),
    ("Bilingual websites", "Plan text delivery for both languages before layout approval. Headings and buttons rarely occupy the same space in Japanese and English."),
    ("Automation", "A good automated email tells the recipient what happened, what they need to do, and how to reach a real person."),
    ("Analytics", "For a consultation site, distinguish someone viewing the booking page from someone actually reserving a time."),
    ("Web design", "Ask what photography is available before choosing a visual direction. The best layout depends on the real material it will carry."),
    ("Booking", "Document cancellation rules and send them in the booking confirmation so customers can find them later."),
    ("Payments", "Test a failed payment and a cancelled checkout. Both paths should tell a customer what to do next."),
    ("Operations", "A shift scheduling tool should capture who requested a change, who approved it, and when the change takes effect."),
    ("Bilingual websites", "Give each translated page its own URL so visitors can share the right language directly."),
    ("Automation", "Identify which steps should stop for human review. A useful automation makes exceptions easier to spot."),
    ("Analytics", "Campaign links can identify which channels bring visitors to a service page. Keep the labels consistent across posts."),
)


class Command(BaseCommand):
    help = "Populate a separate demo workspace with 14 future mock publications."

    def handle(self, *args, **options):
        owner = get_user_model().objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
        if owner is None:
            raise CommandError("Create an owner account before seeding the sample calendar.")
        workspace, created = Workspace.objects.get_or_create(name="Bara Content Calendar Demo")
        if not created and workspace.publicationjob_set.exists():
            self.stdout.write(f"Demo workspace {workspace.pk} already has sample publications.")
            return
        start = timezone.localdate(timezone=TOKYO) + timedelta(days=1)
        with workspace_lock(workspace.pk):
            if workspace.publicationjob_set.exists():
                return
            for platform in Platform.values:
                ChannelSettings.objects.get_or_create(workspace=workspace, platform=platform)
            for index, (category, text) in enumerate(SAMPLES):
                platform = Platform.values[index % len(Platform.values)]
                media = "bara/joey.jpg" if platform == Platform.INSTAGRAM else ""
                draft = save_draft(workspace.pk, platform, category, text, media)
                draft.state = State.VALIDATED
                draft.approved_by = owner
                draft.save(update_fields=["state", "approved_by"])
                _enqueue(draft, datetime.combine(start + timedelta(days=index), time(10), TOKYO))
        self.stdout.write(f"Seeded 14 sample publications in demo workspace {workspace.pk}. Channels are paused.")
