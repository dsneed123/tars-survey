from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("services/", views.services, name="services"),
    path("health/", views.health, name="health"),
    # Docs
    path("docs/", views.docs_index, name="docs_index"),
    path("docs/getting-started/", views.docs_getting_started, name="docs_getting_started"),
    path("docs/worker-setup/", views.docs_worker_setup, name="docs_worker_setup"),
    path("docs/api-reference/", views.docs_api_reference, name="docs_api_reference"),
    path("docs/faq/", views.docs_faq, name="docs_faq"),
    path("docs/changelog/", views.docs_changelog, name="docs_changelog"),
    path("docs/chat-interface/", views.docs_chat_interface, name="docs_chat_interface"),
    # Status
    path("status/", views.status, name="status"),
]
