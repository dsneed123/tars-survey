import bleach
from django import forms

from projects.models import Project

from .models import Task


class TaskForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        value = cleaned.get("title")
        if isinstance(value, str):
            cleaned["title"] = bleach.clean(value, tags=[], strip=True)
        return cleaned

    class Meta:
        model = Task
        fields = ["project", "title"]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Fix login bug, add dark mode, refactor auth module",
                }
            ),
        }

    def __init__(self, user, *args, **kwargs):
        from django.db.models import Q
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            Q(owner=user) | Q(team__owner=user) | Q(team__memberships__user=user),
            is_active=True,
        ).distinct()
        self.fields["project"].empty_label = "Select a project…"
