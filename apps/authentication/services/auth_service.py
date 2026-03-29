# apps/authentication/services/auth_service.py

from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.services.otp_service import create_otp

User = get_user_model()


def register_user(email, password):
    user = User.objects.create_user(email=email, password=password)

    user.is_active = False
    user.is_email_verified = False
    user.save(update_fields=["is_active", "is_email_verified"])

    create_otp(user=user, purpose="email_verification")

    return user


def verify_email(user):
    user.is_active = True
    user.is_email_verified = True
    user.save(update_fields=["is_active", "is_email_verified"])


def login_user(request, email, password):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise Exception("INVALID_CREDENTIALS")

    # account lock check
    if user.account_locked_until and user.account_locked_until > timezone.now():
        raise Exception("ACCOUNT_LOCKED")

    user_auth = authenticate(request, username=email, password=password)

    if not user_auth:
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= 5:
            lock_minutes = min(60, 5 * (2 ** (user.failed_login_attempts - 5)))
            user.account_locked_until = timezone.now() + timedelta(minutes=lock_minutes)

        user.save(update_fields=["failed_login_attempts", "account_locked_until"])

        raise Exception("INVALID_CREDENTIALS")

    # reset counters
    user.failed_login_attempts = 0
    user.account_locked_until = None
    user.save(update_fields=["failed_login_attempts", "account_locked_until"])

    refresh = RefreshToken.for_user(user)

    return {
        "user": user,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
