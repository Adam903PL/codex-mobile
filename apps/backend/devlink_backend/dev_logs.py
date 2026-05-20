from __future__ import annotations

from collections import deque
import logging
from time import perf_counter
from typing import Any

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

RECENT_REQUESTS: deque[dict[str, Any]] = deque(maxlen=300)
RECENT_ERRORS: deque[dict[str, Any]] = deque(maxlen=100)

logger = logging.getLogger(__name__)


class ApiJsonExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            if not request.path.startswith("/api/"):
                raise
            logger.exception("Unhandled API exception on %s", request.get_full_path())
            payload = {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Backend napotkal blad. Szczegoly sa w terminalu serwera i panelu /devlink-debug/.",
                "details": {"exception": exc.__class__.__name__ if settings.DEBUG else ""},
                "request_id": request.headers.get("X-Request-ID", ""),
            }
            record_api_error(request, 500, payload)
            return JsonResponse(payload, status=500)


class RecentRequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = perf_counter()
        response = self.get_response(request)
        duration_ms = int((perf_counter() - started_at) * 1000)
        if request.path == "/devlink-debug/logs.json":
            return response
        RECENT_REQUESTS.appendleft(
            {
                "method": request.method,
                "path": request.get_full_path(),
                "status": response.status_code,
                "duration_ms": duration_ms,
                "remote_addr": request.META.get("REMOTE_ADDR", ""),
                "user": getattr(getattr(request, "user", None), "username", "") if getattr(request, "user", None) and request.user.is_authenticated else "",
                "created_at": timezone.now().isoformat(),
            }
        )
        return response


def record_api_error(request, status_code: int, payload: dict[str, Any]) -> None:
    RECENT_ERRORS.appendleft(
        {
            "method": getattr(request, "method", ""),
            "path": request.get_full_path() if request else "",
            "status": status_code,
            "remote_addr": request.META.get("REMOTE_ADDR", "") if request else "",
            "payload": payload,
            "created_at": timezone.now().isoformat(),
        }
    )
