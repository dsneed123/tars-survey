from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0004_add_task_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='is_pinned',
            field=models.BooleanField(default=False),
        ),
    ]
