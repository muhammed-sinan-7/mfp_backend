import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from storages.backends.s3boto3 import S3Boto3Storage
from apps.industries.models import Industry
from common.models import BaseModel, SoftDeleteModel


class Organization(SoftDeleteModel, BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to="organization_logos/", null=True, blank=True)
    industry = models.ForeignKey(Industry, on_delete=models.SET_NULL, null=True)
    tagline = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_logo_url(self):
        """Return the full S3 signed URL"""
        if self.logo:
            storage = S3Boto3Storage()
            return storage.url(self.logo.name)  
        return None


    def __str__(self):
        return self.name


class OrganizationMember(SoftDeleteModel, BaseModel):

    ROLE_CHOICES = (
        ("OWNER", "Owner"),
        ("ADMIN", "Admin"),
        ("EDITOR", "Editor"),
        ("VIEWER", "Viewer"),
    )

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="members"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    joined_at = models.DateTimeField(default=timezone.now)

    def delete(self, user=None, *args, **kwargs):
        if self.role == "OWNER":
            active_owner_count = OrganizationMember.objects.filter(
                organization=self.organization,
                role="OWNER",
            ).count()

            if active_owner_count <= 1:
                raise ValueError(
                    "You are the owner. Assign a new owner before leaving."
                )

        if self.is_deleted:
            return

        self.is_deleted = True
        self.deleted_at = timezone.now()

        if user:
            self.deleted_by = user

        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="unique_user_membership"),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_deleted=False),
                name="unique_active_user_membership",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.role}"


class OrganizationInvite(models.Model):

    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
        ("EDITOR", "Editor"),
        ("VIEWER", "Viewer"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="invites"
    )

    email = models.EmailField()

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    token = models.UUIDField(default=uuid.uuid4, unique=True)

    is_accepted = models.BooleanField(default=False)

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=3)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invite: {self.email} → {self.organization.name}"
