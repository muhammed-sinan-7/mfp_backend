import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if status.is_server_error(response.status_code):
            logger.exception("Unhandled API server error", exc_info=exc)
            response.data = {
                "error": "Something went wrong. Please try again shortly."
            }
        elif isinstance(response.data, dict) and "detail" in response.data and "error" not in response.data:
            response.data = {"error": response.data["detail"]}
        return response

    logger.exception("Unhandled non-DRF exception", exc_info=exc)
    return Response(
        {"error": "Something went wrong. Please try again shortly."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

