import pytest


@pytest.fixture(autouse=True)
def disable_cache_and_ratelimit(settings):
    """Disable caching and rate limiting for all tests.

    cache_page and rate limiting both rely on the Django cache backend.
    Using DummyCache prevents stale cached responses from bleeding across
    test cases, and prevents rate-limit counters from accumulating across
    the test run (which would cause 429s on later login tests).
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
    settings.RATELIMIT_ENABLE = False
