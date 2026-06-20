from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("chat/", views.chat_home, name="home"),
    path("chat/send/", views.send, name="send"),
    path("chat/conversation/<int:pk>/", views.conversation_detail, name="conversation"),
    path("chat/conversation/<int:pk>/clear/", views.clear_conversation, name="clear"),
    path("chat/clear-all/", views.clear_all, name="clear_all"),
    path("chat/models/", views.models, name="models"),
    path("chat/models/load/", views.model_load, name="model_load"),
    path("chat/models/unload/", views.model_unload, name="model_unload"),
]
