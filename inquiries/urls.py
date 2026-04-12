from django.urls import path

from . import views

app_name = 'inquiries'

urlpatterns = [
    path('inquiries/', views.submit_inquiry, name='submit_inquiry'),
    path('inquiries/stats/', views.inquiry_stats, name='inquiry_stats'),
]
