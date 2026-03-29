from urllib.parse import urlencode

import requests
from django.conf import settings


class MetaOAuthService:

    GRAPH_BASE = "https://graph.facebook.com/v18.0"
    AUTH_BASE_URL = "https://www.facebook.com/v18.0/dialog/oauth"

    SCOPES = [
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
        "instagram_basic",
        "instagram_content_publish",
        "instagram_manage_insights",
        "pages_read_user_content",
    ]

    def exchange_code(self, code: str):
        response = requests.get(
            f"{self.GRAPH_BASE}/oauth/access_token",
            params={
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "redirect_uri": settings.META_REDIRECT_URI,
                "code": code,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_long_lived_token(self, short_token: str):
        response = requests.get(
            f"{self.GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "fb_exchange_token": short_token,
            },
        )
        response.raise_for_status()
        return response.json()

    def fetch_pages(self, user_token: str):
        response = requests.get(
            f"{self.GRAPH_BASE}/me/accounts",
            params={
                "access_token": user_token,
                "fields": "id,name,access_token,instagram_business_account",
            },
        )
        response.raise_for_status()
        return response.json()

    def fetch_user_profile(self, access_token: str):
        response = requests.get(
            f"{self.GRAPH_BASE}/me",
            params={"access_token": access_token},
        )
        response.raise_for_status()
        return response.json()

    def fetch_instagram_account(self, page_id: str, page_token: str):
        response = requests.get(
            f"{self.GRAPH_BASE}/{page_id}",
            params={
                "fields": "instagram_business_account",
                "access_token": page_token,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("instagram_business_account")

    def fetch_instagram_profile(self, ig_id: str, page_token: str):
        response = requests.get(
            f"{self.GRAPH_BASE}/{ig_id}",
            params={
                "fields": "id,username",
                "access_token": page_token,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": settings.META_APP_ID,
            "redirect_uri": settings.META_REDIRECT_URI,
            "scope": ",".join(self.SCOPES),
            "response_type": "code",
            "state": state,
            "auth_type": "rerequest",
        }
        return f"{self.AUTH_BASE_URL}?{urlencode(params)}"
