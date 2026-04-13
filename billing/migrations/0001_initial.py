from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(choices=[("free", "Free"), ("starter", "Starter"), ("pro", "Pro"), ("enterprise", "Enterprise")], max_length=20, unique=True)),
                ("stripe_price_id", models.CharField(blank=True, help_text="Stripe price ID (e.g. price_xxx)", max_length=200)),
                ("max_projects", models.IntegerField(default=1, help_text="0 = unlimited")),
                ("max_tasks_per_month", models.IntegerField(default=10, help_text="0 = unlimited")),
                ("price_cents", models.IntegerField(default=0, help_text="Price in cents (e.g. 4900 = $49.00)")),
            ],
            options={
                "ordering": ["price_cents"],
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stripe_subscription_id", models.CharField(blank=True, max_length=200)),
                ("status", models.CharField(choices=[("active", "Active"), ("canceled", "Canceled"), ("past_due", "Past Due"), ("trialing", "Trialing"), ("incomplete", "Incomplete")], default="active", max_length=20)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="billing.plan")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
