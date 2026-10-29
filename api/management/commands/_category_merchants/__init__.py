# -*- coding: utf-8 -*-
"""
Catálogo demo "un comercio por categoría" para `python manage.py seed_demo_merchants`.

Crea 1 usuario NUEVO por cada categoría principal de `CATALOGO_ESTRUCTURA` (excepto "Otras Categorías"), cada uno
con su compañía (emprendedor, gamificación activa), una sucursal principal a pie de calle en el este de Caracas
(Altamira, Chacao, Los Palos Grandes, Los Dos Caminos, La California y la Av. Francisco de Miranda) y 20 productos.

  * Usuarios: user1@cartmaker.app ... user15@cartmaker.app, con nombre, apellido, cédula venezolana (formato
    `V12345678`, el mismo que guarda el flujo de verificación) y `cedula_verified=True`.
  * Los productos de cada categoría viven en su propio módulo (`alimentos_y_bebidas.py`, `tecnologia.py`, ...) y
    exponen una lista `PRODUCTS` construida con los helpers de `_helpers.py`.
  * Todos los IDs (compañía, sucursal, producto, ítem de inventario) son DETERMINISTAS (uuid5 con un namespace propio,
    distinto del catálogo demo original), por lo que el comando es idempotente y las claves de S3 de las imágenes
    coinciden siempre con las que sube `scripts/demo_merchants/upload_images.py --dataset categories`.

Las coordenadas son puntos aproximados sobre vías reales de cada zona (no verificados contra OSM).
"""
import datetime
import importlib
import uuid

CATEGORY_NAMESPACE = uuid.UUID('3d0f6a52-8c1e-4b7a-9f25-6e4c1d2b7a90')

# Contraseña por defecto de todos los usuarios demo (se puede sobrescribir con --password).
DEFAULT_PASSWORD = 'Zero=25z'
EMAIL_DOMAIN = 'cartmaker.app'
PRODUCTS_PER_COMPANY = 20

# Categoría principal excluida a propósito.
EXCLUDED_CATEGORIES = ('Otras Categorías',)


def demo_uuid(*parts) -> uuid.UUID:
    return uuid.uuid5(CATEGORY_NAMESPACE, 'cartmaker-category-demo:' + ':'.join(str(p) for p in parts))


def _user(n, first_name, last_name, cedula, gender, birth_date):
    """`gender`: 0 = Masculino, 1 = Femenino (UserGender). `birth_date`: 'YYYY-MM-DD'."""
    return {
        'email': f'user{n}@{EMAIL_DOMAIN}',
        'first_name': first_name,
        'last_name': last_name,
        'cedula': cedula,
        'gender': gender,
        'birth_date': datetime.date.fromisoformat(birth_date),
    }


_LOGO = ('flat vector logo icon for {what}, {colors}, centered, plain light background, minimal and modern, '
         'no text, no letters')
_STORE = ('realistic daytime photograph of {what} at street level on a tree lined street in the east of Caracas '
          '(Chacao / Altamira area), Venezuela, glass storefront, sign without readable text, no people in focus')

