from django.http import JsonResponse
from django.shortcuts import render


def handler404(request, exception=None):
    return render(request, "404.html", status=404)


def handler500(request):
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
