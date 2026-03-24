import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_progress', '0002_courseprogressrecord_moduleprogressrecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='badge',
            name='course',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='progress_badges', to='courses.course'),
        ),
    ]
