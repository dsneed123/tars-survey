from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Survey


class SurveySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Survey.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.created_at


class StaticViewSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 1.0

    def items(self):
        return ['surveys:home']

    def location(self, item):
        return reverse(item)
