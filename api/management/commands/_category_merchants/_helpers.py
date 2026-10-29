# -*- coding: utf-8 -*-
"""
Helpers de construcción compartidos por los catálogos de `_category_merchants`.

Se reutilizan los mismos constructores del catálogo demo original (`_demo_merchants_data.py`) para que ambos
conjuntos de datos tengan exactamente la misma forma y los procese el mismo comando `seed_demo_merchants`.

    P(slug, name, sub, parent, price, desc, imgs, *, unit='unit', attrs=None, variants=None, mods=None,
      tokens=None, offer=0, stock=None)
    V(options, stock, price=None)            -> variante
    grid(key_a, vals_a, key_b, vals_b, ...)  -> variantes combinando 2 ejes
    sizes(key, vals, ...)                    -> variantes de 1 eje
    M(name, [(opción, sobreprecio), ...], required=False, max_sel=1) -> grupo de personalización
    TOK_A / TOK_B / TOK_C                    -> niveles de descuento por tokens
    STUDIO / ALT                             -> plantillas de prompt para las 2 fotos de cada producto
"""
from .._demo_merchants_data import ALT, STUDIO, TOK_A, TOK_B, TOK_C, M, P, V, grid, sizes  # noqa: F401

__all__ = ['ALT', 'STUDIO', 'TOK_A', 'TOK_B', 'TOK_C', 'M', 'P', 'V', 'grid', 'sizes']
