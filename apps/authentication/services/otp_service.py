# apps/authentication/services/otp_service.py

import secrets
import threading
import logging
import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.authentication.exceptions import (
    OTPCooldownException,
    OTPInvalidException,
    OTPLockedException,
)
from apps.authentication.models import OTPToken

from ..tasks import send_otp_email_task

logger = logging.getLogger(__name__)


def _otp_digest(user_id, purpose, otp_value):
    payload = f"{user_id}:{purpose}:{otp_value}".encode()
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _dispatch_otp_email(email, otp, purpose):
    def _runner():
        try:
            # Synchronous task call inside background thread avoids broker round-trip latency.
            send_otp_email_task(email, otp, purpose)
        except Exception as err:
            logger.exception("OTP email send failed: %s", err)

    threading.Thread(target=_runner, daemon=True).start()


def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


@transaction.atomic
def create_otp(user, purpose):

    cache_key = f"otp_cooldown:{user.id}:{purpose}"

    if cache.get(cache_key):
        raise OTPCooldownException()

    cache.set(cache_key, True, timeout=60)

    OTPToken.objects.filter(
        user=user,
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)

    otp = generate_otp()

    otp_hash = _otp_digest(user.id, purpose, otp)
    expires_at = timezone.now() + timedelta(minutes=5)

    OTPToken.objects.create(
        user=user,
        otp_hash=otp_hash,
        purpose=purpose,
        expires_at=expires_at,
    )

    transaction.on_commit(lambda: _dispatch_otp_email(user.email, otp, purpose))

    return True


@transaction.atomic
def verify_otp(user, purpose, otp_input):
    otp_obj = (
        OTPToken.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
        )
        .order_by("-created_at")
        .first()
    )

    if not otp_obj or otp_obj.expires_at < timezone.now():
        raise OTPInvalidException()

    if otp_obj.attempt_count >= 5:
        raise OTPLockedException()

    otp_digest = _otp_digest(user.id, purpose, otp_input)
    if not hmac.compare_digest(otp_obj.otp_hash, otp_digest):
        otp_obj.attempt_count += 1
        otp_obj.save(update_fields=["attempt_count"])

        remaining = 5 - otp_obj.attempt_count
        raise OTPInvalidException(f"{remaining}")

    otp_obj.is_used = True
    otp_obj.save(update_fields=["is_used"])

    return True
