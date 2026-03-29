from django.conf import settings
from django.db import models


class AuditLog(models.Model):

    class ActionType(models.TextChoices):
        LOGIN_SUCCESS = "LOGIN_SUCCESS", "Login Success"
        LOGIN_FAILED = "LOGIN_FAILED", "Login Failed"
        LOGOUT = "LOGOUT", "Logout"
        TOKEN_REFRESH = "TOKEN_REFRESH", "Token Refresh"
        OTP_VERIFIED = "OTP_VERIFIED", "OTP Verified"
        ACCOUNT_LOCKED = "ACCOUNT_LOCKED", "Account Locked"
        ORG_CREATED = "ORG_CREATED", "Organization Created"
        ORG_DELETED = "ORG_DELETED", "Organization Deleted"
        MEMBER_REMOVED = "MEMBER_REMOVED", "Member Removed"
        ROLE_CHANGED = "ROLE_CHANGED", "Role Changed"
        POST_CREATED = "POST_CREATED", "Post Created"

        POST_UPDATED = "POST_UPDATED", "Post Updated"
        POST_DELETED = "POST_DELETED", "Post Deleted"
        POST_RESTORED = "POST_RESTORED", "Post Restored"

    SEVERITY_CHOICES = (
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("CRITICAL", "Critical"),
    )

    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="INFO")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
    )

    action = models.CharField(max_length=50, choices=ActionType.choices, db_index=True)

    target_model = models.CharField(max_length=100, null=True, blank=True)
    target_id = models.CharField(max_length=100, null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "action"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Audit logs are immutable.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.actor} - {self.action}"
