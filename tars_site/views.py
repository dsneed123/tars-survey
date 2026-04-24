import logging
import sys

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

_VERSION = "1.0"


async def _ping_channel_layer(channel_layer):
    await channel_layer.group_add("_health_check", "_health_check")
    await channel_layer.group_discard("_health_check", "_health_check")


@require_GET
def api_health(request):
    db_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        logger.warning("Health check: database unreachable")

    redis_ok = False
    try:
        channel_layer = get_channel_layer()
        if channel_layer is not None and channel_layer.__class__.__module__.startswith("channels_redis"):
            async_to_sync(_ping_channel_layer)(channel_layer)
            redis_ok = True
    except Exception:
        logger.warning("Health check: channel layer unreachable")

    healthy = db_ok
    return JsonResponse(
        {
            "status": "ok" if healthy else "error",
            "db": db_ok,
            "redis": redis_ok,
            "version": _VERSION,
        },
        status=200 if healthy else 503,
    )


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
