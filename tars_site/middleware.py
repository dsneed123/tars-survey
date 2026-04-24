import json
import logging
import threading
import time
import uuid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request-ID tracking — thread-local storage shared between middleware and
# the logging filter so every log record carries the current request_id.
# ---------------------------------------------------------------------------
_request_id_local = threading.local()


def get_request_id() -> str:
    return getattr(_request_id_local, "request_id", "-") or "-"


class RequestIdMiddleware:
    """Attach a unique request_id to every HTTP request for log tracing.

    Reads X-Request-Id from the incoming headers (for upstream tracing) or
    generates a fresh UUID.  Stores it on request.request_id and in a
    thread-local so log records emitted during the request carry it.
    The id is echoed back in the X-Request-Id response header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.request_id = request_id
        _request_id_local.request_id = request_id
        try:
            response = self.get_response(request)
        finally:
            _request_id_local.request_id = None
        response["X-Request-Id"] = request_id
        return response


class RequestIdFilter(logging.Filter):
    """Inject the current request_id into every log record."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for Railway log aggregation."""

    def format(self, record):
        record.message = record.getMessage()
        log_entry = {
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.message,
        }
        if record.exc_info:
            log_entry["traceback"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_entry["traceback"] = record.exc_text
        return json.dumps(log_entry, ensure_ascii=False)


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
