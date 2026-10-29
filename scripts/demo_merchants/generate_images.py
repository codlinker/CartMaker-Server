# -*- coding: utf-8 -*-
"""
Genera (o rellena) las 630 imágenes de `scripts/demo_merchants/images/` para los comercios demo.

Soporta dos modos (`--mode`):

  1. `gemini` (por defecto): usa `GEMINI_API_KEY` (o `OPENROUTER_API_KEY`) leyendo automáticamente `variables.sh`
     para generar cada foto con IA a partir de los prompts de `category_image_jobs.json` (`image_jobs.json` si se usa
     `--dataset legacy`). Es idempotente: guarda el progreso en `images/_ai_generated.json` y salta las ya generadas
     con IA, por lo que se puede pausar y reanudar en cualquier momento.
  2. `local`: rellena instantáneamente todas las imágenes faltantes usando las 217 fotografías reales del catálogo
     local (`api/static/img/categories/sub_categories/...`), asignando la foto de la subcategoría exacta del producto
     como imagen #1 y una segunda foto de otra subcategoría hermana como imagen #2. Ideal para subir y probar de
     inmediato sin esperar la generación por IA ni gastar cuota.

Uso (desde la raíz del proyecto):

    # Opción rápida (instantánea, sin llamadas de red, usa las fotos reales de api/static/img/categories/):
    python scripts/demo_merchants/generate_images.py --mode local

    # Opción IA con Gemini (genera fotos únicas por producto desde category_image_jobs.json y reemplaza las locales):
    python scripts/demo_merchants/generate_images.py --mode gemini --workers 4
    python scripts/demo_merchants/generate_images.py --mode gemini --only pixel-store sabor-avila

    # Luego subir a S3 y sembrar la BD:
    python scripts/demo_merchants/upload_images.py
    python manage.py seed_demo_merchants
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))

from api.core.category_schemas import CATALOGO_ESTRUCTURA  # noqa: E402

DATASETS = {
    'categories': (
        'api.management.commands._category_merchants',
        'category_image_jobs.json',
        os.path.join(ROOT, 'api', 'static', 'img', 'demo_merchants'),
    ),
    'legacy': (
        'api.management.commands._demo_merchants_data',
        'image_jobs.json',
        os.path.join(HERE, 'images'),
    ),
}


def _load_env_from_variables_sh():
    """Carga variables desde `variables.sh` si aún no están en `os.environ`."""
    var_file = os.path.join(ROOT, 'variables.sh')
    if not os.path.isfile(var_file):
        return
    pattern = re.compile(r'^\s*export\s+([A-Z0-9_]+)=("([^"]*)"|\'([^\']*)\'|([^\s#]+))')
    with open(var_file, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = pattern.match(line)
            if not m:
                continue
            key = m.group(1)
            val = m.group(3) if m.group(3) is not None else (m.group(4) if m.group(4) is not None else m.group(5))
            if key and val is not None and not os.environ.get(key):
                os.environ[key] = val


def _build_static_catalog_map():
    """Devuelve mapas de categoría -> ruta absoluta de imagen y (categoría, subcategoría) -> ruta absoluta."""
    api_dir = os.path.join(ROOT, 'api')
    cat_img = {}
    sub_img = {}
    cat_subs_imgs = {}
    for entry in CATALOGO_ESTRUCTURA:
        cname = entry['categoria']
        cpath = os.path.join(api_dir, *entry['imagen'].split('/'))
        if os.path.isfile(cpath):
            cat_img[cname] = cpath
        cat_subs_imgs.setdefault(cname, [])
        for sub in entry.get('subcategorias', []):
            spath = os.path.join(api_dir, *sub['imagen'].split('/'))
            if os.path.isfile(spath):
                sub_img[(cname, sub['nombre'])] = spath
                sub_img[sub['nombre']] = spath
                cat_subs_imgs[cname].append(spath)
    return cat_img, sub_img, cat_subs_imgs


def _load_ai_manifest(images_dir):
    path = os.path.join(images_dir, '_ai_generated.json')
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return set(json.load(fh))
    except Exception:
        return set()


def _save_ai_manifest(images_dir, generated_set):
    path = os.path.join(images_dir, '_ai_generated.json')
    os.makedirs(images_dir, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(sorted(generated_set), fh, ensure_ascii=False, indent=1)
        fh.write('\n')


def populate_local_images(data_module, jobs, images_dir, only_companies=None, force=False):
    """Copia fotos reales desde `api/static/img/categories/` para cada job de imagen."""
    cat_img, sub_img, cat_subs_imgs = _build_static_catalog_map()
    all_static = [p for paths in cat_subs_imgs.values() for p in paths]
    if not all_static:
        raise RuntimeError('No se encontraron imágenes estáticas en api/static/img/categories/.')

    companies_by_key = {c['key']: c for c in data_module.COMPANIES}
    products_by_key_slug = {
        (c['key'], p['slug']): p
        for c in data_module.COMPANIES
        for p in c['products']
    }
    ai_done = _load_ai_manifest(images_dir)
    created = skipped = 0

    for idx, job in enumerate(jobs):
        ckey = job['company']
        if only_companies and ckey not in only_companies:
            continue
        rel_file = job['file']
        dst = os.path.join(images_dir, *rel_file.split('/'))
        if os.path.isfile(dst) and (not force or rel_file in ai_done):
            skipped += 1
            continue

        comp = companies_by_key.get(ckey, {})
        pcat = comp.get('product_category')
        src = None
        if job['kind'] == 'logo':
            src = cat_img.get(pcat)
            if not src and pcat in cat_subs_imgs and cat_subs_imgs[pcat]:
                src = cat_subs_imgs[pcat][0]
        elif job['kind'] == 'store':
            siblings = cat_subs_imgs.get(pcat) or []
            src = siblings[min(1, len(siblings) - 1)] if siblings else cat_img.get(pcat)
        else:
            pspec = products_by_key_slug.get((ckey, job.get('slug')), {})
            sub_name = pspec.get('sub')
            parent_name = pspec.get('parent') or pcat
            primary = sub_img.get((parent_name, sub_name)) or sub_img.get(sub_name)
            siblings = [p for p in (cat_subs_imgs.get(parent_name) or []) if p != primary]
            if job.get('n', 1) == 1 and primary:
                src = primary
            elif siblings:
                src = siblings[idx % len(siblings)]
            else:
                src = primary or cat_img.get(parent_name)

        if not src or not os.path.isfile(src):
            src = all_static[idx % len(all_static)]

        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        created += 1

    return created, skipped


def _call_gemini_image_api(prompt: str, aspect: str, api_key: str) -> bytes:
    """
    Intenta generar una imagen con la API de Gemini probando en orden:
      1. `gemini-2.5-flash-image` / `gemini-2.0-flash-exp-image-generation` (generateContent con IMAGE modality)
      2. `imagen-3.0-generate-002` (predict)
    """
    last_err = None
    # 1) Modelos generateContent con modalidad IMAGE
    for model in ('gemini-2.5-flash-image', 'gemini-2.0-flash-preview-image-generation', 'gemini-2.0-flash-exp-image-generation'):
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
        body = json.dumps({
            'contents': [{'parts': [{'text': f'{prompt} (aspect ratio {aspect})'}]}],
            'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']},
        }).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
            for cand in payload.get('candidates') or []:
                for part in (cand.get('content') or {}).get('parts') or []:
                    inline = part.get('inlineData') or part.get('inline_data')
                    if inline and inline.get('data'):
                        return base64.b64decode(inline['data'])
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode('utf-8', errors='replace')[:300]
            last_err = f'{model} HTTP {exc.code}: {err_body}'
            if exc.code == 429:
                time.sleep(4)
        except Exception as exc:
            last_err = f'{model}: {exc}'

    # 2) Modelo Imagen 3 predict
    url = f'https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}'
    body = json.dumps({
        'instances': [{'prompt': prompt}],
        'parameters': {'sampleCount': 1, 'aspectRatio': aspect or '1:1', 'outputOptions': {'mimeType': 'image/jpeg'}},
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        preds = payload.get('predictions') or []
        if preds and preds[0].get('bytesBase64Encoded'):
            return base64.b64decode(preds[0]['bytesBase64Encoded'])
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode('utf-8', errors='replace')[:300]
        last_err = f'imagen-3.0 HTTP {exc.code}: {err_body}'
    except Exception as exc:
        last_err = f'imagen-3.0: {exc}'

    raise RuntimeError(last_err or 'No se recibió imagen desde Gemini API')


def generate_gemini_images(jobs, images_dir, only_companies=None, workers=3, force=False, limit=None):
    _load_env_from_variables_sh()
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('No se encontró GEMINI_API_KEY en el entorno ni en variables.sh.')

    ai_done = _load_ai_manifest(images_dir)
    todo = []
    skipped = 0
    for job in jobs:
        if only_companies and job['company'] not in only_companies:
            continue
        rel_file = job['file']
        dst = os.path.join(images_dir, *rel_file.split('/'))
        if not force and rel_file in ai_done and os.path.isfile(dst):
            skipped += 1
            continue
        todo.append(job)
        if limit and len(todo) >= limit:
            break

    if not todo:
        return 0, skipped, 0

    generated = failed = 0

    def _worker(job):
        rel_file = job['file']
        dst = os.path.join(images_dir, *rel_file.split('/'))
        img_bytes = _call_gemini_image_api(job['prompt'], job.get('aspect', '1:1'), api_key)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as fh:
            fh.write(img_bytes)
        return rel_file, len(img_bytes)

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        future_map = {pool.submit(_worker, job): job for job in todo}
        for fut in as_completed(future_map):
            job = future_map[fut]
            try:
                rel_file, size_b = fut.result()
                ai_done.add(rel_file)
                _save_ai_manifest(images_dir, ai_done)
                generated += 1
                print(f'✓ [{generated}/{len(todo)}] {rel_file} ({size_b // 1024} KB)')
            except Exception as exc:
                failed += 1
                print(f"✗ ERROR en {job['file']}: {exc}")

    return generated, skipped, failed


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dataset', choices=sorted(DATASETS), default='categories')
    parser.add_argument('--mode', choices=('local', 'gemini'), default='local',
                        help="'local' copia fotos reales de api/static/img/categories/; 'gemini' genera con IA usando GEMINI_API_KEY.")
    parser.add_argument('--images-dir', default=None,
                        help='Carpeta destino (por defecto api/static/img/demo_merchants para categories).')
    parser.add_argument('--only', nargs='+', help='Solo estos comercios (por key).')
    parser.add_argument('--workers', type=int, default=3, help='Hilos paralelos en modo gemini (por defecto 3).')
    parser.add_argument('--limit', type=int, help='Máximo de imágenes a generar en esta corrida (modo gemini).')
    parser.add_argument('--force', action='store_true', help='Regenera aunque el archivo ya exista.')
    args = parser.parse_args()

    module_name, jobs_filename, default_images_dir = DATASETS[args.dataset]
    images_dir = args.images_dir or default_images_dir
    data_module = importlib.import_module(module_name)
    jobs_path = os.path.join(HERE, jobs_filename)
    if not os.path.isfile(jobs_path):
        from build_image_jobs import build_jobs
        jobs = build_jobs(data_module)
    else:
        with open(jobs_path, 'r', encoding='utf-8') as fh:
            jobs = json.load(fh)

    only_set = set(args.only) if args.only else None

    if args.mode == 'local':
        created, skipped = populate_local_images(
            data_module, jobs, images_dir, only_companies=only_set, force=args.force
        )
        print(f'Modo local completado -> creadas/actualizadas: {created} | ya existentes: {skipped} | carpeta: {images_dir}')
    else:
        generated, skipped, failed = generate_gemini_images(
            jobs, images_dir, only_companies=only_set, workers=args.workers, force=args.force, limit=args.limit
        )
        print(f'\nModo gemini completado -> generadas con IA: {generated} | ya existentes: {skipped} | fallidas: {failed}')
        sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
