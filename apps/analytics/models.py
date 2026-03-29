import uuid

from django.db import models

from apps.posts.models import PostPlatform


class PostPlatformAnalytics(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    post_platform = models.OneToOneField(
        PostPlatform, on_delete=models.CASCADE, related_name="analytics"
    )

    impressions = models.PositiveIntegerField(default=0)
    reach = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)

    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    saves = models.PositiveIntegerField(default=0)

    watch_time = models.BigIntegerField(default=0)
    traffic_sources = models.JSONField(default=list)
    engagement_rate = models.FloatField(default=0)

    last_synced_at = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_engagement(self):

        base = self.impressions if self.impressions > 0 else self.views

        if base == 0:
            self.engagement_rate = 0
            return

        engagement = self.likes + self.comments + self.shares

        self.engagement_rate = (engagement / base) * 100

    def save(self, *args, **kwargs):
        self.calculate_engagement()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["post_platform"]),
        ]


class PostPlatformAnalyticsSnapshot(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    post_platform = models.ForeignKey(
        PostPlatform, on_delete=models.CASCADE, related_name="analytics_snapshots"
    )

    impressions = models.PositiveIntegerField(default=0)
    reach = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)

    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    saves = models.PositiveIntegerField(default=0)

    watch_time = models.BigIntegerField(default=0)

    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["post_platform", "captured_at"]),
            models.Index(fields=["captured_at"]),
            models.Index(fields=["post_platform", "captured_at", "views"]),
        ]
