from .models import PageView

_SKIP_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
    "/api/workers/",
    "/__debug__/",
    "/favicon.ico",
    "/sitemap.xml",
    "/robots.txt",
)


class PageViewMiddleware:
    """Log every page request as a PageView record."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not any(request.path.startswith(p) for p in _SKIP_PREFIXES):
            ip = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR")
                or None
            )
            user = (
                request.user
                if hasattr(request, "user") and request.user.is_authenticated
                else None
            )
            try:
                PageView.objects.create(
                    path=request.path,
                    user=user,
                    ip_address=ip or None,
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
                    referrer=request.META.get("HTTP_REFERER", "")[:500],
                )
            except Exception:
                pass
        return response
