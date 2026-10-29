# -*- coding: utf-8 -*-
"""
Valida (sin Django ni base de datos) el catálogo demo "un comercio por categoría"
(`api/management/commands/_category_merchants/`).

Comprueba por comercio: 20 productos, slugs únicos, subcategorías oficiales de su categoría, unidad de venta permitida
por el esquema SDUI, claves de atributos/variantes conocidas por el esquema, precios/ofertas/tokens coherentes,
stock, 2 prompts de imagen y que `validate_and_normalize_product_dynamic_data` acepte el producto.

Uso (desde la raíz del proyecto):

    python scripts/demo_merchants/validate_category_catalog.py              # todos los comercios
    python scripts/demo_merchants/validate_category_catalog.py tecnologia   # solo ese módulo
    python scripts/demo_merchants/validate_category_catalog.py --strict     # las advertencias también fallan
"""
import argparse
import importlib
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from api.core.category_schemas import (  # noqa: E402
    CATALOGO_ESTRUCTURA,
    get_subcategory_schema,
    validate_and_normalize_product_dynamic_data,
)

PKG = 'api.management.commands._category_merchants'
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def _subcategories_by_category():
    return {c['categoria']: {s['nombre'] for s in c.get('subcategorias', [])} for c in CATALOGO_ESTRUCTURA}


