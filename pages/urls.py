from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("inquiry/", views.inquiry, name="inquiry"),
    path("inquiry/success/", views.inquiry_success, name="inquiry_success"),
]
