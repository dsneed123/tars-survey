from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Inquiry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('company', models.CharField(blank=True, max_length=255)),
                ('message', models.TextField()),
                ('status', models.CharField(
                    choices=[
                        ('new', 'New'),
                        ('contacted', 'Contacted'),
                        ('qualified', 'Qualified'),
                        ('proposal', 'Proposal'),
                        ('won', 'Won'),
                        ('lost', 'Lost'),
                    ],
                    default='new',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contacted_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'inquiries',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InquiryNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('inquiry', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notes',
                    to='inquiries.inquiry',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
