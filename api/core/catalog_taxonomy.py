"""Taxonomía oficial de categorías de CartMaker (15 categorías y 158 subcategorías)
para el motor de deducción de Atlas.

Sincronizado automáticamente con `CATALOGO_ESTRUCTURA` en `api/core/category_schemas.py`.
"""

from typing import Dict, List
from api.core.category_schemas import CATALOGO_ESTRUCTURA

CATALOG_TAXONOMY: Dict[str, List[str]] = {
    entry["categoria"]: [sub["nombre"] for sub in entry["subcategorias"]]
    for entry in CATALOGO_ESTRUCTURA
}


def render_catalog_for_prompt() -> str:
    """Una línea por categoría: 'Categoría: Sub1 | Sub2 | ...'."""
    return "\n".join(
        f"- {category}: {' | '.join(subcategories)}"
        for category, subcategories in CATALOG_TAXONOMY.items()
    )
