from django.db import migrations


def verify_all(apps, schema_editor):
    """Auto-verify all existing users — email verification ('2FA') is removed."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    CustomUser.objects.filter(is_email_verified=False).update(is_email_verified=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_customuser_github_fields"),
    ]

    operations = [
        migrations.RunPython(verify_all, noop),
    ]
