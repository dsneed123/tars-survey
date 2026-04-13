import logging

logger = logging.getLogger(__name__)


def fire_event(name, user=None, metadata=None):
    """Record an analytics event. Silently fails so it never breaks callers."""
    try:
        from .models import Event

        Event.objects.create(
            name=name,
            user=user,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.warning("Failed to fire analytics event %s: %s", name, exc)
