from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("dashboard/billing/", views.billing_page, name="billing"),
    path("dashboard/billing/checkout/", views.create_checkout_session, name="checkout"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
]
