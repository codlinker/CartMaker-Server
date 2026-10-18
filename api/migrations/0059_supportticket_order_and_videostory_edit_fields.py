import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0058_user_biometric_consent_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportticket',
            name='order',
            field=models.ForeignKey(
                blank=True,
                help_text='Orden reportada por el usuario o comercio (si aplica).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='support_tickets',
                to='api.order',
            ),
        ),
        migrations.AddField(
            model_name='companyvideostory',
            name='title',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='companyvideostory',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='companyvideostory',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
