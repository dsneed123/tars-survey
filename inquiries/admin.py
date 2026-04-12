from django.contrib import admin
from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'email')
    readonly_fields = ('created_at',)
