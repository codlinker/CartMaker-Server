from django.db import migrations, models


def backfill_company_merchant_type(apps, schema_editor):
    Company = apps.get_model('api', 'Company')
    MerchantSubscription = apps.get_model('api', 'MerchantSubscription')
    merchant_types = {
        subscription.merchant_id: subscription.merchant_type
        for subscription in MerchantSubscription.objects.all().only('merchant_id', 'merchant_type')
    }
    for company in Company.objects.all().only('id', 'owner_id', 'merchant_type').iterator():
        merchant_type = merchant_types.get(company.owner_id)
        if merchant_type is not None and company.merchant_type != merchant_type:
            company.merchant_type = merchant_type
            company.save(update_fields=['merchant_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0043_enable_pg_trgm'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='merchant_type',
            field=models.IntegerField(
                choices=[(0, 'Emprendedor'), (1, 'Empresa')],
                default=0,
                help_text='Emprendedor o empresa. Lo define el dueño al configurar la compañía.',
            ),
        ),
        migrations.RunPython(backfill_company_merchant_type, migrations.RunPython.noop),
    ]
