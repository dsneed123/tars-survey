from django.urls import path
from . import views

app_name = 'surveys'

urlpatterns = [
    path('', views.home, name='home'),
    path('<int:pk>/', views.survey_detail, name='survey_detail'),
    path('<int:pk>/submit/', views.survey_submit, name='survey_submit'),
    path('<int:pk>/thank-you/', views.thank_you, name='thank_you'),
]
