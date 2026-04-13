from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inquiries', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inquiry',
            name='primary_language',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='inquiry',
            name='repo_url',
            field=models.URLField(blank=True),
        ),
    ]
