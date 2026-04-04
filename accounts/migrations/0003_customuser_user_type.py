from django.db import migrations, models


def forwards(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    for user in CustomUser.objects.all().iterator():
        if user.is_staff or user.is_superuser:
            user.user_type = 'admin'
        else:
            user.user_type = 'learner'
        user.save(update_fields=['user_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_customuser_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='user_type',
            field=models.CharField(choices=[('learner', 'Learner'), ('admin', 'Admin')], default='learner', max_length=20),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
