from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

_INPUT = "form-control"


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": _INPUT, "placeholder": "Username", "autofocus": True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": _INPUT, "placeholder": "Password"})
    )


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": _INPUT, "placeholder": "Email address"}),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": _INPUT, "placeholder": "Username"})
        self.fields["password1"].widget.attrs.update({"class": _INPUT, "placeholder": "Password"})
        self.fields["password2"].widget.attrs.update({"class": _INPUT, "placeholder": "Confirm password"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
