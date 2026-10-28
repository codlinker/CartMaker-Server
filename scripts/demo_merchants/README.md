# Comercios demo (Soy Techno, EPA, MovilHogar, HERO)

Datos y herramientas para sembrar 4 comercios de Caracas con 15 productos cada uno.

| Archivo | Para qué |
|---|---|
| `api/management/commands/_demo_merchants_data.py` | Catálogo completo (usuarios, calles/coordenadas, productos, variantes, personalizaciones, tokens, ofertas) y claves deterministas de S3. |
| `api/management/commands/seed_demo_merchants.py` | Comando idempotente que escribe en la base de datos. |
| `scripts/demo_merchants/upload_images.py` | Sube a S3 las fotos de `images/` (comprime a ≤ 50 KB y genera variantes thumb/medium). |
| `scripts/demo_merchants/image_jobs.json` | Prompts de las 128 imágenes (logos, fachadas y 2 fotos por producto). |

## Orden de ejecución

1. **Subir imágenes** (en la máquina donde están las fotos; usa las claves AWS del entorno):

   ```bash
   source variables.sh
   python scripts/demo_merchants/upload_images.py --dry-run   # revisa qué subiría / qué falta
   python scripts/demo_merchants/upload_images.py             # idempotente: omite lo ya subido
   ```

2. **Sembrar la base de datos** (en el EC2, con `source variables.sh`):

   ```bash
   python manage.py seed_demo_merchants --dry-run   # simula y hace rollback
   python manage.py seed_demo_merchants
   ```

   El comando solo enlaza a cada producto las imágenes que existen en S3. Si luego subes las que faltan,
   vuelve a ejecutarlo y se completan (no duplica nada).

Opciones: `--only epa hero` (solo algunos comercios), `--skip-image-check`, `--offer-days 90`, `--plan "Plan Comercio"`.

## Qué hace por cada usuario

- `cedula_verified = True` y `user_type = MERCHANT` (sin pasar por la verificación biométrica).
- `Company` (emprendedor, gamificación de tokens activa) + sucursal principal **a pie de calle** con ubicación
  en una vía real de Caracas (coordenadas tomadas de OpenStreetMap).
- `MerchantSubscription` con Plan Comercio (1 año) si el usuario no tiene un plan con gamificación.
- 15 productos con atributos de su subcategoría, variantes con stock, personalizaciones (`modifier_groups`),
  descuentos por tokens, `InventoryItem` con stock y ofertas porcentuales vigentes (90 días).

Si el usuario ya tiene otra compañía, o el nombre ya existe, ese comercio se omite con un aviso (no se toca nada).
