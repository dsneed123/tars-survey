from django.contrib import admin

from .models import MemberProfile


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "plan_tier", "created_at"]
    list_filter = ["plan_tier"]
    search_fields = ["user__username", "user__email"]
    raw_id_fields = ["user"]
