import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create a superuser from env vars if none exists"

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Superuser already exists, skipping.")
            return

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@tarsai.dev")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not password:
            self.stdout.write("DJANGO_SUPERUSER_PASSWORD not set, skipping.")
            return

        User.objects.create_superuser(
            username=email.split("@")[0],
            email=email,
            password=password,
        )
        self.stdout.write(f"Superuser created: {email}")
