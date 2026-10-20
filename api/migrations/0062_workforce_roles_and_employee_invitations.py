# Migración escrita a mano (Fase 1 del sistema de trabajadores / delivery).
# - Extiende Employee con rol, estado, vehículo, alias y última actividad.
# - Crea EmployeeInvitation.
# - Agrega categorías de notificación del sistema de trabajadores.

import api.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def sync_employee_status_from_is_active(apps, schema_editor):
    """
    Los empleados existentes con is_active=False pasan a SUSPENDED (1)
    para que `status` y `is_active` queden consistentes.
    """
    Employee = apps.get_model('api', 'Employee')
    Employee.objects.filter(is_active=False).update(status=1)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0061_supportticket_tripartite_mute_and_resolution'),
    ]

    operations = [
        # =====================================================================
        # 1. EMPLOYEE: rol, estado, vehículo, alias y última actividad
        # =====================================================================
        migrations.AddField(
            model_name='employee',
            name='role',
            field=models.IntegerField(
                choices=[(0, 'Asistente'), (1, 'Repartidor')],
                default=0,
            ),
        ),
        migrations.AddField(
            model_name='employee',
            name='status',
            field=models.IntegerField(
                choices=[(0, 'Activo'), (1, 'Suspendido'), (2, 'Revocado')],
                default=0,
            ),
        ),
        migrations.AddField(
            model_name='employee',
            name='vehicle_type',
            field=models.IntegerField(
                blank=True,
                choices=[(0, 'Moto'), (1, 'Bicicleta'), (2, 'Carro'), (3, 'A pie')],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='employee',
            name='display_alias',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
        migrations.AddField(
            model_name='employee',
            name='last_seen_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='employee',
            index=models.Index(fields=['company', 'role', 'status'], name='emp_company_role_status_idx'),
        ),
        migrations.RunPython(sync_employee_status_from_is_active, migrations.RunPython.noop),

        # =====================================================================
        # 2. NOTIFICATION: nuevas categorías del sistema de trabajadores
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
            ]),
        ),

        # =====================================================================
        # 3. EMPLOYEE INVITATION
        # =====================================================================
        migrations.CreateModel(
            name='EmployeeInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.IntegerField(choices=[(0, 'Asistente'), (1, 'Repartidor')], default=0)),
                ('channel', models.IntegerField(
                    choices=[(0, 'Correo electrónico'), (1, 'Dentro de la app'), (2, 'Enlace o código QR')],
                    default=2,
                )),
                ('target_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('short_code', models.CharField(max_length=8, unique=True)),
                ('status', models.IntegerField(
                    choices=[(0, 'Pendiente'), (1, 'Aceptada'), (2, 'Rechazada'), (3, 'Revocada'), (4, 'Expirada')],
                    default=0,
                )),
                ('expires_at', models.DateTimeField(default=api.models.default_invitation_expiry)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('accepted_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='accepted_employee_invitations',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('allowed_stores', models.ManyToManyField(
                    blank=True,
                    related_name='employee_invitations',
                    to='api.companystore',
                )),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='employee_invitations',
                    to='api.company',
                )),
                ('invited_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sent_employee_invitations',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('target_user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='received_employee_invitations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['company', 'status'], name='empinv_company_status_idx'),
                    models.Index(fields=['target_user', 'status'], name='empinv_target_user_status_idx'),
                    models.Index(fields=['target_email'], name='empinv_target_email_idx'),
                ],
            },
        ),
    ]
