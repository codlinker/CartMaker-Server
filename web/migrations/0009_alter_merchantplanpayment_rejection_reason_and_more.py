from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('web', '0008_remove_atlasplusplan_is_active_notification'),
    ]

    operations = [
        # 1. Destruimos la columna vieja de texto conflictiva
        migrations.RemoveField(
            model_name='merchantplanpayment',
            name='rejection_reason',
        ),
        # 2. Creamos la nueva columna de enteros limpia
        migrations.AddField(
            model_name='merchantplanpayment',
            name='rejection_reason',
            field=models.IntegerField(blank=True, choices=[(1, 'Referencia inválida o no encontrada'), (2, 'Monto insuficiente'), (3, 'Fecha de transferencia incorrecta'), (4, 'Comprobante falso o ilegible'), (5, 'Otro motivo no especificado')], null=True),
        ),
        # 3. Esta es tu otra migración de las notificaciones, déjala intacta
        migrations.AlterField(
            model_name='notification',
            name='section',
            field=models.IntegerField(choices=[(0, 'Home'), (1, 'Ordenes'), (2, 'Carrito'), (3, 'Buscador'), (4, 'Atlas'), (5, 'Ajustes'), (6, 'Ayuda')]),
        ),
    ]