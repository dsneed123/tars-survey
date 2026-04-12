from django.contrib import admin
from .models import Inquiry, InquiryNote


class InquiryNoteInline(admin.TabularInline):
    model = InquiryNote
    extra = 1
    readonly_fields = ('created_at',)


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'company', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'email', 'company', 'message')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [InquiryNoteInline]


@admin.register(InquiryNote)
class InquiryNoteAdmin(admin.ModelAdmin):
    list_display = ('inquiry', 'created_at')
    readonly_fields = ('created_at',)
