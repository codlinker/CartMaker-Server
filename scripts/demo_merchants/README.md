# Comercios demo

Datos y herramientas para sembrar comercios de demostración en Caracas con su catálogo de productos.
El comando `seed_demo_merchants` trabaja con dos conjuntos de datos (`--dataset`):

| Dataset | Qué crea |
|---|---|
| `categories` (por defecto) | **15 usuarios nuevos** (`user1@cartmaker.app` … `user15@cartmaker.app`), uno por cada categoría principal excepto "Otras Categorías", cada uno con identidad verificada, 1 comercio a pie de calle en el este de Caracas (Altamira, Chacao, Los Palos Grandes, Los Dos Caminos, La California) y **20 productos** (1 imagen local por producto en `api/static/img/demo_merchants/`, servida directamente desde local sin S3). |
| `legacy` | Los 4 comercios originales (Soy Techno, EPA, MovilHogar, HERO) con 15 productos c/u, asignados a usuarios **ya existentes** buscados por UUID. |

| Archivo | Para qué |
|---|---|
| `api/management/commands/_category_merchants/` | Dataset `categories`: `__init__.py` (usuarios, comercios, calles/coordenadas y rutas estáticas locales `static/img/demo_merchants/...`) + un módulo de productos por categoría. |
| `api/static/img/demo_merchants/` | **330 imágenes locales** (15 logos `_logo.jpg`, 15 fachadas `_store.jpg` y 300 fotos de productos `<slug>.jpg`), versionadas en git y servidas directamente desde el servidor local (`${DOMAIN}/static/img/demo_merchants/...`) independientemente de `STORAGE_TYPE`. |
| `api/management/commands/_demo_merchants_data.py` | Dataset `legacy` (y helpers `P`, `V`, `M`, `grid`, `sizes` que reutiliza el dataset `categories`). |
| `api/management/commands/seed_demo_merchants.py` | Comando idempotente que escribe en la base de datos y sincroniza `api/static/img/demo_merchants/` hacia `STATIC_ROOT`. |
| `scripts/demo_merchants/validate_category_catalog.py` | Valida el dataset `categories` sin Django (20 productos, subcategorías, unidades, atributos y variantes según el esquema SDUI). |
| `scripts/demo_merchants/build_image_jobs.py` | Genera el manifiesto de imágenes (`category_image_jobs.json` con 330 entradas / `image_jobs.json`). |
| `scripts/demo_merchants/generate_images.py` | Rellena o actualiza `api/static/img/demo_merchants/` en modo instantáneo (`--mode local`, usando las fotos reales de `api/static/img/categories/`) o generando fotos únicas con IA (`--mode gemini`, usando `GEMINI_API_KEY` de `variables.sh`). |
| `scripts/demo_merchants/upload_images.py` | Sube a S3 las fotos del dataset `legacy` si se requiere. |

## Usuarios del dataset `categories`

- Email `userN@cartmaker.app`, nombre y apellido inventados, cédula venezolana `V########` (mismo formato que guarda el
  flujo de verificación), `cedula_verified = True`, `email_verified = True`, `user_type = MERCHANT`.
- Contraseña por defecto `Zero=25z` (se puede cambiar con `--password`). Si el usuario ya existe, se actualizan sus
  datos y su contraseña.
- Si la cédula ya pertenece a otro usuario, o el usuario ya tiene otra compañía, o el nombre del comercio ya existe,
  ese comercio se omite con un aviso (se revierte todo lo de ese comercio).

## Orden de ejecución

1. **Validar el catálogo** (en cualquier máquina, sin base de datos):

   ```bash
   python scripts/demo_merchants/validate_category_catalog.py --strict
   ```

2. **(Opcional) Regenerar imágenes locales en `api/static/img/demo_merchants/`**:

   Las 330 imágenes ya están listas en `api/static/img/demo_merchants/` para subirse a git. Si deseas regenerarlas:

   ```bash
   # Opción A (instantánea): copia fotos reales del catálogo de subcategorías hacia api/static/img/demo_merchants/
   python scripts/demo_merchants/generate_images.py --mode local --overwrite

   # Opción B (con IA): genera fotos únicas por producto con Gemini directamente en api/static/img/demo_merchants/
   python scripts/demo_merchants/generate_images.py --mode gemini --workers 4 --overwrite
   ```

3. **Sembrar la base de datos**:

   ```bash
   python manage.py seed_demo_merchants --dry-run   # simula y hace rollback
   python manage.py seed_demo_merchants             # crea/actualiza los 15 comercios y sincroniza STATIC_ROOT
   ```

Opciones: `--dataset legacy`, `--only pixel-store zona-fit` (solo algunos comercios), `--password`,
`--skip-image-check`, `--offer-days 90`, `--plan "Plan Comercio"`.

## Qué hace por cada comercio

- Usuario (creado/actualizado en `categories`, existente en `legacy`) con `cedula_verified = True` y
  `user_type = MERCHANT` (sin pasar por la verificación biométrica).
- `Company` (emprendedor, gamificación de tokens activa) + sucursal principal **a pie de calle** en una vía de Caracas.
- `MerchantSubscription` con Plan Comercio (1 año) si el usuario no tiene un plan con gamificación.
- Productos con atributos de su subcategoría, variantes con stock, personalizaciones (`modifier_groups`),
  descuentos por tokens, 1 foto local (`static/img/demo_merchants/<company>/<slug>.jpg`), `InventoryItem` con stock y
  ofertas porcentuales vigentes (90 días).
