import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import OrganizationContextMixin
from apps.social_accounts.models import (
    MetaPage,
    PublishingTarget,
    SocialAccount,
    SocialProvider,
)
from apps.social_accounts.services.linkedin import LinkedInOAuthService, LinkedInService
from apps.social_accounts.services.meta_sync_service import MetaSyncService
from apps.social_accounts.services.youtube import YouTubeOAuthService

from ..services.meta import MetaOAuthService
from ..tasks import sync_meta_pages_task
from .serializers import PublishingTargetSerializer, SocialAccountSerializer

logger = logging.getLogger(__name__)


class MetaConnectView(OrganizationContextMixin, APIView):
    permission_classes = [AllowAny]

    def generate_state(self, user_id, org_id):
        payload = {
            "user_id": str(user_id),
            "org_id": str(org_id),
            "timestamp": int(time.time()),
        }

        payload_bytes = json.dumps(payload).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode()

        signature = hmac.new(
            settings.META_STATE_SECRET.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()

        return f"{payload_b64}.{signature}"

    def get(self, request):
        organization = request.organization

        if not organization:
            return Response({"error": "Organization not found"}, status=400)

        org_id = organization.id

        state = self.generate_state(request.user.id, org_id)

        params = {
            "client_id": settings.META_APP_ID,
            "redirect_uri": settings.META_REDIRECT_URI,
            "state": state,
            "scope": ",".join(
                [
                    "pages_show_list",
                    "pages_read_engagement",
                    "instagram_basic",
                    "instagram_content_publish",
                ]
            ),
            "response_type": "code",
        }

        auth_url = "https://www.facebook.com/v18.0/dialog/oauth?" + urlencode(params)

        return Response({"authorization_url": auth_url})


class MetaCallbackView(APIView):
    permission_classes = [AllowAny]

    def verify_state(self, state):
        try:
            payload_b64, signature = state.split(".")

            expected_signature = hmac.new(
                settings.META_STATE_SECRET.encode(),
                payload_b64.encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return None

            payload_json = base64.urlsafe_b64decode(payload_b64.encode())
            payload = json.loads(payload_json)

            if time.time() - payload["timestamp"] > 600:
                return None

            return payload

        except Exception:
            return None

    def get(self, request):

        code = request.GET.get("code")
        state = request.GET.get("state")

        if not code or not state:
            return Response({"error": "Missing code or state"}, status=400)

        payload = self.verify_state(state)
        if not payload:
            return Response({"error": "Invalid state"}, status=400)

        service = MetaOAuthService()

        token_data = service.exchange_code(code)
        if "access_token" not in token_data:
            return Response(token_data, status=400)

        short_token = token_data["access_token"]

        long_token_data = service.get_long_lived_token(short_token)
        if "access_token" not in long_token_data:
            return Response(long_token_data, status=400)

        long_token = long_token_data["access_token"]

        expires_in = long_token_data.get("expires_in", 60 * 24 * 60 * 60)
        expires_at = timezone.now() + timedelta(seconds=expires_in)

        profile = service.fetch_user_profile(long_token)

        meta_user_id = profile["id"]
        meta_user_name = profile.get("name", "Meta Account")

        social_account, _ = SocialAccount.objects.update_or_create(
            organization_id=payload["org_id"],
            provider=SocialProvider.META,
            external_id=meta_user_id,
            defaults={
                "account_name": meta_user_name,
                "access_token": long_token,
                "token_expires_at": expires_at,
                "scopes": service.SCOPES,
                "is_active": True,
            },
        )

        # Run one synchronous sync to avoid "connected account not visible until reload" UX.
        try:
            MetaSyncService.sync_pages(social_account)
        except Exception as exc:
            logger.warning("Immediate Meta sync failed for account %s: %s", social_account.id, str(exc))

        # Keep async sync for eventual consistency and retries.
        sync_meta_pages_task.delay(social_account.id)

        return redirect(f"{settings.FRONTEND_SUCCESS_URL}/accounts")


class MetaPageSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        social_account = SocialAccount.objects.get(
            organization=request.user.organization,
            provider=SocialProvider.META,
            is_active=True,
        )

        sync_meta_pages_task.delay(social_account.id)
        return Response({"message": "Sync started"})


class LinkedInConnectView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        organization = request.organization

        if not organization:
            return Response(
                {"error": "Organization not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        auth_url = LinkedInOAuthService.generate_authorization_url(
            organization_id=organization.id
        )

        return Response({"authorization_url": auth_url})


class LinkedInCallbackView(OrganizationContextMixin, APIView):

    def get(self, request):

        code = request.GET.get("code")
        state = request.GET.get("state")

        if not code or not state:
            return Response(
                {"error": "Missing code or state"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:

            org_id = LinkedInOAuthService.validate_state(state)

            token_data = LinkedInOAuthService.exchange_code(code)

            profile_data = LinkedInOAuthService.fetch_profile(
                token_data.get("access_token")
            )

            LinkedInOAuthService.save_account(
                org_id=org_id, token_data=token_data, profile_data=profile_data
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return redirect(f"{settings.FRONTEND_SUCCESS_URL}/accounts")


class SocialAccountListView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = request.organization

        accounts = SocialAccount.objects.filter(
            organization=organization, is_active=True
        )

        serializer = SocialAccountSerializer(accounts, many=True)

        return Response(serializer.data)


class YouTubeConnectView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        if not request.organization:
            return Response({"error": "Organization not found"}, status=400)

        auth_url = YouTubeOAuthService.generate_authorization_url(
            request.organization.id
        )

        return Response({"authorization_url": auth_url})


class YouTubeCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):

        code = request.GET.get("code")
        state = request.GET.get("state")

        if not code or not state:
            return Response({"error": "Missing code or state"}, status=400)

        org_id = YouTubeOAuthService.validate_state(state)

        token_data = YouTubeOAuthService.exchange_code(code)

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        channel_data = YouTubeOAuthService.fetch_channel(access_token)

        if not channel_data.get("items"):
            return Response({"error": "No YouTube channel found"}, status=400)

        channel = channel_data["items"][0]

        external_id = channel["id"]
        channel_name = channel["snippet"]["title"]
        scopes = token_data.get("scope", "").split(" ")
        social_account, _ = SocialAccount.objects.update_or_create(
            organization_id=org_id,
            provider=SocialProvider.YOUTUBE,
            external_id=external_id,
            defaults={
                "account_name": channel_name,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": timezone.now() + timedelta(seconds=expires_in),
                "is_active": True,
                "scopes": scopes,
            },
        )

        PublishingTarget.objects.update_or_create(
            social_account=social_account,
            provider=SocialProvider.YOUTUBE,
            resource_id=external_id,
            defaults={
                "display_name": channel_name,
                "metadata": channel,
                "is_active": True,
            },
        )

        return redirect(f"{settings.FRONTEND_SUCCESS_URL}/accounts")


class PublishingTargetListAPIView(OrganizationContextMixin, ListAPIView):
    serializer_class = PublishingTargetSerializer
    pagination_class = None

    def get_queryset(self):
        return PublishingTarget.objects.filter(
            social_account__organization=self.request.organization,
            is_active=True,
            provider__in=[
                SocialProvider.INSTAGRAM,
                SocialProvider.LINKEDIN,
                SocialProvider.YOUTUBE,
            ],
        ).order_by("-id")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        has_instagram = queryset.filter(provider=SocialProvider.INSTAGRAM).exists()
        if not has_instagram:
            meta_accounts = SocialAccount.objects.filter(
                organization=request.organization,
                provider=SocialProvider.META,
                is_active=True,
            ).only("id", "access_token")

            for account in meta_accounts:
                try:
                    MetaSyncService.sync_pages(account)
                except Exception as exc:
                    logger.warning(
                        "Auto-sync before publishing-targets failed for account %s: %s",
                        account.id,
                        str(exc),
                    )

            # DB-level recovery: if Meta pages already have IG business IDs,
            # recreate missing Instagram publishing targets without calling Graph.
            meta_pages = (
                MetaPage.objects.filter(
                    social_account__organization=request.organization,
                    social_account__is_active=True,
                    instagram_business_id__isnull=False,
                )
                .exclude(instagram_business_id="")
                .select_related("social_account")
            )
            for page in meta_pages:
                try:
                    PublishingTarget.objects.update_or_create(
                        social_account=page.social_account,
                        provider=SocialProvider.INSTAGRAM,
                        resource_id=page.instagram_business_id,
                        defaults={
                            "display_name": page.name or f"instagram-{page.instagram_business_id}",
                            "metadata": {
                                "id": page.instagram_business_id,
                                "source": "metapage-fallback",
                            },
                            "is_active": True,
                        },
                    )
                except Exception as exc:
                    logger.warning(
                        "Instagram fallback target upsert failed for MetaPage %s: %s",
                        page.id,
                        str(exc),
                    )

            # Legacy-data recovery: infer IG business IDs from Meta target metadata.
            meta_targets = PublishingTarget.objects.filter(
                social_account__organization=request.organization,
                social_account__is_active=True,
                provider=SocialProvider.META,
                is_active=True,
            ).select_related("social_account")
            for target in meta_targets:
                metadata = target.metadata or {}
                ig_data = metadata.get("instagram_business_account") or {}
                ig_id = ig_data.get("id")
                if not ig_id:
                    continue
                try:
                    PublishingTarget.objects.update_or_create(
                        social_account=target.social_account,
                        provider=SocialProvider.INSTAGRAM,
                        resource_id=ig_id,
                        defaults={
                            "display_name": metadata.get("name")
                            or target.display_name
                            or f"instagram-{ig_id}",
                            "metadata": {
                                "id": ig_id,
                                "source": "meta-target-fallback",
                            },
                            "is_active": True,
                        },
                    )
                except Exception as exc:
                    logger.warning(
                        "Instagram fallback from Meta target failed for target %s: %s",
                        target.id,
                        str(exc),
                    )

            queryset = self.get_queryset()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SocialAccountRefreshView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, account_id):
        from apps.social_accounts.tasks import (
            refresh_meta_account_task,
            refresh_youtube_account_task,
            sync_meta_pages_task,
        )

        account = SocialAccount.objects.filter(
            id=account_id,
            organization=request.organization,
        ).first()

        if not account:
            return Response({"error": "Account not found"}, status=404)

        if account.provider == SocialProvider.META:
            refresh_meta_account_task.delay(account.id)
            sync_meta_pages_task.delay(account.id)
        elif account.provider == SocialProvider.YOUTUBE:
            refresh_youtube_account_task.delay(account.id)
        elif account.provider == SocialProvider.LINKEDIN:
            # LinkedIn doesn't support token refresh in current flow; keep UX consistent.
            return Response({"message": "LinkedIn account is active. No refresh required."})
        else:
            return Response({"error": "Unsupported provider for refresh"}, status=400)

        return Response({"message": "Refresh triggered"})


class SocialAccountDisconnectView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, account_id):

        account = SocialAccount.objects.filter(
            id=account_id,
            organization=request.organization,
        ).first()

        if not account:
            return Response({"error": "Account not found"}, status=404)

        account.is_active = False
        account.save(update_fields=["is_active"])

        account.publishing_targets.update(is_active=False)

        return Response({"message": "Account disconnected"})
