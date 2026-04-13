from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import TemplateView

from pages.sitemaps import StaticViewSitemap

sitemaps = {
    "static": StaticViewSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path("", include("pages.urls")),
    path("", include("inquiries.urls")),
    path("", include("accounts.urls")),
    path("", include("members.urls")),
    path("", include("projects.urls")),
    path("", include("tasks.urls")),
    path("", include("workers.urls")),
    path("", include("analytics.urls")),
    path("", include("billing.urls")),
    path("", include("notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
