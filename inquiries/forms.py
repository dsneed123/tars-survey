from django import forms
from .models import Inquiry


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = [
            "contact_name",
            "email",
            "company_name",
            "company_size",
            "phone",
            "industry",
            "project_description",
            "primary_language",
            "repo_url",
            "budget_range",
            "timeline",
            "how_heard_about_us",
        ]
        widgets = {
            "contact_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Jane Smith",
                "autocomplete": "name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "jane@acmecorp.com",
                "autocomplete": "email",
            }),
            "company_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Acme Corp",
                "autocomplete": "organization",
            }),
            "company_size": forms.Select(attrs={"class": "form-select"}),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+1 (555) 000-0000",
                "autocomplete": "tel",
            }),
            "industry": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. SaaS, E-commerce, FinTech",
            }),
            "project_description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Describe what you want to build or automate. Include any relevant context, goals, or constraints...",
            }),
            "primary_language": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Python, TypeScript, Go",
            }),
            "repo_url": forms.URLInput(attrs={
                "class": "form-control",
                "placeholder": "https://github.com/your-org/your-repo",
            }),
            "budget_range": forms.Select(attrs={"class": "form-select"}),
            "timeline": forms.Select(attrs={"class": "form-select"}),
            "how_heard_about_us": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Twitter, Google, a friend",
            }),
        }
