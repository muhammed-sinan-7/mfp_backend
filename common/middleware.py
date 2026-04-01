import logging
import time

logger = logging.getLogger(__name__)


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        try:
            response["Server-Timing"] = f"app;dur={elapsed_ms:.2f}"
            response["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"
        except Exception:
            pass

        if elapsed_ms >= 1000:
            logger.warning(
                "Slow request: method=%s path=%s status=%s duration_ms=%.2f",
                request.method,
                request.path,
                getattr(response, "status_code", "unknown"),
                elapsed_ms,
            )

        return response
