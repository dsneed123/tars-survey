from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0002_memberprofile_onboarding"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="memberprofile",
            name="onboarding_completed",
        ),
        migrations.RemoveField(
            model_name="memberprofile",
            name="onboarding_step",
        ),
    ]
