from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedTextField

from apps.organizations.models import Organization
from common.models import BaseModel

# Create your models here.


class SocialProvider(models.TextChoices):
    META = "meta", "Meta"
    INSTAGRAM = "instagram", "Instagram"
    LINKEDIN = "linkedin", "LinkedIn"
    YOUTUBE = "youtube", "YouTube"

    @staticmethod
    def ui_meta(provider):
        meta = {
            "linkedin": {
                "brand_color": "#0A66C2",
                "text_color": "#FFFFFF",
                "icon": "linkedin",
            },
            "instagram": {
                "brand_color": "#E1306C",
                "text_color": "#FFFFFF",
                "icon": "instagram",
            },
            "youtube": {
                "brand_color": "#FF0000",
                "text_color": "#FFFFFF",
                "icon": "youtube",
            },
            "facebook": {
                "brand_color": "#1877F2",
                "text_color": "#FFFFFF",
                "icon": "facebook",
            },
        }

        return meta.get(
            provider,
            {
                "brand_color": "#6B7280",
                "text_color": "#FFFFFF",
                "icon": "default",
            },
        )


class SocialAccount(BaseModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="social_accounts",
        db_index=True,
    )

    provider = models.CharField(max_length=20, choices=SocialProvider.choices)

    external_id = models.CharField(max_length=255)
    account_name = models.CharField(max_length=255)

    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField(null=True, blank=True)

    token_expires_at = models.DateTimeField(blank=True, null=True)
    scopes = models.JSONField(default=list, blank=True)
    refresh_failed_count = models.IntegerField(default=0)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "provider", "external_id")
        indexes = [
            models.Index(fields=["organization", "provider"]),
            models.Index(fields=["external_id"]),
        ]

    def is_token_expired(self):
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at


class PublishingTarget(BaseModel):
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name="publishing_targets",
        db_index=True,
    )

    provider = models.CharField(
        max_length=20, choices=SocialProvider.choices, db_index=True
    )

    resource_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)

    metadata = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("social_account", "provider", "resource_id")
        indexes = [
            models.Index(fields=["provider"]),
            models.Index(fields=["resource_id"]),
        ]


class MetaPage(BaseModel):
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name="meta_pages",
        limit_choices_to={"provider": SocialProvider.META},
    )

    page_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    page_access_token = EncryptedTextField()

    instagram_business_id = models.CharField(max_length=255, null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("social_account", "page_id")
        indexes = [
            models.Index(fields=["page_id"]),
            models.Index(fields=["social_account"]),
        ]


class LinkedInOrganization(BaseModel):
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name="linkedin_organizations",
        limit_choices_to={"provider": SocialProvider.LINKEDIN},
    )

    linkedin_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    vanity_name = models.CharField(max_length=255, null=True, blank=True)

    logo_url = models.URLField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("social_account", "linkedin_id")
        indexes = [
            models.Index(fields=["linkedin_id"]),
            models.Index(fields=["social_account"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.linkedin_id})"
