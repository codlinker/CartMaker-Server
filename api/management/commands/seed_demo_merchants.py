# -*- coding: utf-8 -*-
"""
Crea (o actualiza) 4 comercios de demostración en Caracas con 15 productos cada uno.

Idempotente: todos los IDs son deterministas (ver `_demo_merchants_data.py`), por lo que puede ejecutarse varias veces
sin duplicar nada. Por cada usuario configurado hace:

  1. Marca `User.cedula_verified = True` (sin pasar por el flujo biométrico) y `user_type = MERCHANT`.
  2. Crea/actualiza la `Company` (emprendedor, gamificación de tokens activa) y su sucursal principal a pie de calle
     (`StoreType.STREET`, nunca centro comercial) con `StoreLocation` en una calle de Caracas.
  3. Garantiza una `MerchantSubscription` con un plan que incluya gamificación (Plan Comercio por defecto).
  4. Crea 15 productos: descripción, precio, atributos de la subcategoría, variantes con stock, personalizaciones
     (`modifier_groups`), descuentos por tokens, 2 fotos (ya subidas a S3 con `scripts/demo_merchants/upload_images.py`),
     su `InventoryItem` con stock y, en parte de ellos, una `InventoryItemOffer` porcentual vigente.

Uso (en el servidor, con las variables de entorno cargadas: `source variables.sh`):

    python manage.py seed_demo_merchants --dry-run          # simula todo y hace rollback
    python manage.py seed_demo_merchants                    # ejecuta
    python manage.py seed_demo_merchants --only hero epa    # solo algunos comercios
"""
import datetime

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.core.category_schemas import validate_and_normalize_product_dynamic_data
from api.cos import storage_manager
from api.models import (
    Company,
    CompanyCategory,
    CompanyStore,
    InventoryItem,
    InventoryItemOffer,
    MerchantPlan,
    MerchantSubscription,
    MerchantType,
    Product,
    StoreLocation,
    StoreType,
    SubCategory,
    User,
    UserType,
)

from . import _demo_merchants_data as data

WORK_HOURS = {'start': '07:00 AM', 'end': '09:00 PM'}
WORK_DAYS = [0, 1, 2, 3, 4, 5, 6]


