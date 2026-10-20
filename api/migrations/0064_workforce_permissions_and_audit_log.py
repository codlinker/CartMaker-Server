# Migración escrita a mano:
# - Permisos granulares en EmployeePermission (`can_confirm_payments`) y EmployeeInvitation (`can_edit_inventory`, `can_confirm_payments`, `can_manage_orders`).
# - Bitácora de auditoría y reversión en 1 toque (`EmployeeAuditLog`).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0063_delivery_assignments_shifts_and_traces'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeepermission',
            name='can_confirm_payments',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='employeeinvitation',
            name='can_edit_inventory',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='employeeinvitation',
            name='can_confirm_payments',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='employeeinvitation',
            name='can_manage_orders',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='EmployeeAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(db_index=True, max_length=40)),
                ('target_type', models.CharField(db_index=True, max_length=32)),
                ('target_id', models.CharField(db_index=True, max_length=64)),
                ('target_label', models.CharField(blank=True, default='', max_length=255)),
                ('summary', models.CharField(blank=True, default='', max_length=255)),
                ('before_snapshot', models.JSONField(blank=True, default=dict)),
                ('after_snapshot', models.JSONField(blank=True, default=dict)),
                ('is_reversible', models.BooleanField(db_index=True, default=False)),
                ('reverted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='employee_audit_logs',
                    to='api.company',
                )),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs',
                    to='api.employee',
                )),
                ('reverted_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reverted_employee_audit_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='employee_audit_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['company', 'employee', '-created_at'], name='empaudit_comp_emp_created_idx'),
                    models.Index(fields=['employee', 'is_reversible', 'reverted_at'], name='empaudit_emp_rev_state_idx'),
                ],
            },
        ),
    ]
