from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('inquiry/<int:pk>/', views.inquiry_detail, name='inquiry_detail'),
    path('inquiry/<int:pk>/add-note/', views.add_note, name='add_note'),
    path('inquiry/<int:pk>/change-status/', views.change_status, name='change_status'),
]
