import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.posts.models import PostPlatform, PublishStatus

from .models import PostPlatformAnalyticsSnapshot
from .services.registry import FETCHERS
from .services.sync import save_metrics

logger = logging.getLogger(__name__)


@shared_task
def sync_post_analytics():

    posts = (
        PostPlatform.objects.filter(
            publish_status=PublishStatus.SUCCESS, external_post_id__isnull=False
        )
        .select_related("publishing_target", "publishing_target__social_account")
        .only(
            "id",
            "external_post_id",
            "publish_status",
            "publishing_target__id",
            "publishing_target__provider",
            "publishing_target__social_account__id",
        )
    )

    for post in posts.iterator(chunk_size=200):

        provider = post.publishing_target.provider

        fetcher = FETCHERS.get(provider)

        if not fetcher:

            continue

        try:
            metrics = fetcher(post)

            if not metrics:

                continue

            save_metrics(post, metrics)

        except Exception as e:
            logger.error(f"Analytics sync error for {provider}: {e}")


@shared_task
def cleanup_old_analytics_snapshots():
    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = PostPlatformAnalyticsSnapshot.objects.filter(
        captured_at__lt=cutoff
    ).delete()
    logger.info("[ANALYTICS CLEANUP] Deleted %s stale snapshots", deleted_count)
    return deleted_count
