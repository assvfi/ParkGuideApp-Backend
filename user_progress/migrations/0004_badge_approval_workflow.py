from django.db import migrations, models


def set_initial_user_badge_status(apps, schema_editor):
    UserBadge = apps.get_model('user_progress', 'UserBadge')

    UserBadge.objects.filter(is_awarded=True).update(status='granted')
    UserBadge.objects.filter(is_awarded=False).update(status='rejected')


class Migration(migrations.Migration):

    dependencies = [
        ('user_progress', '0003_badge_course'),
    ]

    operations = [
        migrations.AddField(
            model_name='badge',
            name='auto_approve_when_eligible',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userbadge',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('granted', 'Granted'), ('rejected', 'Rejected')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.RunPython(set_initial_user_badge_status, migrations.RunPython.noop),
    ]
