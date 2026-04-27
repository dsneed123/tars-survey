from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0003_remove_memberprofile_onboarding"),
    ]

    operations = [
        migrations.AddField(
            model_name="memberprofile",
            name="tour_completed",
            field=models.BooleanField(default=False),
        ),
    ]
