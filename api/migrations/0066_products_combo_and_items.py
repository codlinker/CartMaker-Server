import uuid
import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models


def migrate_legacy_fake_combos_forward(apps, schema_editor):
    """
    Si existían registros temporales de combos guardados como `Product(selling_unit='combo')`
    o `attributes.is_combo = True`, los migra al modelo relacional `ProductsCombo` +
    `ProductsComboItem` y limpia la tabla `Product`.
    """
    Product = apps.get_model('api', 'Product')
    InventoryItem = apps.get_model('api', 'InventoryItem')
    ProductsCombo = apps.get_model('api', 'ProductsCombo')
    ProductsComboItem = apps.get_model('api', 'ProductsComboItem')

    fake_products = list(Product.objects.filter(selling_unit='combo'))
    for prod in fake_products:
        attrs = prod.attributes if isinstance(prod.attributes, dict) else {}
        raw_items = attrs.get('combo_items') if isinstance(attrs.get('combo_items'), list) else []
        inv_items = list(InventoryItem.objects.filter(product_id=prod.id))
        for inv in inv_items:
            combo = ProductsCombo.objects.create(
                id=inv.id,
                company_id=prod.company_id,
                store_id=inv.store_id,
                category_id=prod.category_id,
                name=prod.name,
                description=prod.description or '',
                price=inv.custom_price if inv.custom_price is not None else prod.price,
                custom_images=prod.images if isinstance(prod.images, list) else [],
                stock=inv.stock,
                deduct_component_stock=False,
                paused=inv.paused,
                sold_out_time=inv.sold_out_time,
                expiration_date=inv.expiration_date,
                discounts_by_tokens_active=prod.discounts_by_tokens_active,
                discounts_data=prod.discounts_data if isinstance(prod.discounts_data, (dict, list)) else {},
                cached_popularity_score=inv.cached_popularity_score,
            )
            for idx, entry in enumerate(raw_items):
                if not isinstance(entry, dict):
                    continue
                comp_prod_id = entry.get('product_id')
                comp_inv_id = entry.get('inventory_item_id')
                comp_prod = None
                if comp_prod_id:
                    comp_prod = Product.objects.filter(id=comp_prod_id, company_id=prod.company_id).exclude(id=prod.id).first()
                if comp_prod is None and comp_inv_id:
                    comp_inv = InventoryItem.objects.filter(id=comp_inv_id, store_id=inv.store_id).select_related('product').first()
                    if comp_inv and comp_inv.product_id != prod.id:
                        comp_prod = comp_inv.product
                if comp_prod is not None:
                    ProductsComboItem.objects.create(
                        combo=combo,
                        product=comp_prod,
                        quantity=max(1, int(float(entry.get('quantity') or 1))),
                        notes=str(entry.get('notes') or '')[:255],
                        position=idx,
                    )
        prod.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0065_merge_20261020_1400'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductsCombo',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('custom_images', models.JSONField(blank=True, default=list)),
                ('stock', models.IntegerField(default=0)),
                ('deduct_component_stock', models.BooleanField(
                    default=False,
                    help_text=(
                        'Si es True y los productos que integran el combo tienen lote activo en la misma '
                        'sucursal, al vender o cancelar un combo también se descuenta/reintegra su stock individual.'
                    ),
                )),
                ('paused', models.BooleanField(default=False)),
                ('creation', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('sold_out_time', models.DateTimeField(blank=True, null=True)),
                ('expiration_date', models.DateTimeField(blank=True, null=True)),
                ('discounts_by_tokens_active', models.BooleanField(default=False)),
                ('discounts_data', models.JSONField(blank=True, default=dict)),
                ('cached_popularity_score', models.FloatField(
                    db_index=True,
                    default=0.0,
                    help_text='Puntuación precalculada de interacciones del combo para el motor de búsqueda.',
                )),
                ('category', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='combos',
                    to='api.subcategory',
                )),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='combos',
                    to='api.company',
                )),
                ('store', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='combos',
                    to='api.companystore',
                )),
            ],
            options={
                'ordering': ['-creation'],
                'indexes': [
                    models.Index(fields=['store', 'paused', 'stock'], name='combo_store_paused_stock_idx'),
                    models.Index(fields=['company', '-creation'], name='combo_company_creation_idx'),
                    django.contrib.postgres.indexes.GinIndex(
                        fields=['name'],
                        name='combo_name_gin_idx',
                        opclasses=['gin_trgm_ops'],
                    ),
                    django.contrib.postgres.indexes.GinIndex(
                        fields=['description'],
                        name='combo_desc_gin_idx',
                        opclasses=['gin_trgm_ops'],
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name='ProductsComboItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('selected_variant_id', models.CharField(blank=True, default='', max_length=100)),
                ('notes', models.CharField(blank=True, default='', max_length=255)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('combo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='combo_items',
                    to='api.productscombo',
                )),
                ('inventory_item', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='combo_usages',
                    to='api.inventoryitem',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='combo_occurrences',
                    to='api.product',
                )),
            ],
            options={
                'ordering': ['position', 'id'],
                'indexes': [
                    models.Index(fields=['combo', 'position'], name='comboitem_combo_pos_idx'),
                    models.Index(fields=['product'], name='comboitem_product_idx'),
                ],
            },
        ),
        migrations.RunPython(migrate_legacy_fake_combos_forward, migrations.RunPython.noop),
    ]
