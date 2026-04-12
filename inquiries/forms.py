from django import forms
from .models import Inquiry


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = [
            'company_name', 'contact_name', 'email', 'phone',
            'company_size', 'industry', 'project_description',
            'budget_range', 'timeline', 'how_heard_about_us',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Acme Corp',
            }),
            'contact_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Jane Smith',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'jane@acme.com',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 000-0000',
            }),
            'company_size': forms.Select(attrs={'class': 'form-select'}),
            'industry': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. SaaS, Healthcare, Retail',
            }),
            'project_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe what you need help with…',
            }),
            'budget_range': forms.Select(attrs={'class': 'form-select'}),
            'timeline': forms.Select(attrs={'class': 'form-select'}),
            'how_heard_about_us': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Google, referral, LinkedIn…',
            }),
        }
        labels = {
            'company_name': 'Company Name',
            'contact_name': 'Your Name',
            'email': 'Work Email',
            'phone': 'Phone (optional)',
            'company_size': 'Company Size',
            'industry': 'Industry',
            'project_description': 'Project Description',
            'budget_range': 'Budget Range',
            'timeline': 'Timeline',
            'how_heard_about_us': 'How did you hear about us?',
        }
