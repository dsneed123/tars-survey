import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Worker",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("hostname", models.CharField(max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("capacity", models.IntegerField(default=1)),
                ("current_load", models.IntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("online", "Online"),
                            ("busy", "Busy"),
                            ("offline", "Offline"),
                            ("maintenance", "Maintenance"),
                        ],
                        default="offline",
                        max_length=20,
                    ),
                ),
                ("last_heartbeat", models.DateTimeField(blank=True, null=True)),
                ("registered_at", models.DateTimeField(auto_now_add=True)),
                (
                    "api_key",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("specs", models.TextField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-registered_at"],
            },
        ),
    ]
