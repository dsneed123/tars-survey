from django.contrib import admin

from .models import Team, TeamInvite, TeamMembership


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "created_at")
    search_fields = ("name", "slug", "owner__email")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("team", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("team__name", "user__email")


@admin.register(TeamInvite)
class TeamInviteAdmin(admin.ModelAdmin):
    list_display = ("team", "email", "role", "status", "invited_by", "created_at")
    list_filter = ("status", "role")
    search_fields = ("team__name", "email")
    readonly_fields = ("token", "created_at", "accepted_at")
