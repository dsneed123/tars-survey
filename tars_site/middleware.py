import logging
import time

logger = logging.getLogger(__name__)

# Requests slower than this threshold (seconds) are logged as warnings.
_SLOW_REQUEST_THRESHOLD = 0.5

# Content-Security-Policy directive string.
# Permits CDN assets used by the app (Bootstrap, Stripe, reCAPTCHA, etc.).
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' "
    "https://www.google.com https://www.gstatic.com "
    "https://cdn.jsdelivr.net https://js.stripe.com; "
    "style-src 'self' 'unsafe-inline' "
    "https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' "
    "https://fonts.gstatic.com https://cdn.jsdelivr.net; "
    "img-src 'self' data: https:; "
    "frame-src https://js.stripe.com https://www.google.com; "
    "connect-src 'self';"
)


class SlowRequestLoggingMiddleware:
    """Log a warning for any request that takes longer than 500 ms."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start
        if duration >= _SLOW_REQUEST_THRESHOLD:
            logger.warning(
                "Slow request: %s %s took %.3fs",
                request.method,
                request.get_full_path(),
                duration,
            )
        return response


class ContentSecurityPolicyMiddleware:
    """Attach a Content-Security-Policy header to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", _CSP)
        return response
