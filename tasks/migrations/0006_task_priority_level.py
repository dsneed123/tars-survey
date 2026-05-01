from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0005_task_is_pinned"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="priority_level",
            field=models.CharField(
                choices=[("high", "High"), ("normal", "Normal"), ("low", "Low")],
                db_index=True,
                default="normal",
                max_length=10,
            ),
        ),
    ]
