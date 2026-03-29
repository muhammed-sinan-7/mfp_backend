import os

import redis
from django.db import connection
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({"status": "ok"})


def readiness_check(request):
    try:
        # DB check
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Redis check
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            r = redis.from_url(redis_url)
            r.ping()

        return JsonResponse({"status": "ready"})
    except Exception as e:
        return JsonResponse({"status": "not_ready", "error": str(e)}, status=500)
