from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.posts.models import PostPlatform, PublishStatus


class Command(BaseCommand):
    help = "Reset stuck PROCESSING posts (older than 15 min) to FAILED"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=15)

        stuck = PostPlatform.objects.filter(
            publish_status=PublishStatus.PROCESSING,
            last_attempt_at__lt=cutoff,
        )

        count = stuck.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No stuck posts found."))
            return

        stuck.update(
            publish_status=PublishStatus.FAILED,
            failure_reason="Stuck in processing — manually reset by fix_stuck_processing command",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Reset {count} stuck PROCESSING post(s) to FAILED."
            )
        )
