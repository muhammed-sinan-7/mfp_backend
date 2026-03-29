# mfp_backend/apps/social/services/meta_token_service.py

from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.social_accounts.models import SocialAccount


class MetaTokenService:

    GRAPH_BASE = "https://graph.facebook.com/v18.0"

    @staticmethod
    @transaction.atomic
    def refresh_account(account_id):

        account = SocialAccount.objects.select_for_update().get(id=account_id)

        if not account.is_active:
            return

        old_token = account.access_token

        refresh_url = f"{MetaTokenService.GRAPH_BASE}/oauth/access_token"

        params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "fb_exchange_token": old_token,
        }

        response = requests.get(refresh_url, params=params, timeout=10)

        if response.status_code != 200:
            MetaTokenService._handle_failure(account)
            return

        data = response.json()

        new_token = data.get("access_token")
        expires_in = data.get("expires_in")

        if not new_token:
            MetaTokenService._handle_failure(account)
            return

        account.access_token = new_token

        if expires_in:
            account.token_expires_at = timezone.now() + timedelta(
                seconds=int(expires_in)
            )
        else:

            account.token_expires_at = timezone.now() + timedelta(days=60)

        account.refresh_failed_count = 0

        account.save(
            update_fields=["access_token", "token_expires_at", "refresh_failed_count"]
        )

        MetaTokenService._refresh_page_tokens(account, new_token)

    @staticmethod
    def _refresh_page_tokens(account, user_token: str):

        url = f"{MetaTokenService.GRAPH_BASE}/me/accounts"

        response = requests.get(url, params={"access_token": user_token}, timeout=10)

        if response.status_code != 200:
            return

        pages = response.json().get("data", [])

        metadata = account.metadata or {}
        metadata["pages"] = pages

        account.metadata = metadata
        account.save(update_fields=["metadata"])

    @staticmethod
    def _handle_failure(account):

        account.refresh_failed_count += 1

        if account.refresh_failed_count >= 3:
            account.is_active = False

        account.save(update_fields=["refresh_failed_count", "is_active"])
