from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0044_company_merchant_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemconfig',
            name='atlas_anonymous_daily_limit',
            field=models.IntegerField(default=3),
        ),
        migrations.AlterField(
            model_name='atlasthread',
            name='plan',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='threads',
                to='api.atlasplusplan',
            ),
        ),
        migrations.AddField(
            model_name='atlasthread',
            name='guest_key',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name='atlasthread',
            constraint=models.UniqueConstraint(
                condition=models.Q(('guest_key__isnull', False)),
                fields=('guest_key',),
                name='unique_atlas_thread_guest_key',
            ),
        ),
    ]
