from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0007_chatmessage_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatmessage',
            name='message_type',
            field=models.CharField(
                choices=[
                    ('text', 'Texto'),
                    ('image', 'Imagen'),
                    ('audio', 'Nota de Voz'),
                    ('payment_methods', 'Datos de Pago'),
                    ('payment_info', 'Datos de Pago'),
                ],
                default='text',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='metadata',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