# ----------------------------------------------------------------------------------------------------------------------
# Comercios: (módulo de productos, metadatos). El orden define el número de usuario (user1, user2, ...).
# `company_category` es una lista de preferencia: se usa la primera CompanyCategory que exista en la BD.
# ----------------------------------------------------------------------------------------------------------------------
_COMPANY_SPECS = [
    ('alimentos_y_bebidas', {
        'key': 'bodegon-altamira',
        'name': 'Bodegón Altamira Gourmet',
        'product_category': 'Alimentos y Bebidas',
        'company_category': ['Bodegón y Abasto', 'Supermercado'],
        'user': _user(1, 'María Fernanda', 'González', 'V17845231', 1, '1986-03-14'),
        'zone': 'Altamira',
        'address': '3ra Transversal de Altamira, Chacao, Caracas',
        'details': 'Bodegón a pie de calle en la 3ra Transversal de Altamira, cerca de la Av. San Juan Bosco.',
        'lat': 10.4990, 'lng': -66.8472,
        'tokens_per_dollar': 3,
        'logo_prompt': _LOGO.format(what='a gourmet grocery store, a shopping basket with a baguette and a wine bottle',
                                    colors='deep green and gold'),
        'store_prompt': _STORE.format(what='a small gourmet grocery store (bodegón) with shelves of imported products'),
    }),
    ('restaurantes', {
        'key': 'sabor-avila',
        'name': 'Sabor del Ávila',
        'product_category': 'Restaurantes y Comida Preparada',
        'company_category': ['Restaurante', 'Arepera, Empanadas y Desayunos'],
        'user': _user(2, 'José Gregorio', 'Rodríguez', 'V15632874', 0, '1982-07-22'),
        'zone': 'Los Palos Grandes',
        'address': '2da Avenida de Los Palos Grandes, Chacao, Caracas',
        'details': 'Restaurante criollo a pie de calle en la 2da Avenida de Los Palos Grandes, con terraza.',
        'lat': 10.5005, 'lng': -66.8440,
        'tokens_per_dollar': 4,
        'logo_prompt': _LOGO.format(what='a Venezuelan food restaurant, a golden arepa in front of a green mountain',
                                    colors='warm orange, green and cream'),
        'store_prompt': _STORE.format(what='a cozy Venezuelan restaurant with an open terrace and wooden tables'),
    }),
    ('tecnologia', {
        'key': 'pixel-store',
        'name': 'Pixel Store Caracas',
        'product_category': 'Tecnología y Electrónica',
        'company_category': ['Tecnología', 'Electrodomésticos'],
        'user': _user(3, 'Daniel Alejandro', 'Pérez', 'V24518963', 0, '1995-11-03'),
        'zone': 'Chacao',
        'address': 'Av. Francisco de Miranda, Chacao, Caracas',
        'details': 'Tienda de tecnología a pie de calle sobre la Av. Francisco de Miranda, a pasos del metro de Chacao.',
        'lat': 10.4918, 'lng': -66.8547,
        'tokens_per_dollar': 2,
        'logo_prompt': _LOGO.format(what='a technology store, a stylized pixel square forming a play button',
                                    colors='electric violet and cyan'),
        'store_prompt': _STORE.format(what='a modern electronics store with laptops, phones and headphones on display'),
    }),
    ('ropa_y_accesorios', {
        'key': 'moda-urbana',
        'name': 'Moda Urbana Chacao',
        'product_category': 'Ropa y Accesorios',
        'company_category': ['Moda y Ropa'],
        'user': _user(4, 'Andreína Carolina', 'Hernández', 'V20987451', 1, '1991-05-27'),
        'zone': 'Chacao',
        'address': 'Calle Cecilio Acosta, Chacao, Caracas',
        'details': 'Boutique a pie de calle en la Calle Cecilio Acosta, frente al Mercado de Chacao.',
        'lat': 10.4936, 'lng': -66.8541,
        'tokens_per_dollar': 3,
        'logo_prompt': _LOGO.format(what='an urban fashion boutique, a minimalist clothes hanger with a sneaker',
                                    colors='black and coral'),
        'store_prompt': _STORE.format(what='a trendy clothing boutique with mannequins in the window'),
    }),
    ('salud_y_belleza', {
        'key': 'glow-beauty',
        'name': 'Glow Beauty Bar',
        'product_category': 'Salud y Belleza',
        'company_category': ['Salud y Belleza', 'Farmacia'],
        'user': _user(5, 'Valentina Isabel', 'Rojas', 'V26741358', 1, '1997-01-09'),
        'zone': 'Los Palos Grandes',
        'address': '4ta Transversal de Los Palos Grandes, Chacao, Caracas',
        'details': 'Tienda de belleza y cuidado personal a pie de calle en la 4ta Transversal de Los Palos Grandes.',
        'lat': 10.5022, 'lng': -66.8428,
        'tokens_per_dollar': 4,
        'logo_prompt': _LOGO.format(what='a beauty and skincare shop, a shining drop with a small sparkle',
                                    colors='blush pink and rose gold'),
        'store_prompt': _STORE.format(what='a bright beauty and skincare shop with cosmetics shelves'),
    }),
    ('hogar', {
        'key': 'casa-avila',
        'name': 'Casa Ávila Deco',
        'product_category': 'Hogar, Muebles y Jardín',
        'company_category': ['Hogar y Muebles'],
        'user': _user(6, 'Luis Eduardo', 'Martínez', 'V13274586', 0, '1979-09-18'),
        'zone': 'La California',
        'address': 'Calle California, La California Norte, Sucre, Caracas',
        'details': 'Showroom de hogar y decoración a pie de calle en La California Norte.',
        'lat': 10.4902, 'lng': -66.8152,
        'tokens_per_dollar': 2,
        'logo_prompt': _LOGO.format(what='a home decor store, a simple house outline with a leaf inside',
                                    colors='terracotta and sage green'),
        'store_prompt': _STORE.format(what='a home decor and furniture showroom with sofas, lamps and plants'),
    }),
    ('ferreteria', {
        'key': 'ferre-dos-caminos',
        'name': 'Ferretería Dos Caminos',
        'product_category': 'Ferretería y Construcción',
        'company_category': ['Ferretería', 'Construcción y Materiales'],
        'user': _user(7, 'Carlos Enrique', 'Medina', 'V11853672', 0, '1976-12-02'),
        'zone': 'Los Dos Caminos',
        'address': 'Av. Sucre de Los Dos Caminos, Sucre, Caracas',
        'details': 'Ferretería a pie de calle sobre la Av. Sucre de Los Dos Caminos.',
        'lat': 10.4985, 'lng': -66.8290,
        'tokens_per_dollar': 2,
        'logo_prompt': _LOGO.format(what='a hardware store, a hammer and a screwdriver crossed inside a circle',
                                    colors='safety yellow and charcoal'),
        'store_prompt': _STORE.format(what='a neighborhood hardware store with tools and paint cans displayed'),
    }),
    ('carros_y_motos', {
        'key': 'autopartes-california',
        'name': 'AutoPartes La California',
        'product_category': 'Carros, Motos y Otros',
        'company_category': ['Repuestos Automotrices', 'Servicios Automotrices'],
        'user': _user(8, 'Ricardo Antonio', 'Salazar', 'V16349825', 0, '1984-04-30'),
        'zone': 'La California',
        'address': 'Av. Francisco de Miranda, La California Norte, Sucre, Caracas',
        'details': 'Tienda de repuestos y accesorios a pie de calle sobre la Av. Francisco de Miranda, en La California Norte.',
        'lat': 10.4884, 'lng': -66.8168,
        'tokens_per_dollar': 2,
        'logo_prompt': _LOGO.format(what='an auto parts store, a gear combined with a car wheel rim',
                                    colors='racing red and steel gray'),
        'store_prompt': _STORE.format(what='an auto parts store with tires, motor oil and car accessories'),
    }),
    ('deportes', {
        'key': 'zona-fit',
        'name': 'Zona Fit Altamira',
        'product_category': 'Deportes y Fitness',
        'company_category': ['Deportes'],
        'user': _user(9, 'Gabriela Alejandra', 'Torres', 'V22615478', 1, '1993-08-11'),
        'zone': 'Altamira',
        'address': 'Av. Luis Roche, Altamira, Chacao, Caracas',
        'details': 'Tienda deportiva a pie de calle en la Av. Luis Roche de Altamira.',
        'lat': 10.4996, 'lng': -66.8502,
        'tokens_per_dollar': 3,
        'logo_prompt': _LOGO.format(what='a sports and fitness store, a dumbbell forming a lightning bolt',
                                    colors='lime green and navy'),
        'store_prompt': _STORE.format(what='a sports and fitness store with sportswear, balls and gym gear'),
    }),
    ('bebes', {
        'key': 'mi-bebe-feliz',
        'name': 'Mi Bebé Feliz',
        'product_category': 'Bebés y Maternidad',
        'company_category': ['Bebés y Maternidad', 'Juguetería', 'Salud y Belleza'],
        'user': _user(10, 'Mariana Sofía', 'Castillo', 'V19478236', 1, '1989-02-25'),
        'zone': 'Altamira',
        'address': 'Av. Francisco de Miranda, Altamira Sur, Chacao, Caracas',
        'details': 'Tienda para bebés y maternidad a pie de calle en la Av. Francisco de Miranda, cerca de la Plaza Altamira.',
        'lat': 10.4952, 'lng': -66.8478,
        'tokens_per_dollar': 3,
        'logo_prompt': _LOGO.format(what='a baby store, a smiling baby face inside a cloud',
                                    colors='baby blue and soft yellow'),
        'store_prompt': _STORE.format(what='a cheerful baby store with strollers, cribs and baby clothes'),
    }),
    ('juguetes', {
        'key': 'mundo-magico',
        'name': 'Juguetería Mundo Mágico',
        'product_category': 'Juegos y Juguetes',
        'company_category': ['Juguetería'],
        'user': _user(11, 'Jesús Alberto', 'Ramírez', 'V18236547', 0, '1987-06-16'),
        'zone': 'Los Dos Caminos',
        'address': 'Av. Francisco de Miranda, Los Dos Caminos, Sucre, Caracas',
        'details': 'Juguetería a pie de calle sobre la Av. Francisco de Miranda, a pasos del metro de Los Dos Caminos.',
        'lat': 10.4955, 'lng': -66.8282,
        'tokens_per_dollar': 4,
        'logo_prompt': _LOGO.format(what='a toy store, a colorful spinning top with stars',
                                    colors='bright red, yellow and blue'),
        'store_prompt': _STORE.format(what='a colorful toy store with plush toys, board games and building blocks'),
    }),
    ('mascotas', {
        'key': 'patitas-felices',
        'name': 'Patitas Felices Pet Shop',
        'product_category': 'Mascotas',
        'company_category': ['Mascotas'],
        'user': _user(12, 'Daniela Patricia', 'Morales', 'V23794615', 1, '1994-10-07'),
        'zone': 'Los Palos Grandes',
        'address': 'Av. Francisco de Miranda, Los Palos Grandes, Chacao, Caracas',
        'details': 'Pet shop a pie de calle sobre la Av. Francisco de Miranda, a la altura de Los Palos Grandes.',
        'lat': 10.4972, 'lng': -66.8430,
        'tokens_per_dollar': 3,
        'logo_prompt': _LOGO.format(what='a pet shop, a dog paw print with a small heart',
                                    colors='teal and warm orange'),
        'store_prompt': _STORE.format(what='a friendly pet shop with pet food bags, toys and accessories'),
    }),
    ('papeleria', {
        'key': 'papeleria-altamira',
        'name': 'Librería y Papelería Altamira',
        'product_category': 'Papelería, Oficina y Libros',
        'company_category': ['Papelería y Oficina'],
        'user': _user(13, 'Rafael Ignacio', 'Briceño', 'V12568934', 0, '1978-03-21'),
        'zone': 'Altamira',
        'address': '1ra Avenida de Altamira, Chacao, Caracas',
        'details': 'Librería y papelería a pie de calle en la 1ra Avenida de Altamira.',
        'lat': 10.4975, 'lng': -66.8515,
        'tokens_per_dollar': 3,
        'logo_prompt': _LOGO.format(what='a bookstore and stationery shop, an open book with a pencil',
                                    colors='royal blue and mustard'),
        'store_prompt': _STORE.format(what='a bookstore and stationery shop with notebooks, books and art supplies'),
    }),
    ('instrumentos', {
        'key': 'sonido-criollo',
        'name': 'Sonido Criollo Music Store',
        'product_category': 'Instrumentos Musicales',
        'company_category': ['Entretenimiento y Eventos', 'Arte y Artesanías'],
        'user': _user(14, 'Miguel Ángel', 'Guerrero', 'V21346789', 0, '1992-12-19'),
        'zone': 'Chacao',
        'address': 'Av. Francisco de Miranda con Calle Elice, Chacao, Caracas',
        'details': 'Tienda de instrumentos musicales a pie de calle en la Av. Francisco de Miranda, esquina Calle Elice.',
        'lat': 10.4925, 'lng': -66.8530,
        'tokens_per_dollar': 2,
        'logo_prompt': _LOGO.format(what='a music instruments store, a Venezuelan cuatro guitar with sound waves',
                                    colors='burgundy and gold'),
        'store_prompt': _STORE.format(what='a music instruments store with guitars, cuatros and keyboards on the walls'),
    }),
    ('fiestas', {
        'key': 'la-fiesta',
        'name': 'Piñatería La Fiesta',
        'product_category': 'Fiestas y Piñatería',
        'company_category': ['Entretenimiento y Eventos', 'Juguetería'],
        'user': _user(15, 'Carolina Beatriz', 'Mendoza', 'V25183694', 1, '1996-07-04'),
        'zone': 'La California',
        'address': 'Av. Principal de La California Norte, Sucre, Caracas',
        'details': 'Piñatería y artículos de fiesta a pie de calle en La California Norte.',
        'lat': 10.4915, 'lng': -66.8140,
        'tokens_per_dollar': 4,
        'logo_prompt': _LOGO.format(what='a party supplies store, a colorful piñata star with confetti',
                                    colors='magenta, turquoise and yellow'),
        'store_prompt': _STORE.format(what='a party supplies store (piñatería) with balloons, piñatas and decorations'),
    }),
]


