import datetime

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

# Date the site launched / content was last meaningfully updated.
_SITE_LAUNCH = datetime.date(2026, 4, 12)

# (url_name, priority, lastmod)
_PAGES = [
    ("pages:landing",            1.0, _SITE_LAUNCH),
    ("pages:inquiry",            0.7, _SITE_LAUNCH),
    ("pages:services",           0.6, _SITE_LAUNCH),
    ("pages:status",             0.4, _SITE_LAUNCH),
    ("pages:docs_index",         0.6, _SITE_LAUNCH),
    ("pages:docs_getting_started", 0.5, _SITE_LAUNCH),
    ("pages:docs_worker_setup",  0.5, _SITE_LAUNCH),
    ("pages:docs_api_reference", 0.5, _SITE_LAUNCH),
    ("pages:docs_faq",           0.5, _SITE_LAUNCH),
    ("pages:docs_changelog",     0.4, _SITE_LAUNCH),
]


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        return _PAGES

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    def lastmod(self, item):
        return item[2]
