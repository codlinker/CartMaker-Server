# -*- coding: utf-8 -*-
"""
Genera el manifiesto de imágenes a producir (logos, fachadas y 2 fotos por producto) para un catálogo demo, con el
mismo formato que `image_jobs.json`. Cada entrada indica el archivo local esperado dentro de
`scripts/demo_merchants/images/` (que luego sube `upload_images.py`) y el prompt para generarla.

No requiere Django ni base de datos.

Uso (desde la raíz del proyecto):

    python scripts/demo_merchants/build_image_jobs.py                       # -> category_image_jobs.json
    python scripts/demo_merchants/build_image_jobs.py --dataset legacy      # -> image_jobs.json
"""
import argparse
import importlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))

DATASETS = {
    'categories': ('api.management.commands._category_merchants', 'category_image_jobs.json'),
    'legacy': ('api.management.commands._demo_merchants_data', 'image_jobs.json'),
}


def build_jobs(data):
    jobs = []
    for company in data.COMPANIES:
        key = company['key']
        jobs.append({'company': key, 'kind': 'logo', 'file': data.local_image_name('logo', key),
                     'prompt': company['logo_prompt'], 'aspect': '1:1'})
        jobs.append({'company': key, 'kind': 'store', 'file': data.local_image_name('store', key),
                     'prompt': company['store_prompt'], 'aspect': '4:3'})
        for spec in company['products']:
            for n, prompt in enumerate(spec['img_prompts'], 1):
                jobs.append({'company': key, 'kind': 'product', 'slug': spec['slug'], 'name': spec['name'], 'n': n,
                             'file': data.local_image_name('product', key, spec['slug'], n),
                             'prompt': prompt, 'aspect': '1:1'})
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dataset', choices=sorted(DATASETS), default='categories')
    parser.add_argument('--output', help='Ruta del JSON de salida (por defecto según el dataset).')
    args = parser.parse_args()

    module_name, default_file = DATASETS[args.dataset]
    jobs = build_jobs(importlib.import_module(module_name))
    output = args.output or os.path.join(HERE, default_file)
    with open(output, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(jobs, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    kinds = {k: sum(1 for j in jobs if j['kind'] == k) for k in ('logo', 'store', 'product')}
    print(f'{len(jobs)} imágenes -> {output} ({kinds})')


if __name__ == '__main__':
    main()
