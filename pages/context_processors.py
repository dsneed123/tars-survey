from django.conf import settings


def site_url(request):
    return {"SITE_URL": getattr(settings, "SITE_URL", "")}
