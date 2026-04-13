from .models import Notification


def notifications(request):
    """Inject unread notification count and recent notifications into templates."""
    if not request.user.is_authenticated:
        return {}
    recent = list(
        Notification.objects.filter(user=request.user).order_by("-created_at")[:10]
    )
    unread_count = sum(1 for n in recent if not n.is_read)
    return {
        "notifications_recent": recent,
        "notifications_unread_count": unread_count,
    }
