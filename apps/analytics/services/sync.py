from datetime import timedelta

from django.utils import timezone

from apps.analytics.models import PostPlatformAnalytics, PostPlatformAnalyticsSnapshot


def save_metrics(post_platform, metrics):
    # Avoid storing duplicate snapshots on every sync run.
    latest = (
        PostPlatformAnalyticsSnapshot.objects.filter(post_platform=post_platform)
        .order_by("-captured_at")
        .first()
    )
    now = timezone.now()
    min_snapshot_interval = timedelta(minutes=15)

    should_create_snapshot = True
    if latest:
        unchanged = (
            latest.impressions == metrics["impressions"]
            and latest.reach == metrics["reach"]
            and latest.views == metrics["views"]
            and latest.likes == metrics["likes"]
            and latest.comments == metrics["comments"]
            and latest.shares == metrics["shares"]
            and latest.saves == metrics["saves"]
            and latest.watch_time == metrics["watch_time"]
        )
        too_soon = (now - latest.captured_at) < min_snapshot_interval

        if unchanged and too_soon:
            should_create_snapshot = False

    if should_create_snapshot:
        PostPlatformAnalyticsSnapshot.objects.create(
            post_platform=post_platform,
            impressions=metrics["impressions"],
            reach=metrics["reach"],
            views=metrics["views"],
            likes=metrics["likes"],
            comments=metrics["comments"],
            shares=metrics["shares"],
            saves=metrics["saves"],
            watch_time=metrics["watch_time"],
        )

    PostPlatformAnalytics.objects.update_or_create(
        post_platform=post_platform, defaults=metrics
    )
