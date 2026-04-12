from django.urls import path
from . import api

urlpatterns = [
    path("inquiries/", api.submit_inquiry, name="api-submit-inquiry"),
    path("inquiries/stats/", api.inquiry_stats, name="api-inquiry-stats"),
]