def validate_company(cfg, expected_count):
    errors, warnings = [], []
    subs_by_cat = _subcategories_by_category()
    cat = cfg['product_category']
    if cat not in subs_by_cat:
        errors.append(f"categoría '{cat}' no existe en CATALOGO_ESTRUCTURA")
        return errors, warnings
    official_subs = subs_by_cat[cat]
    products = cfg['products']
    if len(products) != expected_count:
        errors.append(f'tiene {len(products)} productos (se esperan {expected_count})')

    seen_slugs, seen_names, used_subs = set(), set(), set()
    for spec in products:
        tag = f"[{spec.get('slug')}]"
        slug = spec['slug']
        if not SLUG_RE.match(slug) or len(slug) > 60:
            errors.append(f'{tag} slug inválido (kebab-case, <= 60 caracteres)')
        if slug in seen_slugs:
            errors.append(f'{tag} slug duplicado')
        seen_slugs.add(slug)
        if spec['name'].lower() in seen_names:
            errors.append(f'{tag} nombre duplicado')
        seen_names.add(spec['name'].lower())
        if not (3 <= len(spec['name']) <= 120):
            errors.append(f'{tag} nombre con longitud fuera de rango')
        if spec['parent'] != cat:
            errors.append(f"{tag} parent '{spec['parent']}' != categoría del comercio '{cat}'")
        if spec['sub'] not in official_subs:
            errors.append(f"{tag} subcategoría '{spec['sub']}' no pertenece a '{cat}'")
            continue
        used_subs.add(spec['sub'])

        price = spec['price']
        if not isinstance(price, (int, float)) or price <= 0:
            errors.append(f'{tag} precio inválido: {price!r}')
            continue
        if len(spec['description']) < 60:
            warnings.append(f'{tag} descripción muy corta')
        if not isinstance(spec['offer'], int) or not (0 <= spec['offer'] <= 60):
            errors.append(f"{tag} offer debe ser entero 0..60 (es {spec['offer']!r})")
        if spec['tokens']:
            tiers = spec['tokens']
            if not all(isinstance(t, dict) and t.get('tokens', 0) > 0 and 0 < t.get('percentage', 0) < 100 for t in tiers):
                errors.append(f'{tag} tokens con niveles inválidos')
        if len(spec['img_prompts']) != 1 or not all(isinstance(p, str) and len(p) > 40 for p in spec['img_prompts']):
            errors.append(f'{tag} debe tener exactamente 1 prompt de imagen descriptivo')

        schema = get_subcategory_schema(subcategory_name=spec['sub'], parent_category_name=cat)
        allowed_units = schema.get('allowed_selling_unit_codes') or ['unit']
        if spec['selling_unit'] not in allowed_units:
            errors.append(f"{tag} unidad '{spec['selling_unit']}' no permitida ({allowed_units})")

        fields = {f['key']: f for f in schema.get('fields', [])}
        for key, value in (spec['attributes'] or {}).items():
            if key not in fields:
                errors.append(f"{tag} atributo '{key}' no existe en el esquema de '{spec['sub']}' ({sorted(fields)})")
                continue
            field = fields[key]
            opts = field.get('options') or []
            ftype = field.get('type')
            if ftype == 'select' and opts and value not in opts:
                warnings.append(f"{tag} '{key}'='{value}' no está entre las opciones del esquema")
            if ftype in ('multiselect', 'multi_select', 'chips') and opts:
                vals = value if isinstance(value, list) else [value]
                bad = [v for v in vals if v not in opts]
                if bad:
                    warnings.append(f"{tag} '{key}' valores fuera de opciones: {bad}")
            if ftype == 'number' and not isinstance(value, (int, float)):
                warnings.append(f"{tag} '{key}' debería ser numérico")
            if ftype in ('boolean', 'bool', 'switch') and not isinstance(value, bool):
                warnings.append(f"{tag} '{key}' debería ser booleano")
        required = [k for k, f in fields.items() if f.get('required')]
        missing = [k for k in required if k not in (spec['attributes'] or {})]
        if missing:
            warnings.append(f'{tag} faltan atributos requeridos por el esquema: {missing}')

        variants = spec['variants'] or []
        if variants:
            if not schema.get('supports_variants', True):
                warnings.append(f"{tag} el esquema de '{spec['sub']}' no soporta variantes")
            axes = {a['key'] for a in (schema.get('variant_config') or {}).get('axes', [])}
            for v in variants:
                unknown = [k for k in v['options'] if axes and k not in axes]
                if unknown:
                    warnings.append(f'{tag} eje(s) de variante {unknown} no definidos en el esquema ({sorted(axes)})')
                    break
            if not any(int(v['stock'] or 0) > 0 for v in variants):
                errors.append(f'{tag} todas las variantes están agotadas')
        else:
            if not isinstance(spec['stock'], int) or spec['stock'] <= 0:
                errors.append(f"{tag} sin variantes necesita stock entero > 0 (es {spec['stock']!r})")
        if spec['modifier_groups'] and not schema.get('supports_modifier_groups'):
            warnings.append(f"{tag} el esquema de '{spec['sub']}' no declara modifier_groups")

        try:
            validate_and_normalize_product_dynamic_data(
                {'selling_unit': spec['selling_unit'], 'attributes': spec['attributes'],
                 'variants': variants, 'modifier_groups': spec['modifier_groups']},
                subcategory_name=spec['sub'], category_name=cat, base_price=float(price),
            )
        except Exception as exc:  # pragma: no cover - diagnóstico
            errors.append(f'{tag} validate_and_normalize_product_dynamic_data falló: {exc}')

    retail_subs = official_subs - {'Inmuebles y Locales Comerciales', 'Servicios Profesionales'}
    if len(used_subs) < min(5, len(retail_subs)):
        warnings.append(f'solo usa {len(used_subs)} subcategorías distintas (se recomiendan >= 5)')
    offers = sum(1 for p in products if p['offer'])
    tokens = sum(1 for p in products if p['tokens'])
    with_variants = sum(1 for p in products if p['variants'])
    return errors, warnings, {'subs': len(used_subs), 'offers': offers, 'tokens': tokens, 'variants': with_variants}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('modules', nargs='*', help='Módulos de productos a validar (por defecto todos).')
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    pkg = importlib.import_module(PKG)
    specs = pkg._COMPANY_SPECS
    if args.modules:
        specs = [s for s in specs if s[0] in args.modules]
    total_err = total_warn = 0
    seen_emails, seen_cedulas = set(), set()
    for module_name, meta in specs:
        cfg = next(c for c in pkg.COMPANIES if c['key'] == meta['key'])
        result = validate_company(cfg, pkg.PRODUCTS_PER_COMPANY)
        errors, warnings = result[0], result[1]
        stats = result[2] if len(result) > 2 else {}
        user = cfg['user']
        if user['email'] in seen_emails or user['cedula'] in seen_cedulas:
            errors.append('email o cédula de usuario duplicados')
        seen_emails.add(user['email'])
        seen_cedulas.add(user['cedula'])
        status = 'OK ' if not errors else 'ERR'
        print(f"{status} {module_name:<22} {cfg['name']:<32} productos={len(cfg['products'])} {stats}")
        for e in errors:
            print(f'    ✗ {e}')
        for w in warnings:
            print(f'    ! {w}')
        total_err += len(errors)
        total_warn += len(warnings)
    print(f'\nErrores: {total_err} | Advertencias: {total_warn}')
    sys.exit(1 if total_err or (args.strict and total_warn) else 0)


if __name__ == '__main__':
    main()
