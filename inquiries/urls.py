from django.urls import path
from . import views

app_name = 'inquiries'

urlpatterns = [
    path('get-started/', views.get_started, name='get_started'),
    path('get-started/thank-you/', views.thank_you, name='thank_you'),
]
