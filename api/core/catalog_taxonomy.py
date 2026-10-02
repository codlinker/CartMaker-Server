"""Taxonomía de categorías de CartMaker (solo nombres) para el motor de deducción de Atlas.

Espejo de `catalogo_estructura` en `fill_default_bd.py`, sin las imágenes.
Si se agregan o renombran categorías allá, actualizar aquí.
"""

from typing import Dict, List

CATALOG_TAXONOMY: Dict[str, List[str]] = {
    'Alimentos y Bebidas': [
        'Despensa y Víveres', 'Frescos', 'Charcutería y Lácteos', 'Bebidas',
        'Licores', 'Snacks y Dulces', 'Limpieza del Hogar',
    ],
    'Tecnología y Electrónica': [
        'Celulares y Tablets', 'Computación', 'Periféricos y Accesorios',
        'Audio y Video', 'Videojuegos y Consolas', 'Wearables', 'Cámaras y Fotografía',
    ],
    'Moda y Accesorios': [
        'Ropa Femenina', 'Ropa Masculina', 'Ropa Infantil y Bebés', 'Calzado',
        'Bolsos y Carteras', 'Accesorios y Joyería',
    ],
    'Salud y Belleza': [
        'Cuidado Personal', 'Skincare y Cuidado Facial', 'Maquillaje', 'Perfumería',
        'Farmacia y Bienestar',
    ],
    'Hogar, Muebles y Jardín': [
        'Electrodomésticos', 'Muebles', 'Dormitorio', 'Baño', 'Decoración',
        'Jardín y Exteriores',
    ],
    'Ferretería y Construcción': [
        'Herramientas', 'Electricidad e Iluminación', 'Plomería',
        'Materiales de Construcción', 'Seguridad y Domótica',
    ],
    'Automotriz y Motos': [
        'Repuestos para Autos', 'Lubricantes y Fluidos', 'Neumáticos y Rines',
        'Accesorios para Vehículos', 'Motos',
    ],
    'Deportes y Fitness': [
        'Fitness y Musculación', 'Ropa y Calzado Deportivo', 'Deportes Específicos',
        'Camping y Outdoors',
    ],
    'Bebés y Maternidad': [
        'Pañales y Toallitas', 'Lactancia y Alimentación', 'Paseo y Viaje',
        'Higiene y Cuidado del Bebé', 'Cuarto del Bebé',
    ],
    'Juegos y Juguetes': [
        'Juguetes para Bebés', 'Muñecas y Peluches', 'Figuras de Acción',
        'Juegos de Mesa y Rompecabezas', 'Bloques y Construcción', 'Juguetes de Exterior',
    ],
    'Mascotas': [
        'Perros', 'Gatos', 'Higiene y Salud Animal',
    ],
    'Papelería, Oficina y Libros': [
        'Útiles Escolares', 'Oficina', 'Libros',
    ],
    'Instrumentos Musicales': [
        'Guitarras y Bajos', 'Teclados y Pianos', 'Baterías y Percusión',
        'Instrumentos de Viento', 'Instrumentos de Cuerda', 'Audio Profesional y DJ',
        'Accesorios Musicales',
    ],
}


def render_catalog_for_prompt() -> str:
    """Una línea por categoría: 'Categoría: Sub1 | Sub2 | ...'."""
    return "\n".join(
        f"- {category}: {' | '.join(subcategories)}"
        for category, subcategories in CATALOG_TAXONOMY.items()
    )
