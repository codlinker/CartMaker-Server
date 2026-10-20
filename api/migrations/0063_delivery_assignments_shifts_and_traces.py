# Migración escrita a mano (Fases 2, 3 y 4 del delivery en tiempo real).
# - RiderShift (turnos de repartidores).
# - DeliveryAssignment (entrega 1:1 con Order, con restricción parcial one_active_delivery_per_rider).
# - DeliveryTrace (traza comprimida msgpack+gzip, expira a los 30 días).
# - Nuevas categorías de notificación de delivery.

import api.models
import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0062_workforce_roles_and_employee_invitations'),
    ]

    operations = [
        # =====================================================================
        # 1. NOTIFICATION: categorías de delivery
        # =====================================================================
        migrations.AlterField(
            model_name='notification',
            name='category',
            field=models.IntegerField(choices=[
                (0, 'Nuevo pago recibido.'),
                (1, 'Pago aprobado.'),
                (2, 'Pago rechazado.'),
                (3, 'Suscripción expirada.'),
                (4, 'Nueva pregunta de cliente.'),
                (5, 'Nuevo pedido recibido.'),
                (6, 'Nueva respuesta recibida.'),
                (7, 'Stock bajo de producto.'),
                (8, 'Producto agotado.'),
                (9, 'Reporte de métricas listo.'),
                (10, 'Alerta de tokens/gamificación.'),
                (11, 'Actualización en orden.'),
                (12, 'Nuevo Mensaje de Chat'),
                (13, 'Invitación para trabajar en un comercio.'),
                (14, 'Actualización de trabajador.'),
                (15, 'Asignación de Delivery'),
                (16, 'Estado de Delivery'),
            ]),
        ),

        # =====================================================================
        # 2. RIDER SHIFT
        # =====================================================================
        migrations.CreateModel(
            name='RiderShift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('last_point', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('last_heartbeat_at', models.DateTimeField(blank=True, null=True)),
                ('battery_level', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='shifts',
                    to='api.employee',
                )),
                ('store', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rider_shifts',
                    to='api.companystore',
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['store', 'is_active'], name='ridershift_store_active_idx'),
                    models.Index(fields=['employee', 'is_active'], name='ridershift_emp_active_idx'),
                ],
            },
        ),

        # =====================================================================
        # 3. DELIVERY ASSIGNMENT
        # =====================================================================
        migrations.CreateModel(
            name='DeliveryAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_auto_assigned', models.BooleanField(default=True)),
                ('status', models.IntegerField(
                    choices=[
                        (0, 'Buscando repartidor'),
                        (1, 'Asignado (esperando aceptación)'),
                        (2, 'Aceptado (en camino a tienda)'),
                        (3, 'En la tienda'),
                        (4, 'En camino al cliente'),
                        (5, 'Llegando al destino'),
                        (6, 'Entregado'),
                        (7, 'Entrega fallida'),
                        (8, 'Cancelado'),
                    ],
                    db_index=True,
                    default=0,
                )),
                ('origin_point', django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ('dest_point', django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ('dest_address_snapshot', models.TextField(blank=True, default='')),
                ('route_geometry', django.contrib.gis.db.models.fields.LineStringField(blank=True, null=True, srid=4326)),
                ('route_polyline6', models.TextField(blank=True, default='')),
                ('route_cum_dist', models.JSONField(blank=True, default=list)),
                ('route_cum_time', models.JSONField(blank=True, default=list)),
                ('route_version', models.PositiveIntegerField(default=1)),
                ('route_distance_m', models.FloatField(default=0.0)),
                ('route_duration_s', models.FloatField(default=0.0)),
                ('eta_at', models.DateTimeField(blank=True, null=True)),
                ('tracking_key', models.CharField(default='', max_length=64)),
                ('handoff_pin', models.CharField(default='', max_length=4)),
                ('handoff_pin_hash', models.CharField(default='', max_length=128)),
                ('pin_attempts', models.PositiveSmallIntegerField(default=0)),
                ('declined_rider_ids', models.JSONField(blank=True, default=list)),
                ('offer_expires_at', models.DateTimeField(blank=True, null=True)),
                ('failure_reason', models.CharField(blank=True, default='', max_length=255)),
                ('last_fix_point', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('last_fix_speed_mps', models.FloatField(blank=True, null=True)),
                ('last_fix_heading', models.FloatField(blank=True, null=True)),
                ('last_fix_accuracy_m', models.FloatField(blank=True, null=True)),
                ('last_fix_at', models.DateTimeField(blank=True, null=True)),
                ('last_fix_source', models.IntegerField(
                    blank=True,
                    choices=[(0, 'GPS directo'), (1, 'Buffer offline'), (2, 'Retransmisión BLE')],
                    null=True,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assigned_at', models.DateTimeField(blank=True, null=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('at_store_at', models.DateTimeField(blank=True, null=True)),
                ('picked_up_at', models.DateTimeField(blank=True, null=True)),
                ('arriving_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assigned_deliveries',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('order', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='delivery_assignment',
                    to='api.order',
                )),
                ('rider', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='deliveries',
                    to='api.employee',
                )),
                ('store', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='delivery_assignments',
                    to='api.companystore',
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['store', 'status'], name='dlv_store_status_idx'),
                    models.Index(fields=['rider', 'status'], name='dlv_rider_status_idx'),
                    models.Index(fields=['status', 'offer_expires_at'], name='dlv_status_offer_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        condition=models.Q(('status__in', [1, 2, 3, 4, 5])),
                        fields=('rider',),
                        name='one_active_delivery_per_rider',
                    ),
                ],
            },
        ),

        # =====================================================================
        # 4. DELIVERY TRACE
        # =====================================================================
        migrations.CreateModel(
            name='DeliveryTrace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('compressed_points', models.BinaryField(blank=True, null=True)),
                ('matched_polyline6', models.TextField(blank=True, default='')),
                ('point_count', models.PositiveIntegerField(default=0)),
                ('max_gap_s', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True, default=api.models.default_trace_expiry)),
                ('delivery', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='trace',
                    to='api.deliveryassignment',
                )),
            ],
        ),
    ]
