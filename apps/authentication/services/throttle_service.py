# apps/authentication/services/throttle_service.py

from django.core.cache import cache
from rest_framework.exceptions import Throttled

THROTTLE_CONFIG = {
    "otp_request": {"ip": 10, "email": 5, "window": 60},
    "login": {"ip": 10, "email": 5, "window": 60},
    "otp_verify": {"ip": 15, "email": 10, "window": 60},
}


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def atomic_increment(key, window):
    if cache.add(key, 1, timeout=window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return 1


def check_limit(key, limit, window):
    count = atomic_increment(key, window)

    if count > limit:
        raise Throttled(detail="Too many requests")


def throttle_request(request, scope, email=None):
    config = THROTTLE_CONFIG.get(scope)

    if not config:
        return

    ip = get_client_ip(request)

    check_limit(
        key=f"throttle:{scope}:ip:{ip}",
        limit=config["ip"],
        window=config["window"],
    )

    if email:
        check_limit(
            key=f"throttle:{scope}:email:{email}",
            limit=config["email"],
            window=config["window"],
        )
