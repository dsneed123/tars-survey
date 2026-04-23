from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workers', '0002_taskassignment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='worker',
            name='status',
            field=models.CharField(
                choices=[('online', 'Online'), ('busy', 'Busy'), ('offline', 'Offline'), ('maintenance', 'Maintenance')],
                db_index=True,
                default='offline',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='worker',
            name='last_heartbeat',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
