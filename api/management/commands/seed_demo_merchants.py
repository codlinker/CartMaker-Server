# -*- coding: utf-8 -*-
"""
Crea (o actualiza) comercios de demostración en Caracas con su catálogo de productos.

Dos conjuntos de datos (`--dataset`):

  * `categories` (por defecto): 1 usuario NUEVO por cada categoría principal (excepto "Otras Categorías"), definido en
    `_category_merchants/`. Cada usuario (user1@cartmaker.app, user2@cartmaker.app, ...) se crea con nombre, apellido,
    cédula venezolana verificada y la contraseña indicada en `--password`; su comercio queda a pie de calle en el este
    de Caracas (Altamira, Chacao, Los Palos Grandes, Los Dos Caminos, La California) con 20 productos.
  * `legacy`: los 4 comercios originales (Soy Techno, EPA, MovilHogar, HERO) de `_demo_merchants_data.py`, que se
    asignan a usuarios YA existentes buscados por su UUID (15 productos c/u).

Idempotente: todos los IDs son deterministas (uuid5), por lo que puede ejecutarse varias veces sin duplicar nada.
Por cada comercio hace:

  1. Usuario: en `categories` lo crea/actualiza (nombre, cédula `V12345678`, `cedula_verified=True`,
     `email_verified=True`, contraseña); en `legacy` busca el usuario existente. En ambos: `user_type = MERCHANT`
     (sin pasar por el flujo biométrico).
  2. Crea/actualiza la `Company` (emprendedor, gamificación de tokens activa) y su sucursal principal a pie de calle
     (`StoreType.STREET`, nunca centro comercial) con `StoreLocation` en una calle de Caracas.
  3. Garantiza una `MerchantSubscription` con un plan que incluya gamificación (Plan Comercio por defecto).
  4. Crea los productos: descripción, precio, atributos de la subcategoría, variantes con stock, personalizaciones
     (`modifier_groups`), descuentos por tokens, 1 foto servida siempre desde disco local
     (`api/static/img/demo_merchants/<company_key>/<slug>.jpg`, versionada en git sin depender de S3),
     su `InventoryItem` con stock y, en parte de ellos, una `InventoryItemOffer` porcentual vigente.

Uso (en el servidor, con las variables de entorno cargadas: `source variables.sh`):

    python manage.py seed_demo_merchants --dry-run                       # simula todo y hace rollback
    python manage.py seed_demo_merchants                                 # 15 comercios, uno por categoría
    python manage.py seed_demo_merchants --only pixel-store zona-fit     # solo algunos comercios
    python manage.py seed_demo_merchants --dataset legacy                # los 4 comercios originales
"""
import datetime
import os
import shutil

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.core.category_schemas import validate_and_normalize_product_dynamic_data
from api.cos import storage_manager
from api.models import (
    AtlasPlusPlan,
    Category,
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
    UserNacionality,
    UserType,
    UserWallet,
)

from . import _category_merchants as category_data
from . import _demo_merchants_data as legacy_data

DATASETS = {'categories': category_data, 'legacy': legacy_data}

WORK_HOURS = {'start': '07:00 AM', 'end': '09:00 PM'}
WORK_DAYS = [0, 1, 2, 3, 4, 5, 6]


