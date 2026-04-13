from django import forms

from .models import Team, TeamInvite, TeamMembership


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Rapid Scuba Crew",
                "autofocus": "autofocus",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "What's this team working on?",
            }),
        }


class TeamInviteForm(forms.ModelForm):
    class Meta:
        model = TeamInvite
        fields = ["email", "role"]
        widgets = {
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "person@example.com (optional — a shareable link is always generated)",
            }),
            "role": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "email": "Invitee email (optional)",
            "role": "Role",
        }
