from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
        ("teams", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="team",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional. Link this project to a team so members can collaborate on it.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="projects",
                to="teams.team",
            ),
        ),
    ]
