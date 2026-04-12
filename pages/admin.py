from django.contrib import admin
from .models import Inquiry, InquiryNote


class InquiryNoteInline(admin.TabularInline):
    model = InquiryNote
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "company", "team_size", "status", "created_at"]
    list_filter = ["status", "team_size", "created_at"]
    search_fields = ["name", "email", "company"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
    inlines = [InquiryNoteInline]


@admin.register(InquiryNote)
class InquiryNoteAdmin(admin.ModelAdmin):
    list_display = ["inquiry", "created_at"]
    readonly_fields = ["created_at"]