class Command(BaseCommand):
    help = ('Crea/actualiza comercios demo en Caracas: por defecto 1 usuario nuevo por categoría con su compañía, '
            'sucursal y 20 productos (--dataset legacy para los 4 comercios originales).')

    def add_arguments(self, parser):
        parser.add_argument('--dataset', choices=sorted(DATASETS), default='categories',
                            help="Catálogo a sembrar: 'categories' (por defecto) o 'legacy'.")
        parser.add_argument('--only', nargs='+', help='Procesa solo estos comercios (por su key).')
        parser.add_argument('--password', default=category_data.DEFAULT_PASSWORD,
                            help='Contraseña de los usuarios creados por el dataset categories.')
        parser.add_argument('--dry-run', action='store_true', help='Simula todo y revierte la transacción.')
        parser.add_argument('--skip-image-check', action='store_true',
                            help='No verifica en S3 que existan las imágenes referenciadas.')
        parser.add_argument('--offer-days', type=int, default=90,
                            help='Días de vigencia de las ofertas porcentuales a partir de hoy (por defecto 90).')
        parser.add_argument('--plan', default='Plan Comercio',
                            help='Nombre del plan a asignar si el usuario no tiene uno con gamificación.')

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        self.data = data = DATASETS[opts['dataset']]
        if opts['dataset'] == 'categories':
            self._sync_local_demo_static_images()
            db_cats = list(
                Category.objects.exclude(name__in=category_data.EXCLUDED_CATEGORIES)
                .prefetch_related('subcategories')
                .order_by('id')
            )
            companies_list = category_data.companies_for_db_categories(db_cats)
        else:
            companies_list = list(data.COMPANIES)
        all_keys = [c['key'] for c in companies_list]
        unknown = sorted(set(opts.get('only') or []) - set(all_keys))
        if unknown:
            raise CommandError(f"Comercio(s) desconocido(s) en --dataset {opts['dataset']}: {', '.join(unknown)}. "
                               f"Opciones: {', '.join(all_keys)}")
        keys = set(opts.get('only') or all_keys)
        self.dry_run = bool(opts['dry_run'])
        self.check_images = not opts['skip_image_check']
        self.offer_days = max(1, int(opts['offer_days']))
        self.plan_name = opts['plan']
        self.password = opts['password']
        self.warnings = []
        summary = []

        for company_cfg in companies_list:
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
                    f"  ✓ {row['name']} ({row['email']}): {row['products']} productos, {row['offers']} ofertas, "
                    f"{row['token_products']} con descuento por tokens, {row['variants']} variantes, "
                    f"stock total {row['stock']} — {row['address']}"
                )
        if self.warnings:
            self.stdout.write(self.style.WARNING(f'\n{len(self.warnings)} advertencia(s):'))
            for w in self.warnings:
                self.stdout.write(self.style.WARNING(f'  - {w}'))

    # ------------------------------------------------------------------
    def _sync_local_demo_static_images(self):
        """
        Sincroniza `api/static/img/demo_merchants` hacia `STATIC_ROOT/img/demo_merchants` (igual que hace
        `fill_default_bd.py` con `api/static/img/categories`) para que las imágenes locales del repositorio
        se sirvan siempre desde `${DOMAIN}/static/img/demo_merchants/...` sin pasar por S3.
        """
        try:
            src_dir = os.path.join(settings.BASE_DIR, 'api', 'static', 'img', 'demo_merchants')
            static_root = getattr(settings, 'STATIC_ROOT', None)
            if static_root and os.path.isdir(src_dir):
                dst_dir = os.path.join(str(static_root), 'img', 'demo_merchants')
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        except Exception as exc:
            self._warn(f'No se pudo sincronizar staticfiles/img/demo_merchants: {exc}')

    def _warn(self, msg):
        self.warnings.append(msg)
        self.stdout.write(self.style.WARNING(f'  ! {msg}'))

    def _seed_company(self, cfg):
        data = self.data
        ids = data.company_ids(cfg)
        if 'user' in cfg:
            # 1a) Dataset `categories`: usuario nuevo con identidad verificada (crea o actualiza por email)
            user = self._ensure_demo_user(cfg['user'])
        else:
            # 1b) Dataset `legacy`: usuario existente buscado por UUID; cédula verificada + rol comerciante
            user = User.objects.select_for_update().filter(pk=cfg['user_id']).first()
            if user is None:
                raise CommandError(f"el usuario {cfg['user_id']} no existe en esta base de datos.")
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
        category_names = cfg['company_category']
        if isinstance(category_names, str):
            category_names = [category_names]
        category = None
        for category_name in category_names:
            category = CompanyCategory.objects.filter(name=category_name).first()
            if category is not None:
                break
        if category is None:
            raise CommandError(f"no existe ninguna CompanyCategory de: {', '.join(category_names)}.")

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
        return {'name': cfg['name'], 'address': cfg['address'], 'email': user.email, **totals}

    # ------------------------------------------------------------------
    def _ensure_demo_user(self, spec):
        """Crea o actualiza (por email) el usuario demo con identidad verificada y la contraseña indicada."""
        email = User.objects.normalize_email(spec['email'])
        user = User.objects.select_for_update().filter(email__iexact=email).first()

        cedula_clash = User.objects.filter(cedula_number__iexact=spec['cedula'])
        if user is not None:
            cedula_clash = cedula_clash.exclude(pk=user.pk)
        clash = cedula_clash.first()
        if clash is not None:
            raise CommandError(f"la cédula {spec['cedula']} ya pertenece a otro usuario ({clash.email}).")

        profile = {
            'first_name': spec['first_name'],
            'last_name': spec['last_name'],
            'cedula_number': spec['cedula'],
            'nacionality': UserNacionality.VENEZOLANO,
            'birth_date': spec['birth_date'],
            'gender': spec['gender'],
            'cedula_verified': True,
            'email_verified': True,
            'user_type': UserType.MERCHANT,
            'is_active': True,
        }
        if user is None:
            desired_uid = self.data.demo_uuid('user', email)
            if not User.objects.filter(pk=desired_uid).exists():
                profile['id'] = desired_uid
            user = User.objects.create_user(email, password=self.password, **profile)
            action = 'creado'
        else:
            for field, value in profile.items():
                setattr(user, field, value)
            user.set_password(self.password)
            user.save()
            action = 'actualizado'
        UserWallet.objects.get_or_create(user=user)
        AtlasPlusPlan.objects.get_or_create(user=user)
        self.stdout.write(
            f"  ✓ Usuario {action}: {user.email} — {user.first_name} {user.last_name}, "
            f"C.I. {user.cedula_number} (verificada), user_type=MERCHANT"
        )
        return user

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
        data = self.data
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
            existing_keys = [key for key in image_keys if storage_manager.file_exists(key)]
            if len(existing_keys) < len(image_keys):
                if not existing_keys and getattr(subcategory, 'img_url', None):
                    existing_keys = [subcategory.img_url.lstrip('/')]
                self._warn(
                    f"{cfg['name']} / {spec['name']}: faltan {len(image_keys) - len(existing_keys)} de "
                    f"{len(image_keys)} imágenes locales/storage."
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