class Command(BaseCommand):
    help = 'Crea/actualiza 4 comercios demo en Caracas (verifica cédula, compañía, sucursal, 15 productos c/u).'

    def add_arguments(self, parser):
        parser.add_argument('--only', nargs='+', choices=[c['key'] for c in data.COMPANIES],
                            help='Procesa solo estos comercios.')
        parser.add_argument('--dry-run', action='store_true', help='Simula todo y revierte la transacción.')
        parser.add_argument('--skip-image-check', action='store_true',
                            help='No verifica en S3 que existan las imágenes referenciadas.')
        parser.add_argument('--offer-days', type=int, default=90,
                            help='Días de vigencia de las ofertas porcentuales a partir de hoy (por defecto 90).')
        parser.add_argument('--plan', default='Plan Comercio',
                            help='Nombre del plan a asignar si el usuario no tiene uno con gamificación.')

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        keys = set(opts.get('only') or [c['key'] for c in data.COMPANIES])
        self.dry_run = bool(opts['dry_run'])
        self.check_images = not opts['skip_image_check']
        self.offer_days = max(1, int(opts['offer_days']))
        self.plan_name = opts['plan']
        self.warnings = []
        summary = []

        for company_cfg in data.COMPANIES:
            if company_cfg['key'] not in keys:
                continue
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n== {company_cfg['name']} =="))
            try:
                with transaction.atomic():
                    summary.append(self._seed_company(company_cfg))
                    if self.dry_run:
                        transaction.set_rollback(True)
            except CommandError as exc:
                self.stdout.write(self.style.ERROR(f"  ✗ {company_cfg['name']}: {exc}"))
                self.warnings.append(f"{company_cfg['name']}: {exc}")
                summary.append({'name': company_cfg['name'], 'error': str(exc)})

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Resumen' + (' (DRY-RUN, sin cambios)' if self.dry_run else '')))
        for row in summary:
            if row.get('error'):
                self.stdout.write(self.style.ERROR(f"  ✗ {row['name']}: {row['error']}"))
            else:
                self.stdout.write(
                    f"  ✓ {row['name']}: {row['products']} productos, {row['offers']} ofertas, "
                    f"{row['token_products']} con descuento por tokens, {row['variants']} variantes, "
                    f"stock total {row['stock']} — {row['address']}"
                )
        if self.warnings:
            self.stdout.write(self.style.WARNING(f'\n{len(self.warnings)} advertencia(s):'))
            for w in self.warnings:
                self.stdout.write(self.style.WARNING(f'  - {w}'))

    # ------------------------------------------------------------------
    def _warn(self, msg):
        self.warnings.append(msg)
        self.stdout.write(self.style.WARNING(f'  ! {msg}'))

    def _seed_company(self, cfg):
        ids = data.company_ids(cfg)
        user = User.objects.select_for_update().filter(pk=cfg['user_id']).first()
        if user is None:
            raise CommandError(f"el usuario {cfg['user_id']} no existe en esta base de datos.")

        # 1) Cédula verificada + rol comerciante
        user.cedula_verified = True
        user.user_type = UserType.MERCHANT
        user.save(update_fields=['cedula_verified', 'user_type'])
        self.stdout.write(f"  ✓ Usuario {user.email}: cedula_verified=True, user_type=MERCHANT")

        # 2) Compañía
        existing = Company.objects.filter(owner=user).first()
        if existing is not None and existing.pk != ids['company']:
            raise CommandError(
                f"el usuario ya posee otra compañía ('{existing.name}', {existing.pk}); no se modifica."
            )
        if Company.objects.filter(name__iexact=cfg['name']).exclude(pk=ids['company']).exists():
            raise CommandError(f"ya existe otra compañía llamada '{cfg['name']}'.")
        category = CompanyCategory.objects.filter(name=cfg['company_category']).first()
        if category is None:
            raise CommandError(f"no existe la CompanyCategory '{cfg['company_category']}'.")

        company, created = Company.objects.update_or_create(
            id=ids['company'],
            defaults={
                'owner': user,
                'name': cfg['name'],
                'category': category,
                'merchant_type': MerchantType.ENTREPRENEUR,
                'image': data.company_logo_key(cfg),
                'gamification_enabled': True,
                'gamification_tokens_per_dollar': cfg['tokens_per_dollar'],
                'main_work_hours': WORK_HOURS,
                'main_work_days': WORK_DAYS,
            },
        )
        self.stdout.write(f"  ✓ Compañía {'creada' if created else 'actualizada'}: {company.name} ({company.pk})")

        # 3) Sucursal principal a pie de calle + ubicación
        store = CompanyStore.objects.filter(company=company, is_main_store=True).first()
        if store is not None and store.pk != ids['store']:
            self._warn(f"{cfg['name']}: ya tenía una sucursal principal ({store.pk}); se reutiliza.")
            store.store_type = StoreType.STREET
            store.is_active = True
            store.save(update_fields=['store_type', 'is_active'])
        else:
            store, _ = CompanyStore.objects.update_or_create(
                id=ids['store'],
                defaults={
                    'company': company,
                    'name': 'Sucursal Principal',
                    'store_type': StoreType.STREET,
                    'is_main_store': True,
                    'is_active': True,
                    'store_img_url': data.store_image_key(cfg),
                    'work_hours': WORK_HOURS,
                    'work_days': WORK_DAYS,
                },
            )
        StoreLocation.objects.update_or_create(
            store=store,
            defaults={
                'mall': None,
                'mall_floor': None,
                'coordinates': Point(float(cfg['lng']), float(cfg['lat']), srid=4326),
                'name': cfg['address'],
                'details': cfg['details'],
            },
        )
        self.stdout.write(f"  ✓ Sucursal a pie de calle: {cfg['address']} ({cfg['lat']}, {cfg['lng']})")

        # 4) Suscripción con gamificación
        self._ensure_subscription(user)

        # 5) Productos
        totals = {'products': 0, 'offers': 0, 'token_products': 0, 'variants': 0, 'stock': 0}
        sub_cache = {}
        valid_until = timezone.now() + datetime.timedelta(days=self.offer_days)
        for spec in cfg['products']:
            self._seed_product(cfg, company, store, spec, sub_cache, valid_until, totals)
        self.stdout.write(
            f"  ✓ {totals['products']} productos ({totals['offers']} con oferta, "
            f"{totals['token_products']} con descuento por tokens)"
        )
        return {'name': cfg['name'], 'address': cfg['address'], **totals}

    # ------------------------------------------------------------------
    def _ensure_subscription(self, user):
        sub = MerchantSubscription.objects.filter(merchant=user).select_related('plan').first()
        target_valid = timezone.now() + datetime.timedelta(days=365)
        if sub is not None and sub.plan.gamification_system:
            if sub.valid_until is None or sub.valid_until < target_valid:
                sub.valid_until = target_valid
                sub.save(update_fields=['valid_until'])
            self.stdout.write(f"  ✓ Suscripción existente conservada: {sub.plan.name}")
            return
        plan = MerchantPlan.objects.filter(name=self.plan_name).first()
        if plan is None:
            self._warn(f"No existe el plan '{self.plan_name}'; no se creó suscripción para {user.email}.")
            return
        MerchantSubscription.objects.update_or_create(
            merchant=user,
            defaults={'plan': plan, 'valid_until': target_valid, 'merchant_type': MerchantType.ENTREPRENEUR},
        )
        self.stdout.write(f"  ✓ Suscripción asignada: {plan.name} (1 año)")

    # ------------------------------------------------------------------
    @staticmethod
    def _build_variants(slug, raw_variants):
        out = []
        for i, v in enumerate(raw_variants, 1):
            item = {'id': f'{slug}-v{i}', 'options': dict(v['options']), 'stock': v['stock']}
            if v.get('price') is not None:
                item['price'] = v['price']
            out.append(item)
        return out

    @staticmethod
    def _build_modifiers(slug, raw_groups):
        out = []
        for gi, g in enumerate(raw_groups, 1):
            group = dict(g)
            group['id'] = f'{slug}-g{gi}'
            group['options'] = [
                {'id': f'{slug}-g{gi}-o{oi}', 'name': o['name'], 'price_delta': o['price_delta'], 'is_available': True}
                for oi, o in enumerate(g['options'], 1)
            ]
            out.append(group)
        return out

    def _resolve_subcategory(self, spec, cache):
        key = (spec['sub'], spec['parent'])
        if key not in cache:
            qs = SubCategory.objects.select_related('parent_category')
            cache[key] = (qs.filter(name=spec['sub'], parent_category__name=spec['parent']).first()
                          or qs.filter(name=spec['sub']).first())
        return cache[key]

    def _seed_product(self, cfg, company, store, spec, sub_cache, offer_valid_until, totals):
        subcategory = self._resolve_subcategory(spec, sub_cache)
        if subcategory is None:
            self._warn(f"{cfg['name']} / {spec['name']}: no existe la subcategoría '{spec['sub']}'; producto omitido.")
            return

        slug = spec['slug']
        variants = self._build_variants(slug, spec['variants'])
        modifiers = self._build_modifiers(slug, spec['modifier_groups'])
        dynamic = validate_and_normalize_product_dynamic_data(
            {
                'selling_unit': spec['selling_unit'],
                'attributes': spec['attributes'],
                'variants': variants,
                'modifier_groups': modifiers,
            },
            subcategory_name=subcategory.name,
            category_name=subcategory.parent_category.name if subcategory.parent_category_id else None,
            base_price=float(spec['price']),
        )

        image_keys = data.product_image_keys(cfg['key'], slug, len(spec['img_prompts']))
        if self.check_images:
            # Solo se enlazan las imágenes que YA existen en el storage; al volver a ejecutar el comando
            # (tras subir las que falten con upload_images.py) se completan automáticamente.
            existing_keys = [key for key in image_keys if storage_manager.file_exists(key)]
            if len(existing_keys) < len(image_keys):
                self._warn(
                    f"{cfg['name']} / {spec['name']}: faltan {len(image_keys) - len(existing_keys)} de "
                    f"{len(image_keys)} imágenes en el storage (se enlazan solo las existentes)."
                )
            image_keys = existing_keys

        product, _ = Product.objects.update_or_create(
            id=data.product_id(cfg['key'], slug),
            defaults={
                'company': company,
                'name': spec['name'],
                'price': spec['price'],
                'description': spec['description'],
                'category': subcategory,
                'discounts_by_tokens_active': bool(spec['tokens']),
                'discounts_data': spec['tokens'] or [],
                'images': image_keys,
                'selling_unit': dynamic['selling_unit'],
                'unit_label': dynamic['unit_label'],
                'allow_fractional_quantity': dynamic['allow_fractional_quantity'],
                'min_order_quantity': dynamic['min_order_quantity'],
                'unit_step': dynamic['unit_step'],
                'attributes': dynamic['attributes'],
                'variants': dynamic['variants'],
                'modifier_groups': dynamic['modifier_groups'],
            },
        )

        if dynamic['variants']:
            stock = sum(int(v.get('stock') or 0) for v in dynamic['variants'])
        else:
            stock = int(spec['stock'] or 0)
        item, _ = InventoryItem.objects.update_or_create(
            id=data.inventory_item_id(cfg['key'], slug),
            defaults={
                'product': product,
                'store': store,
                'stock': stock,
                'paused': False,
                'sold_out_time': None,
                'custom_price': None,
            },
        )

        if spec['offer'] > 0:
            InventoryItemOffer.objects.update_or_create(
                product_item=item,
                defaults={'valid_until': offer_valid_until, 'percentage': int(spec['offer'])},
            )
            totals['offers'] += 1
        else:
            InventoryItemOffer.objects.filter(product_item=item).delete()

        totals['products'] += 1
        totals['variants'] += len(dynamic['variants'])
        totals['stock'] += stock
        if spec['tokens']:
            totals['token_products'] += 1
