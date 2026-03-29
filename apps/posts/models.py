import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.organizations.models import Organization
from apps.social_accounts.models import PublishingTarget

# Create your models here.

User = get_user_model()


class PostContentType(models.TextChoices):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    MIXED = "MIXED"


class PostStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    PROCESSING = "processing", "Processing"
    PARTIALLY_PUBLISHED = "partially_published", "Partially Published"
    PUBLISHED = "published", "Published"
    FAILED = "failed", "Failed"


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="posts",
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_posts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization"]),
        ]

    def __str__(self):
        return str(self.id)


class PlatformType(models.TextChoices):
    LINKEDIN = "linkedin", "LinkedIn"
    INSTAGRAM = "instagram", "Instagram"
    YOUTUBE = "youtube", "YouTube"


class PublishStatus(models.TextChoices):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class PostPlatform(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="platforms",
        db_index=True,
    )

    publishing_target = models.ForeignKey(
        PublishingTarget,
        on_delete=models.CASCADE,
        related_name="post_platforms",
    )

    caption = models.TextField(blank=True)

    scheduled_time = models.DateTimeField(db_index=True)

    publish_status = models.CharField(
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.PENDING,
        db_index=True,
    )

    external_post_id = models.CharField(max_length=255, blank=True, null=True)

    failure_reason = models.TextField(blank=True, null=True)

    retry_count = models.PositiveSmallIntegerField(default=0)

    last_attempt_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "publishing_target")
        indexes = [
            models.Index(fields=["publish_status", "scheduled_time"]),
        ]

    def clean(self):
        if (
            self.post.organization_id
            != self.publishing_target.social_account.organization_id
        ):
            raise ValidationError(
                "Post and PublishingTarget must belong to same organization"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.post_id} - {self.publishing_target_id}"


class MediaType(models.TextChoices):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class PostPlatformMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    post_platform = models.ForeignKey(
        PostPlatform,
        on_delete=models.CASCADE,
        related_name="media",
        db_index=True,
    )

    file = models.FileField(upload_to="post_media/")

    media_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
    )

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        indexes = [
            models.Index(fields=["post_platform", "media_type"]),
        ]

    def clean(self):

        provider = self.post_platform.publishing_target.provider

        existing_types = set(
            self.post_platform.media.exclude(id=self.id).values_list(
                "media_type", flat=True
            )
        )
        total_media = self.post_platform.media.exclude(id=self.id).count()

        if provider == "instagram" and total_media >= 10:
            raise ValidationError("Instagram max 10 media items.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