def _load_companies():
    companies = []
    for module_name, meta in _COMPANY_SPECS:
        module = importlib.import_module(f'{__name__}.{module_name}')
        cfg = dict(meta)
        products = []
        for raw_prod in getattr(module, 'PRODUCTS', []):
            prod = dict(raw_prod)
            # Para los comercios demo por categoría basta 1 imagen por producto.
            prod['img_prompts'] = list(prod.get('img_prompts') or [])[:1]
            products.append(prod)
        cfg['products'] = products
        companies.append(cfg)
    return companies


COMPANIES = _load_companies()

_EAST_CARACAS_SPOTS = [
    ('Altamira', 'Av. San Juan Bosco, Altamira, Chacao, Caracas', 10.4982, -66.8485),
    ('Chacao', 'Av. Francisco de Miranda, Chacao, Caracas', 10.4922, -66.8540),
    ('Los Palos Grandes', '1ra Avenida de Los Palos Grandes, Chacao, Caracas', 10.4998, -66.8435),
    ('Los Dos Caminos', 'Av. Rómulo Gallegos, Los Dos Caminos, Sucre, Caracas', 10.4968, -66.8286),
    ('La California', 'Av. Francisco de Miranda, La California Norte, Sucre, Caracas', 10.4892, -66.8158),
]

