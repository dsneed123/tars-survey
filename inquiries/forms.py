from django import forms
from .models import Inquiry


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = [
            "company_name",
            "contact_name",
            "email",
            "phone",
            "company_size",
            "industry",
            "project_description",
            "budget_range",
            "timeline",
            "how_heard_about_us",
        ]
        widgets = {
            "company_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Acme Corp",
            }),
            "contact_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Jane Smith",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "jane@acmecorp.com",
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+1 (555) 000-0000 (optional)",
            }),
            "company_size": forms.Select(attrs={"class": "form-select"}),
            "industry": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. SaaS, E-commerce, FinTech",
            }),
            "project_description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Describe what you want to build or automate...",
            }),
            "budget_range": forms.Select(attrs={"class": "form-select"}),
            "timeline": forms.Select(attrs={"class": "form-select"}),
            "how_heard_about_us": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Twitter, Google, a friend",
            }),
        }
