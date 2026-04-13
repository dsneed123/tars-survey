import re
import urllib.error
import urllib.request

from django import forms

from .models import Project


def _parse_github_repo(value):
    """Accept a full GitHub URL or owner/repo slug; return 'owner/repo' or None."""
    value = value.strip().rstrip("/")
    # Full URL: https://github.com/owner/repo(.git)
    match = re.match(
        r"^(?:https?://)?github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$",
        value,
    )
    if match:
        return match.group(1)
    # Already owner/repo
    if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", value):
        return value
    return None


def _repo_exists_on_github(github_repo):
    """
    Check if a public GitHub repo exists.
    Returns True if found, False if 404, None on network/other error.
    """
    url = f"https://api.github.com/repos/{github_repo}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "TARS/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        return None
    except Exception:
        return None


class ProjectForm(forms.ModelForm):
    github_repo_url = forms.CharField(
        label="GitHub Repository",
        max_length=300,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "https://github.com/owner/repo  or  owner/repo",
            }
        ),
        help_text="Enter the full GitHub URL or owner/repo slug.",
    )

    class Meta:
        model = Project
        fields = ["name", "description", "language", "default_branch", "team"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "My Project"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "What does this project do?",
                }
            ),
            "language": forms.Select(attrs={"class": "form-select"}),
            "default_branch": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "main"}
            ),
            "team": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["github_repo_url"].initial = self.instance.github_repo
        # Limit team choices to teams the user owns or belongs to.
        if user is not None and user.is_authenticated:
            from teams.models import Team
            from django.db.models import Q
            self.fields["team"].queryset = (
                Team.objects.filter(Q(owner=user) | Q(memberships__user=user))
                .distinct()
                .order_by("name")
            )
        else:
            from teams.models import Team
            self.fields["team"].queryset = Team.objects.none()
        self.fields["team"].empty_label = "Personal (no team)"
        self.fields["team"].required = False

    def clean_github_repo_url(self):
        raw = self.cleaned_data.get("github_repo_url", "")
        parsed = _parse_github_repo(raw)
        if not parsed:
            raise forms.ValidationError(
                "Enter a valid GitHub URL (https://github.com/owner/repo) or owner/repo slug."
            )
        result = _repo_exists_on_github(parsed)
        if result is False:
            raise forms.ValidationError(
                f'Repository "{parsed}" was not found on GitHub. '
                "Check the URL and make sure the repo is public."
            )
        # result is None means a network/API error — allow it through silently
        return parsed

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.github_repo = self.cleaned_data["github_repo_url"]
        if commit:
            instance.save()
        return instance


class ProjectSettingsForm(ProjectForm):
    """Same as ProjectForm but also exposes is_active toggle."""

    class Meta(ProjectForm.Meta):
        fields = ProjectForm.Meta.fields + ["is_active", "default_branch"]
        widgets = {
            **ProjectForm.Meta.widgets,
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
