# Generated manually for dashboard backup settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='BackupSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('auto_backup_enabled', models.BooleanField(default=False)),
                ('backup_frequency', models.CharField(choices=[('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly')], default='daily', max_length=16)),
                ('firebase_backup_prefix', models.CharField(default='system_backups', max_length=255)),
                ('last_backup_at', models.DateTimeField(blank=True, null=True)),
                ('next_backup_at', models.DateTimeField(blank=True, null=True)),
                ('last_backup_blob_path', models.CharField(blank=True, max_length=500)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
