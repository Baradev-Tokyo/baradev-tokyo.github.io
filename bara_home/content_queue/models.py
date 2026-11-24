import uuid

from django.conf import settings
from django.db import models

from operations.models import Workspace


class Platform(models.TextChoices):
    BLOG = "blog", "Blog"
    INSTAGRAM = "instagram", "Instagram"
    X = "x", "X"
    FACEBOOK = "facebook", "Facebook"
    TIKTOK = "tiktok", "TikTok"
    YOUTUBE = "youtube", "YouTube"
    LINKEDIN = "linkedin", "LinkedIn"


class State(models.TextChoices):
    DRAFT = "draft", "Draft"
    VALIDATED = "validated", "Validated"
    NEEDS_APPROVAL = "needs_approval", "Needs approval"
    QUEUED = "queued", "Queued"
    PUBLISHING = "publishing", "Publishing"
    PUBLISHED = "published", "Published"
    CANCELLED = "cancelled", "Cancelled"
    FAILED = "failed", "Failed"


class AutomationPolicy(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.PROTECT)
    enabled = models.BooleanField(default=False)
    horizon_days = models.PositiveSmallIntegerField(default=14)
    generation_enabled = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=0, editable=False)


class ChannelSettings(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    platform = models.CharField(max_length=12, choices=Platform)
    paused = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "platform"], name="content_unique_channel")]


class ContentDraft(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    platform = models.CharField(max_length=12, choices=Platform)
    category = models.CharField(max_length=60)
    text = models.TextField()
    media = models.CharField(max_length=150, blank=True)
    media_bytes = models.BinaryField(default=bytes, blank=True)
    state = models.CharField(max_length=16, choices=State, default=State.DRAFT)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text.splitlines()[0][:90] if self.text else str(self.pk)


class ContentPoolEntry(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    url = models.URLField(max_length=1000)
    note = models.TextField(max_length=2000, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "url"], name="content_pool_unique_link")]


class PublicationJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    campaign = models.UUIDField(default=uuid.uuid4, db_index=True)
    draft = models.ForeignKey(ContentDraft, on_delete=models.PROTECT)
    platform = models.CharField(max_length=12, choices=Platform)
    scheduled_at = models.DateTimeField()
    state = models.CharField(max_length=16, choices=State, default=State.QUEUED)
    replace_requested = models.BooleanField(default=False)
    retry_at = models.DateTimeField(null=True)
    dispatch_started = models.BooleanField(default=False)
    external_reference = models.CharField(max_length=150, blank=True)
    last_error = models.CharField(max_length=200, blank=True)

    class Meta:
        indexes = [models.Index(fields=["workspace", "state", "scheduled_at"])]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "platform", "scheduled_at"],
                condition=~models.Q(state=State.CANCELLED), name="content_unique_active_slot"),
            models.UniqueConstraint(fields=["draft"], condition=~models.Q(state=State.CANCELLED),
                name="content_unique_active_draft"),
        ]


class PublicationRevision(models.Model):
    job = models.ForeignKey(PublicationJob, on_delete=models.PROTECT, related_name="history")
    draft = models.ForeignKey(ContentDraft, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=36)
    scheduled_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class PublishingAttempt(models.Model):
    job = models.ForeignKey(PublicationJob, on_delete=models.PROTECT, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    outcome = models.CharField(max_length=30, default="dispatching")


class QueueAudit(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
