from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0057_alter_atlasplusinvoice_issuer_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='biometric_consent_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='biometric_consent_version',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='biometric_suppressed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='supportticket',
            name='topic',
            field=models.IntegerField(
                choices=[
                    (0, 'Problema con una Orden'),
                    (1, 'Reclamo sobre Tienda'),
                    (2, 'Problema con mi Cuenta'),
                    (3, 'Otro'),
                    (4, 'Privacidad y Habeas Data'),
                ],
                default=3,
            ),
        ),
    ]
