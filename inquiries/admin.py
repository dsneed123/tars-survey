from django.contrib import admin
from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_name', 'email', 'company_size', 'budget_range', 'status', 'created_at')
    list_filter = ('status', 'company_size', 'budget_range', 'timeline')
    search_fields = ('company_name', 'contact_name', 'email', 'industry')
    readonly_fields = ('created_at',)
