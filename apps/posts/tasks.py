import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Post, PostPlatform, PublishStatus
from .services import get_publisher

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


@shared_task(bind=True, max_retries=3)
def publish_platform(self, platform_id):
    try:
        # --- LOCK & INITIAL STATE ---
        with transaction.atomic():
            platform = (
                PostPlatform.objects.select_for_update()
                .select_related(
                    "publishing_target",
                    "publishing_target__social_account",
                    "post",
                )
                .get(id=platform_id)
            )

            # Idempotency guard
            if platform.publish_status == PublishStatus.SUCCESS:
                logger.info(f"[SKIP] Already published: {platform_id}")
                return

            platform.publish_status = PublishStatus.PROCESSING
            platform.last_attempt_at = timezone.now()
            platform.save(update_fields=["publish_status", "last_attempt_at"])

        account = platform.publishing_target.social_account

        # --- TOKEN VALIDATION ---
        if account.is_token_expired():
            with transaction.atomic():
                platform = PostPlatform.objects.select_for_update().get(id=platform_id)
                platform.publish_status = PublishStatus.FAILED
                platform.failure_reason = "Token expired"
                platform.save(update_fields=["publish_status", "failure_reason"])

            logger.warning(f"[TOKEN EXPIRED] {platform_id}")
            return

        # --- PUBLISH ---
        publisher = get_publisher(platform.publishing_target.provider)
        result = publisher.publish(platform)

        # --- SUCCESS SAVE ---
        with transaction.atomic():
            platform = PostPlatform.objects.select_for_update().get(id=platform_id)

            # Double-check idempotency
            if platform.publish_status == PublishStatus.SUCCESS:
                return

            platform.external_post_id = result.get("external_id")
            platform.publish_status = PublishStatus.SUCCESS
            platform.failure_reason = None
            platform.save(
                update_fields=["external_post_id", "publish_status", "failure_reason"]
            )

        logger.info(f"[SUCCESS] Platform published: {platform_id}")

    except Exception as e:
        logger.error(f"[ERROR] Platform {platform_id}: {str(e)}")

        with transaction.atomic():
            platform = PostPlatform.objects.select_for_update().get(id=platform_id)

            platform.retry_count += 1
            platform.failure_reason = str(e)

            if platform.retry_count >= 3:
                # All retries exhausted — mark as FAILED permanently
                platform.publish_status = PublishStatus.FAILED
                platform.save(
                    update_fields=[
                        "publish_status",
                        "retry_count",
                        "failure_reason",
                    ]
                )
                logger.error(f"[FAILED] Platform {platform_id} exhausted all retries.")
                return  # Do NOT raise so Celery doesn't retry again
            else:
                platform.publish_status = PublishStatus.PROCESSING
                platform.save(
                    update_fields=[
                        "publish_status",
                        "retry_count",
                        "failure_reason",
                    ]
                )

        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def dispatch_scheduled_platforms():
    now = timezone.now()

    with transaction.atomic():
        platforms = (
            PostPlatform.objects.select_for_update(skip_locked=True)
            .filter(
                Q(publish_status=PublishStatus.PENDING)
                | Q(
                    publish_status=PublishStatus.PROCESSING,
                    last_attempt_at__lt=now - timedelta(minutes=10),
                ),
                scheduled_time__lte=now,
                post__is_deleted=False,
            )
            .order_by("scheduled_time")[:BATCH_SIZE]
        )

        platform_ids = list(platforms.values_list("id", flat=True))

        # Claim via timestamp (lightweight lock)
        PostPlatform.objects.filter(id__in=platform_ids).update(
            last_attempt_at=timezone.now()
        )

    for pid in platform_ids:
        publish_platform.delay(str(pid))


@shared_task
def purge_recycle_bin():
    threshold = timezone.now() - timedelta(days=30)

    posts = Post.objects.filter(is_deleted=True, deleted_at__lt=threshold)

    count = posts.count()
    posts.delete()

    logger.info(f"[CLEANUP] Deleted {count} posts")

    return f"{count} posts permanently deleted"
