from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import CustomUser

_INPUT = "form-control"


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": _INPUT, "placeholder": "you@company.com", "autofocus": True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": _INPUT, "placeholder": "Password"})
    )


class RegisterForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": _INPUT, "placeholder": "you@company.com", "autofocus": True})
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": _INPUT, "placeholder": "Create a password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"class": _INPUT, "placeholder": "Repeat password"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except ValidationError as e:
                self.add_error("password1", e)
        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"].lower()
        display_name = email.split("@")[0]
        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            password=self.cleaned_data["password1"],
            first_name=display_name,
        )
        return user
