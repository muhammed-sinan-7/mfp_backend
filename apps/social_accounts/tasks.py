# mfp_backend/apps/social/tasks.py

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.social_accounts.models import SocialAccount, SocialProvider
from apps.social_accounts.services.meta_sync_service import MetaSyncService
from apps.social_accounts.services.youtube import YouTubeOAuthService


@shared_task
def dispatch_expiring_meta_refresh_tasks():

    threshold = timezone.now() + timedelta(days=5)

    accounts = SocialAccount.objects.filter(
        provider=SocialProvider.META, is_active=True, token_expires_at__lte=threshold
    ).values_list("id", flat=True)

    for account_id in accounts:
        refresh_meta_account_task.delay(account_id)


@shared_task(bind=True, max_retries=3)
def refresh_meta_account_task(self, account_id: int):

    from apps.social_accounts.services.meta_token_service import MetaTokenService

    try:
        MetaTokenService.refresh_account(account_id)

    except Exception as exc:
        # Exponential backoff retry
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def sync_meta_pages_task(social_account_id):
    social_account = SocialAccount.objects.get(id=social_account_id)
    MetaSyncService.sync_pages(social_account)


@shared_task(bind=True, max_retries=3)
def refresh_youtube_account_task(self, account_id):

    account = SocialAccount.objects.filter(id=account_id).first()

    if not account:
        return

    if not account.refresh_token:
        return

    try:
        token_data = YouTubeOAuthService.refresh_access_token(account.refresh_token)

        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)

        account.access_token = access_token
        account.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        account.save()

    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def dispatch_expiring_youtube_refresh_tasks():

    threshold = timezone.now() + timedelta(minutes=30)

    accounts = SocialAccount.objects.filter(
        provider=SocialProvider.YOUTUBE, is_active=True, token_expires_at__lte=threshold
    ).values_list("id", flat=True)

    for account_id in accounts:
        refresh_youtube_account_task.delay(account_id)
