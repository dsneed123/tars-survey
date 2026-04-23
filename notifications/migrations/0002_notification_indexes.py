from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='is_read',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterField(
            model_name='notification',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