_EXTRA_NAMES = [
    ('Andrés Felipe', 'Urdaneta', 0),
    ('Paola Andrea', 'Villamizar', 1),
    ('Leonardo José', 'Cárdenas', 0),
    ('Verónica Alejandra', 'Quintero', 1),
    ('Sebastián David', 'Ochoa', 0),
    ('Camila Fernanda', 'Zambrano', 1),
    ('Alejandro José', 'Padrón', 0),
    ('Natalia Valentina', 'Linares', 1),
]


def _slugify_ascii(text: str) -> str:
    import re
    import unicodedata
    norm = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', '-', norm).strip('-') or 'categoria'


def _build_dynamic_company_for_category(cat_obj, user_index: int):
    """
    Fallback dinámico por si en la base de datos existe alguna Category adicional fuera de las 15 de
    CATALOGO_ESTRUCTURA (excluyendo 'Otras Categorías'): genera user<N>@cartmaker.app, comercio en el este de
    Caracas y 20 productos repartidos entre sus subcategorías.
    """
    from ._helpers import ALT, STUDIO, TOK_A, TOK_B, P, V
    cat_name = cat_obj.name.strip()
    slug_base = _slugify_ascii(cat_name)[:36]
    key = f'comercio-{slug_base}'
    first_name, last_name, gender = _EXTRA_NAMES[(user_index - 1) % len(_EXTRA_NAMES)]
    cedula = f'V{14000000 + (user_index * 17389) % 15000000}'
    zone, address, lat, lng = _EAST_CARACAS_SPOTS[(user_index - 1) % len(_EAST_CARACAS_SPOTS)]

    subs = list(cat_obj.subcategories.all().order_by('id'))
    sub_names = [s.name for s in subs] or [cat_name]

    products = []
    for i in range(1, PRODUCTS_PER_COMPANY + 1):
        sub_name = sub_names[(i - 1) % len(sub_names)]
        pslug = f'{slug_base[:28]}-item-{i:02d}'
        pname = f'{sub_name} Selección #{i} ({cat_name})'[:110]
        price = round(6.50 + (i * 3.75) % 85.0, 2)
        use_offer = (i % 3 == 0)
        use_tokens = (not use_offer) and (i % 2 == 1)
        has_variants = (i % 2 == 0)
        products.append(
            P(
                pslug,
                pname,
                sub_name,
                cat_name,
                price,
                f'{pname} disponible para entrega inmediata en {zone}, Caracas. '
                f'Producto verificado con garantía en tienda y despacho el mismo día.',
                (
                    STUDIO.format(what=f'commercial product from category {cat_name} ({sub_name}), item {i}'),
                ),
                unit='unit',
                attrs={},
                variants=[V({'presentation': 'Estándar'}, 6), V({'presentation': 'Especial'}, 4)] if has_variants else [],
                mods=[],
                tokens=(TOK_A if i % 4 == 1 else TOK_B) if use_tokens else None,
                offer=(10 if i % 6 == 0 else 15) if use_offer else 0,
                stock=None if has_variants else (8 + (i % 7)),
            )
        )

    return {
        'key': key,
        'name': f' Centro {cat_name[:42]} {zone}'.strip(),
        'product_category': cat_name,
        'company_category': [cat_name, 'Bodegón y Abasto', 'Tecnología', 'Moda y Ropa', 'Hogar y Muebles'],
        'user': _user(user_index, first_name, last_name, cedula, gender, f'{1980 + (user_index % 18)}-06-15'),
        'zone': zone,
        'address': address,
        'details': f'Local comercial a pie de calle en {address} ({zone}).',
        'lat': round(lat + ((user_index % 5) - 2) * 0.0004, 6),
        'lng': round(lng + ((user_index % 5) - 2) * 0.0004, 6),
        'tokens_per_dollar': 3,
        'logo_prompt': _LOGO.format(what=f'a retail store specialized in {cat_name}', colors='royal blue and gold'),
        'store_prompt': _STORE.format(what=f'a retail store specialized in {cat_name}'),
        'products': products,
    }


