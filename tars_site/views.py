import logging
import sys

from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def handler404(request, exception=None):
    return render(request, "404.html", status=404)


def handler500(request):
    exc_info = sys.exc_info()
    logger.error(
        "Unhandled 500 error [request_id=%s] %s %s",
        getattr(request, "request_id", "-"),
        request.method,
        request.get_full_path(),
        exc_info=exc_info if exc_info[0] is not None else None,
    )
    return render(request, "500.html", status=500)


def handler403(request, exception=None):
    try:
        from django_ratelimit.exceptions import Ratelimited
        if isinstance(exception, Ratelimited):
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status=429,
                )
            return render(request, "403.html", {"rate_limited": True}, status=429)
    except ImportError:
        pass
    return render(request, "403.html", status=403)
