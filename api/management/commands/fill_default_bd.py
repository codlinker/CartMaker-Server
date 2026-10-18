import json
import os
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from api.core.category_schemas import (
    CATALOGO_ESTRUCTURA,
    get_subcategory_schema,
)
from api.models import (
    Announcement,
    BillingIssuerType,
    BillingTaxRegime,
    Category,
    CompanyCategory,
    Mall,
    MerchantPlan,
    Product,
    SubCategory,
    SystemConfig,
    User,
)

class Command(BaseCommand):
    help = "Puebla la base de datos con registros por defecto optimizados y sincronizados sin duplicar datos."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING('Iniciando carga de datos por defecto...'))
        
        self._poblar_system_config()
        self._poblar_categorias()
        self._poblar_planes()
        self._poblar_anuncios()
        self._poblar_malls()
        self._poblar_categorias_empresa()

        self.stdout.write(self.style.SUCCESS('Carga de datos finalizada exitosamente.'))

    def _poblar_system_config(self):
        self.stdout.write("Verificando SystemConfig (Tarifas Atlas Plus y Datos Fiscales SENIAT)...")
        defaults = {
            'platinum_min_rating_promedy_requirement': Decimal('4.50'),
            'platinum_min_sells_per_month_requirement': 100,
            'atlas_plus_price_usd': Decimal('3.99'),
            'atlas_plus_daily_limit': 30,
            'atlas_free_daily_limit': 7,
            'atlas_anonymous_daily_limit': 3,
            'billing_issuer_type': BillingIssuerType.PERSONAL,
            'billing_issuer_name': 'ATREYUS DE JESUS REYES ALVAREZ',
            'billing_trade_name': 'CartMaker',
            'billing_issuer_rif': 'V-30222103-7',
            'billing_issuer_cedula': 'V-30.222.103',
            'billing_fiscal_address': (
                'CTRA NACIONAL GUATIRE-GUARENAS CASA TOWN HOUSE NRO C-11 '
                'CONJUNTO RESIDENCIAL EL REFUGIO GUATIRE MIRANDA ZONA POSTAL 1221'
            ),
            'billing_seniat_region': (
                'GERENCIA REGIONAL DE TRIBUTOS INTERNOS REGIÓN CAPITAL / '
                'SECTOR GUARENAS / GUATIRE'
            ),
            'billing_rif_certificate_number': '202401P0000063963955',
            'billing_tax_regime': BillingTaxRegime.EXENTO_NO_SUJETO,
            'billing_iva_percentage': Decimal('0.00'),
            'billing_series_prefix': 'A',
            'billing_control_prefix': '00',
            'billing_service_concept': (
                'Servicios de Programación, Procesamiento de Datos y Suscripción Mensual '
                'al Asistente de Inteligencia Artificial Atlas Plus (CartMaker)'
            ),
        }

        config = SystemConfig.objects.order_by('-creation').first()
        if not config:
            config = SystemConfig.objects.create(**defaults)
            self.stdout.write(
                self.style.SUCCESS(
                    '  [+] SystemConfig creado (Atlas Plus: 3,99$ | Límites: 30 Plus / 7 Gratis / 3 Anónimo | RIF: V-30222103-7).'
                )
            )
        else:
            updated_fields = []
            # Sincronizar tarifas y límites de Atlas Plus
            for field in (
                'atlas_plus_price_usd',
                'atlas_plus_daily_limit',
                'atlas_free_daily_limit',
                'atlas_anonymous_daily_limit',
            ):
                if getattr(config, field) != defaults[field]:
                    setattr(config, field, defaults[field])
                    updated_fields.append(field)

            # Garantizar datos fiscales SENIAT si estaban vacíos
            for fiscal_field in (
                'billing_issuer_type',
                'billing_issuer_name',
                'billing_trade_name',
                'billing_issuer_rif',
                'billing_issuer_cedula',
                'billing_fiscal_address',
                'billing_seniat_region',
                'billing_rif_certificate_number',
                'billing_tax_regime',
                'billing_series_prefix',
                'billing_control_prefix',
                'billing_service_concept',
            ):
                if not getattr(config, fiscal_field, None):
                    setattr(config, fiscal_field, defaults[fiscal_field])
                    updated_fields.append(fiscal_field)

            if updated_fields:
                config.save(update_fields=updated_fields)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [+] SystemConfig actualizado ({', '.join(updated_fields)})."
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING('  [-] Sin cambios en SystemConfig. Ya tiene los parámetros oficiales.')
                )

        cache.delete("cartmaker:global:system_config")

    def _bulk_create_if_not_exists(self, model, data_list, unique_field):
        """
        Método helper centralizado. Recibe el modelo, la lista de diccionarios 
        con la data, y el campo que define si el registro ya existe (ej: 'name').
        """
        # Obtenemos los valores existentes de la BD en un set (búsqueda O(1))
        existing_values = set(model.objects.values_list(unique_field, flat=True))
        
        # Filtramos solo los registros que NO existen en la base de datos
        objects_to_create = [
            model(**data) for data in data_list if data[unique_field] not in existing_values
        ]
        
        if objects_to_create:
            model.objects.bulk_create(objects_to_create)
            self.stdout.write(self.style.SUCCESS(f'  [+] Se crearon {len(objects_to_create)} registros en {model.__name__}.'))
        else:
            self.stdout.write(self.style.WARNING(f'  [-] Sin cambios en {model.__name__}. Los registros ya existen.'))

    def _poblar_categorias_empresa(self):
        self.stdout.write("Verificando CompanyCategories (Rubros comerciales)...")
        
        company_categories_data = [
            # --- Sector Automotriz ---
            {'name': 'Repuestos Automotrices'},
            {'name': 'Servicios Automotrices'},
            
            # --- Alimentación y Bebidas ---
            {'name': 'Restaurante'},
            {'name': 'Supermercado'},
            {'name': 'Panadería y Pastelería'},
            {'name': 'Licorería'},
            
            # --- Salud, Belleza y Cuidado ---
            {'name': 'Farmacia'},
            {'name': 'Salud y Belleza'},
            {'name': 'Mascotas'},
            {'name': 'Lavandería'},
            
            # --- Tecnología y Hogar ---
            {'name': 'Tecnología'},
            {'name': 'Electrodomésticos'},
            {'name': 'Hogar y Muebles'},
            {'name': 'Ferretería'},
            {'name': 'Construcción y Materiales'},
            
            # --- Comercio y Retail ---
            {'name': 'Moda y Ropa'},
            {'name': 'Joyería y Relojería'},
            {'name': 'Juguetería'},
            {'name': 'Deportes'},
            {'name': 'Papelería y Oficina'},
            {'name': 'Floristería y Jardinería'},
            {'name': 'Arte y Artesanías'},
            
            # --- Servicios Profesionales y Financieros ---
            {'name': 'Servicios Financieros'},
            {'name': 'Inmobiliaria'},
            {'name': 'Educación'},
            
            # --- Logística, Turismo y Eventos ---
            {'name': 'Transporte y Logística'},
            {'name': 'Turismo y Hotelería'},
            {'name': 'Entretenimiento y Eventos'},
            {'name': 'Agroindustria y Campo'},
        ]
        
        self._bulk_create_if_not_exists(CompanyCategory, company_categories_data, unique_field='name')

    def _poblar_categorias(self):
        import shutil
        self.stdout.write("Verificando Categories y SubCategories desde CATALOGO_ESTRUCTURA...")

        # 0. Sincronizar imágenes físicas de api/static/img/categories hacia STATIC_ROOT (staticfiles/img/categories)
        try:
            src_cat_img_dir = os.path.join(settings.BASE_DIR, 'api', 'static', 'img', 'categories')
            static_root = getattr(settings, 'STATIC_ROOT', None)
            if static_root and os.path.exists(src_cat_img_dir):
                dst_cat_img_dir = os.path.join(str(static_root), 'img', 'categories')
                os.makedirs(dst_cat_img_dir, exist_ok=True)
                shutil.copytree(src_cat_img_dir, dst_cat_img_dir, dirs_exist_ok=True)
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"  [!] No se pudo sincronizar staticfiles/img/categories: {exc}"))

        official_cat_names_lower = {
            entry['categoria'].strip().lower() for entry in CATALOGO_ESTRUCTURA
        }
        official_sub_names_lower = {
            sub['nombre'].strip().lower()
            for entry in CATALOGO_ESTRUCTURA
            for sub in entry.get('subcategorias', [])
        }

        created_cats = 0
        renamed_cats = 0
        updated_cats = 0
        created_subs = 0
        renamed_subs = 0
        updated_subs = 0
        official_categories_by_id = set()
        official_categories_list = []
        official_subcategories_by_id = set()
        official_subcategories_list = []

        # 1. Sincronizar todas las Categorías y Subcategorías definidas en CATALOGO_ESTRUCTURA
        for cat_entry in CATALOGO_ESTRUCTURA:
            cat_name = cat_entry['categoria']
            cat_img = cat_entry['imagen']
            sub_names_in_entry = [s['nombre'] for s in cat_entry.get('subcategorias', [])]

            existing_cats = list(Category.objects.filter(name__iexact=cat_name).order_by('id'))
            if not existing_cats:
                # Si la categoría fue renombrada en CATALOGO_ESTRUCTURA, localizarla por img_url o subcategorías hijas
                candidate_cat = (
                    Category.objects.exclude(id__in=official_categories_by_id)
                    .filter(img_url=cat_img)
                    .order_by('id')
                    .first()
                )
                if not candidate_cat and sub_names_in_entry:
                    candidate_cat = (
                        Category.objects.exclude(id__in=official_categories_by_id)
                        .filter(subcategories__name__in=sub_names_in_entry)
                        .order_by('id')
                        .first()
                    )
                if candidate_cat and candidate_cat.name.strip().lower() not in official_cat_names_lower:
                    candidate_cat.name = cat_name
                    candidate_cat.img_url = cat_img
                    candidate_cat.save(update_fields=['name', 'img_url'])
                    existing_cats = [candidate_cat]
                    renamed_cats += 1

            if existing_cats:
                cat_obj = existing_cats[0]
                if len(existing_cats) > 1:
                    for dup_cat in existing_cats[1:]:
                        SubCategory.objects.filter(parent_category=dup_cat).update(parent_category=cat_obj)
                        for u in User.objects.filter(preferred_categories=dup_cat):
                            u.preferred_categories.add(cat_obj)
                            u.preferred_categories.remove(dup_cat)
                        dup_cat.delete()

                cat_changed_fields = []
                if cat_obj.name != cat_name:
                    cat_obj.name = cat_name
                    cat_changed_fields.append('name')
                if cat_obj.img_url != cat_img:
                    cat_obj.img_url = cat_img
                    cat_changed_fields.append('img_url')
                if cat_changed_fields:
                    cat_obj.save(update_fields=cat_changed_fields)
                    updated_cats += 1
            else:
                cat_obj = Category.objects.create(name=cat_name, img_url=cat_img)
                created_cats += 1

            official_categories_by_id.add(cat_obj.id)
            official_categories_list.append(cat_obj)

            for sub_entry in cat_entry['subcategorias']:
                sub_name = sub_entry['nombre']
                sub_img = sub_entry['imagen']
                schema_cfg = get_subcategory_schema(
                    subcategory_name=sub_name,
                    parent_category_name=cat_name,
                )

                existing_subs = list(SubCategory.objects.filter(name__iexact=sub_name).order_by('id'))
                if not existing_subs:
                    candidate_sub = (
                        SubCategory.objects.exclude(id__in=official_subcategories_by_id)
                        .filter(img_url=sub_img)
                        .order_by('id')
                        .first()
                    )
                    if candidate_sub and candidate_sub.name.strip().lower() not in official_sub_names_lower:
                        candidate_sub.name = sub_name
                        candidate_sub.parent_category = cat_obj
                        candidate_sub.img_url = sub_img
                        candidate_sub.schema_config = schema_cfg
                        candidate_sub.save(update_fields=['name', 'parent_category', 'img_url', 'schema_config'])
                        existing_subs = [candidate_sub]
                        renamed_subs += 1

                if existing_subs:
                    sub_obj = existing_subs[0]
                    if len(existing_subs) > 1:
                        dup_ids = [dup.id for dup in existing_subs[1:]]
                        Product.objects.filter(category_id__in=dup_ids).update(category=sub_obj)
                        SubCategory.objects.filter(id__in=dup_ids).delete()

                    changed_fields = []
                    if sub_obj.name != sub_name:
                        sub_obj.name = sub_name
                        changed_fields.append('name')
                    if sub_obj.parent_category_id != cat_obj.id:
                        sub_obj.parent_category = cat_obj
                        changed_fields.append('parent_category')
                    if sub_obj.img_url != sub_img:
                        sub_obj.img_url = sub_img
                        changed_fields.append('img_url')
                    if sub_obj.schema_config != schema_cfg:
                        sub_obj.schema_config = schema_cfg
                        changed_fields.append('schema_config')
                    if changed_fields:
                        sub_obj.save(update_fields=changed_fields)
                        updated_subs += 1
                else:
                    sub_obj = SubCategory.objects.create(
                        name=sub_name,
                        parent_category=cat_obj,
                        img_url=sub_img,
                        schema_config=schema_cfg,
                    )
                    created_subs += 1

                official_subcategories_by_id.add(sub_obj.id)
                official_subcategories_list.append(sub_obj)

        # 2. Eliminar cualquier SubCategoría que ya no exista en CATALOGO_ESTRUCTURA
        fallback_sub = official_subcategories_list[-1] if official_subcategories_list else None
        obsolete_subs = list(
            SubCategory.objects.exclude(id__in=official_subcategories_by_id).select_related('parent_category')
        )
        deleted_subs = 0
        for old_sub in obsolete_subs:
            target_sub = None
            if old_sub.parent_category_id in official_categories_by_id:
                target_sub = (
                    SubCategory.objects.filter(
                        parent_category_id=old_sub.parent_category_id,
                        id__in=official_subcategories_by_id,
                    )
                    .order_by('id')
                    .first()
                )
            if target_sub is None:
                target_sub = fallback_sub
            if target_sub is not None:
                Product.objects.filter(category=old_sub).update(category=target_sub)
            old_sub.delete()
            deleted_subs += 1

        # 3. Eliminar cualquier Categoría principal que ya no exista en CATALOGO_ESTRUCTURA
        fallback_cat = official_categories_list[-1] if official_categories_list else None
        obsolete_cats = list(Category.objects.exclude(id__in=official_categories_by_id))
        deleted_cats = 0
        for old_cat in obsolete_cats:
            if fallback_cat and fallback_cat.id != old_cat.id:
                SubCategory.objects.filter(parent_category=old_cat).update(parent_category=fallback_cat)
                for u in User.objects.filter(preferred_categories=old_cat):
                    u.preferred_categories.add(fallback_cat)
                    u.preferred_categories.remove(old_cat)
            old_cat.delete()
            deleted_cats += 1

        # 4. Invalidar todas las llaves de caché de categorías y buscador en Redis
        cache.delete_many([
            "cartmaker:global:categories",
            "cartmaker:global:categories:v2",
            "cartmaker:global:search",
        ])
        self.stdout.write(
            self.style.SUCCESS(
                f"  [+] Categorías listas (creadas: {created_cats}, renombradas: {renamed_cats}, "
                f"actualizadas: {updated_cats}, obsoletas eliminadas: {deleted_cats}) | "
                f"SubCategorías listas (creadas: {created_subs}, renombradas: {renamed_subs}, "
                f"actualizadas: {updated_subs}, obsoletas eliminadas: {deleted_subs})."
            )
        )

    def _poblar_planes(self):
        self.stdout.write("Verificando MerchantPlans...")
        plans_data = [
            {
                'name': "Plan Emprendo",
                'price': Decimal(15.0),
                'inventory_capacity': 25,
                'products_registration_with_ia': True,
                'digital_performance_analytics': True,
                'short_description_html': "Diseñado para <b>emprendedores</b> que suelen vender de forma informal por redes sociales.",
                'large_description_html': "Dile adiós al «vendedor de DM» para convertirte en un comercio con una <b>vitrina digital estructurada</b>. Podrás organizar tus ofertas sin barreras técnicas complicadas.",
                'card_bg_color': "#E7E6ED",
                'label_bg_color': "#9E8ED9",
                'label_border_color': "#6D49F2",
                'label_text_color': "#F2F2F2"
            },
            {
                'name': "Plan Comercio",
                'price': Decimal(35.0),
                'inventory_capacity': 60,
                'products_registration_with_ia': True,
                'profile_histories': True,
                'gamification_system': True,
                'gamification_analytics': True,
                'digital_performance_analytics': True,
                'is_popular': True,
                'short_description_html': "Diseñado para negocios con <b>clientes recurrentes</b> que necesitan una <b>plataforma robusta</b> para escalar sus ventas.",
                'large_description_html': "Convierte tu catálogo en una herramienta de marketing activo mediante <b>historias</b> y <b>gamificación</b> para potenciar la lealtad y el rendimiento de tu marca en el mercado.",
                'card_bg_color': "#DCD7EF",
                'label_bg_color': "#6D49F2",
                'label_border_color': "#F2F2F2",
                'label_text_color': "#F2F2F2"
            },
            {
                'name': "Plan Franquicia",
                'price': Decimal(165.0),
                'inventory_capacity': 100,
                'products_registration_with_ia': True,
                'profile_histories': True,
                'gamification_system': True,
                'gamification_analytics': True,
                'digital_performance_analytics': True,
                'clients_behavior_analytics': True,
                'operative_management_analytics': True,
                'company_branches': True,
                'company_employees': True,
                'short_description_html': 'Construido para <b>marcas consolidadas</b> que ya no se preocupan solo por "vender", sino por "<b>controlar</b>" lo que venden en <b>diferentes puntos geográficos</b>.',
                'large_description_html': "Diseñado para directores de negocio que necesitan una visión de 360 grados de su operación, gestionando la complejidad de <b>múltiples inventarios</b> y logística distribuida desde un solo centro de mando, asegurando que la experiencia de marca sea la misma en cada <b>sucursal</b>.",
                'card_bg_color': "#FFFFF2",
                'label_bg_color': "#6D49F2",
                'label_border_color': "#F2ED49",
                'label_text_color': "#F2ED49",
                'requires_business': True
            }
        ]
        self._bulk_create_if_not_exists(MerchantPlan, plans_data, unique_field='name')

    def _poblar_anuncios(self):
        self.stdout.write("Verificando Announcements...")
        announcements_data = [
            {'banner_img': 'static/img/third_banner_test.png', 'navigate_to': 'home'},
            {'banner_img': 'static/img/2_banner_test.png', 'navigate_to': 'home'},
            {'banner_img': 'static/img/first_banner_test.png', 'navigate_to': 'home'}
        ]
        self._bulk_create_if_not_exists(Announcement, announcements_data, unique_field='banner_img')

    def _poblar_malls(self):
        self.stdout.write("Verificando Malls desde JSON...")
        json_path = os.path.join(settings.BASE_DIR, 'api', 'static', 'json', 'malls.json')
        
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f'  [!] Archivo JSON no encontrado: {json_path}'))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            malls_data = json.load(f)

        existing_malls = set(Mall.objects.values_list('name', flat=True))
        malls_to_create = []

        for estado, ciudades in malls_data.items():
            for ciudad, malls in ciudades.items():
                for mall in malls:
                    # Si el nombre ya existe en la BD, lo saltamos automáticamente
                    if mall['name'] in existing_malls:
                        continue
                    
                    if mall.get('lat') and mall.get('lng'):
                        try:
                            lng = float(mall['lng'])
                            lat = float(mall['lat'])
                            ubicacion = Point(lng, lat, srid=4326)
                            
                            malls_to_create.append(
                                Mall(
                                    name=mall['name'],
                                    coordinates=ubicacion,
                                    floors_quantity=mall['floors_quantity'],
                                    img_url=mall['img_url']
                                )
                            )
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"  [!] Error en coordenadas para: {mall['name']}. Saltando..."))
                            continue

        if malls_to_create:
            Mall.objects.bulk_create(malls_to_create)
            self.stdout.write(self.style.SUCCESS(f'  [+] Se crearon {len(malls_to_create)} registros en Mall.'))
        else:
            self.stdout.write(self.style.WARNING('  [-] Sin cambios en Mall. Los registros ya existen o no tienen coordenadas válidas.'))