def companies_for_db_categories(db_categories=None):
    """
    Devuelve la lista de comercios a sembrar:
      * Si `db_categories` contiene las categorías de `Category` en la BD (excluyendo `EXCLUDED_CATEGORIES`),
        empareja cada `Category` con su comercio curado en `COMPANIES` y, si existiera alguna `Category` adicional en
        la BD, le genera automáticamente su usuario (`userN@cartmaker.app`), comercio en el este de Caracas y 20 productos.
      * Si `db_categories` es vacío o `None`, devuelve `COMPANIES` (las 15 categorías oficiales).
    """
    if not db_categories:
        return list(COMPANIES)
    excluded_norm = {c.strip().lower() for c in EXCLUDED_CATEGORIES}
    curated_by_cat = {c['product_category'].strip().lower(): c for c in COMPANIES}
    result = []
    used_keys = set()
    next_user_idx = len(COMPANIES) + 1
    for cat_obj in db_categories:
        cat_norm = (getattr(cat_obj, 'name', '') or '').strip().lower()
        if not cat_norm or cat_norm in excluded_norm:
            continue
        curated = curated_by_cat.get(cat_norm)
        if curated is not None and curated['key'] not in used_keys:
            result.append(curated)
            used_keys.add(curated['key'])
        else:
            dyn = _build_dynamic_company_for_category(cat_obj, next_user_idx)
            next_user_idx += 1
            result.append(dyn)
            used_keys.add(dyn['key'])
    return result or list(COMPANIES)


