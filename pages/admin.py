from django.contrib import admin

from .models import InquirySubmission


@admin.register(InquirySubmission)
class InquirySubmissionAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "company", "team_size", "created_at")
    list_filter = ("team_size", "created_at")
    search_fields = ("name", "email", "company")
    readonly_fields = ("created_at",)
