from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    path("dashboard/teams/", views.team_list, name="list"),
    path("dashboard/teams/new/", views.team_create, name="create"),
    path("dashboard/teams/<slug:slug>/", views.team_detail, name="detail"),
    path("dashboard/teams/<slug:slug>/invite/", views.team_invite, name="invite"),
    path("dashboard/teams/<slug:slug>/leave/", views.team_leave, name="leave"),
    path("dashboard/teams/<slug:slug>/members/<int:user_id>/remove/",
         views.team_member_remove, name="member_remove"),
    path("teams/invite/<str:token>/", views.invite_accept, name="invite_accept"),
]
