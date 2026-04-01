import secrets
import urllib.parse
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.mixins import OrganizationContextMixin
from apps.social_accounts.models import PublishingTarget, SocialAccount, SocialProvider


class YouTubeOAuthService:

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    YT_API_BASE = "https://www.googleapis.com/youtube/v3"

    STATE_TTL = 600

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ]

    @staticmethod
    def generate_authorization_url(organization_id):

        state = secrets.token_urlsafe(32)

        cache.set(
            f"youtube_oauth_state:{state}",
            str(organization_id),
            timeout=YouTubeOAuthService.STATE_TTL,
        )

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(YouTubeOAuthService.SCOPES),
            "access_type": "offline",
            "prompt": "select_account consent",
            "state": state,
        }

        return YouTubeOAuthService.AUTH_URL + "?" + urllib.parse.urlencode(params)

    @staticmethod
    def exchange_code(code):

        response = requests.post(
            YouTubeOAuthService.TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception("YouTube token exchange failed")

        return response.json()

    @staticmethod
    def refresh_access_token(refresh_token):

        response = requests.post(
            YouTubeOAuthService.TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"YouTube token refresh failed: {response.text}")

        return response.json()

    @staticmethod
    def fetch_channel(access_token):

        response = requests.get(
            f"{YouTubeOAuthService.YT_API_BASE}/channels",
            params={
                "part": "snippet",
                "mine": "true",
            },
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception("Failed to fetch YouTube channel")

        return response.json()

    @staticmethod
    def validate_state(state):

        org_id = cache.get(f"youtube_oauth_state:{state}")

        if not org_id:
            raise Exception("Invalid or expired YouTube OAuth state")

        cache.delete(f"youtube_oauth_state:{state}")

        return org_id
