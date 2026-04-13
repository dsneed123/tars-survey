import logging
from datetime import timezone

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as dj_timezone
from django.views.decorators.http import require_POST

from projects.models import Project

from .forms import TeamForm, TeamInviteForm
from .models import Team, TeamInvite, TeamMembership

logger = logging.getLogger(__name__)
User = get_user_model()


def _user_teams(user):
    """Return all teams the user owns or belongs to."""
    return (
        Team.objects.filter(Q(owner=user) | Q(memberships__user=user))
        .distinct()
        .order_by("-created_at")
    )


@login_required
def team_list(request):
    teams = _user_teams(request.user)
    return render(request, "teams/team_list.html", {"teams": teams})


@login_required
def team_create(request):
    if request.method == "POST":
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.owner = request.user
            team.save()
            messages.success(request, f'Team "{team.name}" created.')
            return redirect("teams:detail", slug=team.slug)
    else:
        form = TeamForm()
    return render(request, "teams/team_create.html", {"form": form})


@login_required
def team_detail(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not team.is_member(request.user):
        raise Http404()
    memberships = team.memberships.select_related("user").order_by("joined_at")
    projects = team.projects.filter(is_active=True).order_by("-created_at")
    pending_invites = team.invites.filter(status="pending").order_by("-created_at")
    return render(request, "teams/team_detail.html", {
        "team": team,
        "memberships": memberships,
        "projects": projects,
        "pending_invites": pending_invites,
        "is_admin": team.is_admin(request.user),
    })


@login_required
def team_invite(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not team.is_admin(request.user):
        raise Http404()

    invite = None
    if request.method == "POST":
        form = TeamInviteForm(request.POST)
        if form.is_valid():
            invite = form.save(commit=False)
            invite.team = team
            invite.invited_by = request.user
            invite.save()
            messages.success(request, "Invite link generated — share it with your teammate.")
            return render(request, "teams/team_invite.html", {
                "team": team,
                "form": TeamInviteForm(),
                "invite": invite,
                "absolute_invite_url": request.build_absolute_uri(invite.accept_url()),
            })
    else:
        form = TeamInviteForm()

    return render(request, "teams/team_invite.html", {
        "team": team,
        "form": form,
        "invite": invite,
    })


@login_required
def invite_accept(request, token):
    invite = get_object_or_404(TeamInvite, token=token)
    if invite.status != "pending":
        messages.error(request, "This invite has already been used or revoked.")
        return redirect("teams:list")

    team = invite.team
    if team.is_member(request.user):
        messages.info(request, f"You're already a member of {team.name}.")
        return redirect("teams:detail", slug=team.slug)

    if request.method == "POST":
        with transaction.atomic():
            TeamMembership.objects.create(
                team=team,
                user=request.user,
                role=invite.role,
                invited_by=invite.invited_by,
            )
            invite.status = "accepted"
            invite.accepted_at = dj_timezone.now()
            invite.save(update_fields=["status", "accepted_at"])
        messages.success(request, f"Welcome to {team.name}.")
        return redirect("teams:detail", slug=team.slug)

    return render(request, "teams/team_invite_accept.html", {
        "team": team,
        "invite": invite,
    })


@login_required
@require_POST
def team_leave(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if team.owner_id == request.user.id:
        messages.error(request, "Owners can't leave their own team. Transfer ownership or delete it.")
        return redirect("teams:detail", slug=team.slug)
    TeamMembership.objects.filter(team=team, user=request.user).delete()
    messages.success(request, f"You left {team.name}.")
    return redirect("teams:list")


@login_required
@require_POST
def team_member_remove(request, slug, user_id):
    team = get_object_or_404(Team, slug=slug)
    if not team.is_admin(request.user):
        raise Http404()
    if team.owner_id == user_id:
        messages.error(request, "You can't remove the team owner.")
        return redirect("teams:detail", slug=team.slug)
    removed = TeamMembership.objects.filter(team=team, user_id=user_id).delete()
    if removed[0]:
        messages.success(request, "Member removed.")
    return redirect("teams:detail", slug=team.slug)
