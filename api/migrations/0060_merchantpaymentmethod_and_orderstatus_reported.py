import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0059_supportticket_order_and_videostory_edit_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.IntegerField(
                choices=[
                    (0, 'En espera'),
                    (1, 'En camino'),
                    (2, 'Reportada / En revisión'),
                    (3, 'Cancelada'),
                    (4, 'Completada'),
                    (5, 'Solucionada'),
                ],
                default=0,
            ),
        ),
        migrations.CreateModel(
            name='MerchantPaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'method_type',
                    models.CharField(
                        choices=[
                            ('pago_movil', 'Pago Móvil'),
                            ('transferencia', 'Transferencia Bancaria'),
                            ('zelle', 'Zelle'),
                            ('binance', 'Binance Pay'),
                            ('efectivo_usd', 'Efectivo (USD)'),
                            ('efectivo_bs', 'Efectivo (Bs.)'),
                            ('punto_venta', 'Punto de Venta'),
                            ('paypal', 'PayPal'),
                            ('zinli', 'Zinli'),
                            ('wally', 'Wally'),
                            ('otro', 'Otro Método'),
                        ],
                        db_index=True,
                        default='pago_movil',
                        max_length=32,
                    ),
                ),
                (
                    'alias',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text="Etiqueta opcional del método (ej. 'Pago Móvil Banesco Principal').",
                        max_length=120,
                    ),
                ),
                ('bank_name', models.CharField(blank=True, default='', max_length=120)),
                ('bank_code', models.CharField(blank=True, default='', max_length=10)),
                ('phone', models.CharField(blank=True, default='', max_length=40)),
                (
                    'dni',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='Cédula o RIF asociado a la cuenta (ej. V-12345678 o J-31234567-8).',
                        max_length=40,
                    ),
                ),
                ('document_type', models.CharField(blank=True, default='V', max_length=10)),
                ('account_number', models.CharField(blank=True, default='', max_length=60)),
                ('account_type', models.CharField(blank=True, default='', max_length=30)),
                ('holder_name', models.CharField(blank=True, default='', max_length=150)),
                ('email', models.CharField(blank=True, default='', max_length=150)),
                ('wallet_id', models.CharField(blank=True, default='', max_length=120)),
                ('currency', models.CharField(blank=True, default='Bs', max_length=12)),
                ('notes', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='payment_methods',
                        to='api.company',
                    ),
                ),
            ],
            options={
                'ordering': ['-is_active', 'id'],
                'indexes': [
                    models.Index(fields=['company', 'is_active'], name='mpm_company_active_idx'),
                ],
            },
        ),
    ]
