from django.contrib.auth import get_user_model
from django.db import transaction

from .otp_service import create_otp

User = get_user_model()


@transaction.atomic
def register_user(email, password):
    user = User.objects.create_user(email=email, password=password)
    user.is_active = False
    user.is_email_verified = False
    user.save()

    create_otp(email=email, purpose="email_verification")

    return user
