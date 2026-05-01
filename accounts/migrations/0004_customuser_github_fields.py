from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_add_is_email_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='github_id',
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='github_username',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='customuser',
            name='github_avatar_url',
            field=models.URLField(blank=True),
        ),
    ]
