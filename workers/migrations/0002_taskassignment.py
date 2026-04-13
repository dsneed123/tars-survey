from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0002_task_error_message"),
        ("workers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskAssignment",
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
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "result",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("timeout", "Timeout"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="tasks.task",
                    ),
                ),
                (
                    "worker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="workers.worker",
                    ),
                ),
            ],
            options={
                "ordering": ["-assigned_at"],
            },
        ),
    ]
