import re
from django.db import migrations, models


def clean_existing_merchant_payment_method_dnis(apps, schema_editor):
    MerchantPaymentMethod = apps.get_model('api', 'MerchantPaymentMethod')
    for pm in MerchantPaymentMethod.objects.all():
        raw_dni = str(pm.dni or '').strip()
        raw_type = str(pm.document_type or '').strip().upper()
        prefix_match = re.match(r'^([VEJGP])[-\s]*', raw_dni, flags=re.IGNORECASE)
        if prefix_match and not raw_type:
            raw_type = prefix_match.group(1).upper()
        clean_type = (raw_type[:1] if raw_type and raw_type[0] in 'VEJGP' else 'V')
        clean_digits = re.sub(r'^([VEJGP][-\s]*)+', '', raw_dni, flags=re.IGNORECASE).strip()
        if pm.dni != clean_digits or pm.document_type != clean_type:
            pm.dni = clean_digits
            pm.document_type = clean_type
            pm.save(update_fields=['dni', 'document_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0060_merchantpaymentmethod_and_orderstatus_reported'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportticket',
            name='resolution_note',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Conclusión o dictamen detallado escrito por el agente de soporte al cerrar el ticket.',
            ),
        ),
        migrations.AddField(
            model_name='supportticket',
            name='muted_client',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, el comprador está silenciado temporalmente en este ticket.',
            ),
        ),
        migrations.AddField(
            model_name='supportticket',
            name='muted_merchant',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, el comerciante está silenciado temporalmente en este ticket.',
            ),
        ),
        migrations.AddField(
            model_name='supportticket',
            name='mute_reason',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Motivo opcional del silenciamiento temporal.',
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name='supportmessage',
            name='message_type',
            field=models.CharField(
                choices=[
                    ('text', 'Texto'),
                    ('image', 'Imagen'),
                    ('audio', 'Nota de Voz'),
                    ('system', 'Sistema'),
                ],
                default='text',
                max_length=10,
            ),
        ),
        migrations.RunPython(clean_existing_merchant_payment_method_dnis, migrations.RunPython.noop),
    ]
