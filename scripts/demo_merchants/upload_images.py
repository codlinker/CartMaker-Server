# -*- coding: utf-8 -*-
"""
Sube a S3 las imágenes de demostración generadas en `scripts/demo_merchants/images/` usando las MISMAS claves
deterministas que referencia `python manage.py seed_demo_merchants`.

  * Comprime cada imagen a <= 50 KB (mismo motor que la API) y sube original + variantes thumb/medium (WebP).
  * Idempotente: omite las que ya existen en el bucket (usa --force para volver a subirlas).
  * `--dataset categories` (por defecto) = 1 comercio por categoría; `--dataset legacy` = los 4 comercios originales.

Uso (desde la raíz del proyecto, con `source variables.sh` cargado):

    python scripts/demo_merchants/upload_images.py --dry-run
    python scripts/demo_merchants/upload_images.py
    python scripts/demo_merchants/upload_images.py --dataset legacy
"""
import argparse
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cartmaker_admin.settings')

import django  # noqa: E402

django.setup()

from api.core.image_variants import generate_image_variants  # noqa: E402
from api.cos import compress_uploaded_image_stream, storage_manager  # noqa: E402
from api.management.commands import _category_merchants as category_data  # noqa: E402
from api.management.commands import _demo_merchants_data as legacy_data  # noqa: E402

DATASETS = {'categories': category_data, 'legacy': legacy_data}
HERE = os.path.dirname(os.path.abspath(__file__))


def build_targets(data):
    """[(archivo_local_relativo, clave_s3, etiqueta)] para todas las imágenes del catálogo demo."""
    targets = []
    for company in data.COMPANIES:
        targets.append((data.local_image_name('logo', company['key']), data.company_logo_key(company),
                        f"{company['name']} · logo"))
        targets.append((data.local_image_name('store', company['key']), data.store_image_key(company),
                        f"{company['name']} · fachada"))
        for spec in company['products']:
            keys = data.product_image_keys(company['key'], spec['slug'], len(spec['img_prompts']))
            for n, key in enumerate(keys, 1):
                targets.append((data.local_image_name('product', company['key'], spec['slug'], n), key,
                                f"{company['name']} · {spec['name']} #{n}"))
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--images-dir', default=os.path.join(HERE, 'images'))
    parser.add_argument('--dataset', choices=sorted(DATASETS), default='categories')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true', help='Vuelve a subir aunque ya exista en el bucket.')
    args = parser.parse_args()

    if storage_manager.storage_type != 'aws':
        print(f"⚠️  STORAGE_TYPE={storage_manager.storage_type!r}: las imágenes se guardarán en MEDIA_ROOT, no en S3.")

    targets = build_targets(DATASETS[args.dataset])
    uploaded = skipped = missing = failed = 0
    for rel_file, key, label in targets:
        path = os.path.join(args.images_dir, *rel_file.split('/'))
        if not os.path.isfile(path):
            print(f'✗ FALTA  {rel_file}  ({label})')
            missing += 1
            continue
        if not args.force and storage_manager.file_exists(key):
            print(f'· existe {key}')
            skipped += 1
            continue
        if args.dry_run:
            print(f'→ subiría {rel_file} -> {key}')
            continue

        with open(path, 'rb') as fh:
            stream, _ = compress_uploaded_image_stream(fh, file_name=os.path.basename(path))
            payload = stream.read() if hasattr(stream, 'read') else fh.read()
        if not storage_manager.put_bytes(key, payload, content_type='image/jpeg'):
            print(f'✗ ERROR subiendo {key}')
            failed += 1
            continue
        status = generate_image_variants(key, force=True, original_bytes=payload)
        print(f'✓ {key}  ({len(payload) // 1024} KB, variantes: {status})')
        uploaded += 1

    print(f'\nTotal: {len(targets)} | subidas: {uploaded} | ya existentes: {skipped} | faltantes: {missing} | errores: {failed}')
    sys.exit(1 if (missing or failed) else 0)


if __name__ == '__main__':
    main()
