from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("inquiry/", views.inquiry, name="inquiry"),
    path("about/", views.about, name="about"),
    path("faq/", views.faq, name="faq"),
]
