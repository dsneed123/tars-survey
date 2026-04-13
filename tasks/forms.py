import bleach
from django import forms

from projects.models import Project

from .models import Task


class TaskForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        for field in ("title", "description"):
            value = cleaned.get(field)
            if isinstance(value, str):
                cleaned[field] = bleach.clean(value, tags=[], strip=True)
        return cleaned

    class Meta:
        model = Task
        fields = ["project", "title", "description", "priority"]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Fix login bug, Add dark mode, Refactor auth module",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": "Describe what you want TARS to build or fix. Be specific — include context, acceptance criteria, and any relevant file paths.",
                    "id": "id_description",
                }
            ),
            "priority": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 100,
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
        self.fields["priority"].initial = 50
        self.fields["priority"].help_text = "1 (low) – 100 (urgent). Default is 50."
