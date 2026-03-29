import secrets
import urllib.parse
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.social_accounts.models import (
    LinkedInOrganization,
    PublishingTarget,
    SocialAccount,
    SocialProvider,
)


class LinkedInOAuthService:

    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    PROFILE_URL = "https://api.linkedin.com/v2/userinfo"

    STATE_TTL = 600

    @staticmethod
    def generate_authorization_url(organization_id):

        state = secrets.token_urlsafe(32)

        cache.set(
            f"linkedin_oauth_state:{state}",
            str(organization_id),
            timeout=LinkedInOAuthService.STATE_TTL,
        )

        params = {
            "response_type": "code",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "scope": "openid profile email w_member_social",
            "state": state,
        }

        return LinkedInOAuthService.AUTH_URL + "?" + urllib.parse.urlencode(params)

    @staticmethod
    def exchange_code(code):

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }

        response = requests.post(LinkedInOAuthService.TOKEN_URL, data=data, timeout=10)

        if response.status_code != 200:
            raise Exception("LinkedIn token exchange failed")

        return response.json()

    @staticmethod
    def fetch_profile(access_token):

        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(
            LinkedInOAuthService.PROFILE_URL, headers=headers, timeout=10
        )

        if response.status_code != 200:
            raise Exception("Failed to fetch LinkedIn profile")

        return response.json()

    @staticmethod
    def validate_state(state):

        org_id = cache.get(f"linkedin_oauth_state:{state}")

        if not org_id:
            raise Exception("Invalid or expired OAuth state")

        cache.delete(f"linkedin_oauth_state:{state}")

        return org_id

    @staticmethod
    def save_account(org_id, token_data, profile_data):

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        external_id = profile_data.get("sub")
        account_name = profile_data.get("name")

        social_account, _ = SocialAccount.objects.update_or_create(
            organization_id=org_id,
            provider="linkedin",
            external_id=external_id,
            defaults={
                "account_name": account_name,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expires_at": timezone.now() + timedelta(seconds=expires_in),
                "is_active": True,
            },
        )
        PublishingTarget.objects.update_or_create(
            social_account=social_account,
            resource_id=external_id,
            defaults={
                "provider": SocialProvider.LINKEDIN,
                "display_name": account_name,
                "metadata": profile_data,
                "is_active": True,
            },
        )

        return social_account


class LinkedInService:

    BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, social_account):
        self.social_account = social_account

    def ensure_valid_token(self):

        if self.social_account.is_token_expired():
            raise Exception("LinkedIn token expired. Please reconnect account.")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    # def fetch_admin_organizations(self):
    #     """
    #     Fetch organizations where the authenticated user
    #     has ADMINISTRATOR role.
    #     """
    #     url = f"{self.BASE_URL}/organizationAcls?q=roleAssignee"

    #     response = requests.get(
    #         url,
    #         headers=self._headers(),
    #         timeout=10
    #     )

    #     response.raise_for_status()
    #     data = response.json()

    #     return data.get("elements", [])

    # def fetch_organization_detail(self, org_id):
    #     """
    #     Fetch full organization details.
    #     """
    #     url = f"{self.BASE_URL}/organizations/{org_id}"

    #     response = requests.get(
    #         url,
    #         headers=self._headers(),
    #         timeout=10
    #     )

    #     response.raise_for_status()
    #     return response.json()

    # def sync_organizations(self):
    #     """
    #     Sync LinkedIn organizations into:
    #     - LinkedInOrganization model
    #     - PublishingTarget model
    #     """

    #     elements = self.fetch_admin_organizations()

    #     for element in elements:
    #         org_urn = element.get("organization")

    #         if not org_urn:
    #             continue

    #         org_id = org_urn.split(":")[-1]

    #         org_data = self.fetch_organization_detail(org_id)

    #         linkedin_org, _ = LinkedInOrganization.objects.update_or_create(
    #             social_account=self.social_account,
    #             linkedin_id=org_id,
    #             defaults={
    #                 "name": org_data.get("localizedName"),
    #                 "vanity_name": org_data.get("vanityName"),
    #                 "metadata": org_data,
    #                 "is_active": True,
    #             },
    #         )

    #         PublishingTarget.objects.update_or_create(
    #             social_account=self.social_account,
    #             resource_id=org_id,
    #             defaults={
    #                 "provider": self.social_account.provider,
    #                 "display_name": linkedin_org.name,
    #                 "metadata": org_data,
    #                 "is_active": True,
    #             },
    #         )