# ----------------------------------------------------------------------------------------------------------------------
# IDs deterministas y rutas locales bajo `api/static/img/demo_merchants/`
# (se sirven SIEMPRE desde el servidor local / repositorio git, nunca desde S3)
# ----------------------------------------------------------------------------------------------------------------------
STATIC_REL_PREFIX = 'static/img/demo_merchants'


def company_ids(company):
    return {'company': demo_uuid('company', company['key']), 'store': demo_uuid('store', company['key'])}


def product_id(company_key, slug):
    return demo_uuid('product', company_key, slug)


def inventory_item_id(company_key, slug):
    return demo_uuid('item', company_key, slug)


def product_image_keys(company_key, slug, count=1):
    return [f'{STATIC_REL_PREFIX}/{company_key}/{slug}.jpg']


def company_logo_key(company):
    return f"{STATIC_REL_PREFIX}/{company['key']}/_logo.jpg"


def store_image_key(company):
    return f"{STATIC_REL_PREFIX}/{company['key']}/_store.jpg"


def local_image_name(kind, company_key, slug=None, n=1):
    """Ruta relativa (dentro de api/static/img/demo_merchants/) del archivo local."""
    if kind == 'product':
        return f'{company_key}/{slug}.jpg'
    return f'{company_key}/_{kind}.jpg'
