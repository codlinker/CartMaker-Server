import json
import uuid
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# 1. ESTRUCTURA OFICIAL DEL CATÁLOGO (14 CATEGORÍAS Y 72 SUBCATEGORÍAS)
# ==============================================================================

CATALOGO_ESTRUCTURA: List[Dict[str, Any]] = [
    {
        "categoria": "Alimentos y Bebidas",
        "imagen": "static/img/categories/alimentos_y_bebidas.jpg",
        "subcategorias": [
            {"nombre": "Víveres y Granos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/viveres_y_granos.jpg"},
            {"nombre": "Frutas, Verduras y Hortalizas", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/frutas_verduras_y_hortalizas.jpg"},
            {"nombre": "Carnicería y Aves", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/carniceria_y_aves.jpg"},
            {"nombre": "Pescadería y Mariscos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/pescaderia_y_mariscos.jpg"},
            {"nombre": "Charcutería", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/charcuteria.jpg"},
            {"nombre": "Lácteos y Huevos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/lacteos_y_huevos.jpg"},
            {"nombre": "Panadería y Pastelería", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/panaderia_y_pasteleria.jpg"},
            {"nombre": "Enlatados y Conservas", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/enlatados_y_conservas.jpg"},
            {"nombre": "Salsas, Condimentos y Aceites", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/salsas_condimentos_y_aceites.jpg"},
            {"nombre": "Café, Té e Infusiones", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/cafe_te_e_infusiones.jpg"},
            {"nombre": "Bebidas, Refrescos y Maltas", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/bebidas_refrescos_y_maltas.jpg"},
            {"nombre": "Licores", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/licores.jpg"},
            {"nombre": "Chucherías, Snacks y Dulces", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/chucherias_snacks_y_dulces.jpg"},
            {"nombre": "Congelados y Pasapalos", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/congelados_y_pasapalos.jpg"},
            {"nombre": "Avena y Cereales", "imagen": "static/img/categories/sub_categories/alimentos_y_bebidas/avena_y_cereales.jpg"}
        ]
    },
    {
        "categoria": "Tecnología y Electrónica",
        "imagen": "static/img/categories/tecnologia_y_electronica.jpg",
        "subcategorias": [
            {"nombre": "Teléfonos y Tablets", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/telefonos_y_tablets.jpg"},
            {"nombre": "Computadoras y Laptops", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/computadoras_y_laptops.jpg"},
            {"nombre": "Componentes de PC y Hardware", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/componentes_de_pc_y_hardware.jpg"},
            {"nombre": "Almacenamiento y Memorias", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/almacenamiento_y_memorias.jpg"},
            {"nombre": "Monitores y Televisores", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/monitores_y_televisores.jpg"},
            {"nombre": "Impresoras y Escaners", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/impresoras_y_escaners.jpg"},
            {"nombre": "Smartwatches y Wearables", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/smartwatches_y_wearables.jpg"},
            {"nombre": "Cámaras y Fotografía", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/camaras_y_fotografia.jpg"},
            {"nombre": "Audífonos y Cornetas", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/audifonos_y_cornetas.jpg"},
            {"nombre": "Teclados y Mouse", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/teclados_y_mouse.jpg"},
            {"nombre": "Redes, Routers y Conectividad", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/redes_routers_y_conectividad.jpg"},
            {"nombre": "Consolas y Videojuegos", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/consolas_y_videojuegos.jpg"},
            {"nombre": "Cargadores, Cables y Powerbanks", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/cargadores_cables_y_powerbanks.jpg"},
            {"nombre": "Reguladores, Protectores y UPS", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/reguladores_protectores_y_ups.jpg"},
            {"nombre": "Smart Home y Domótica", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/smart_home_y_domotica.jpg"},
            {"nombre": "Seguridad y Cámaras de Vigilancia", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/seguridad_y_camaras_de_vigilancia.jpg"},
            {"nombre": "Proyectores y Video Beam", "imagen": "static/img/categories/sub_categories/tecnologia_y_electronica/proyectores_y_video_beam.jpg"},
        ],
    },
    {
        "categoria": "Ropa y Accesorios",
        "imagen": "static/img/categories/ropa_y_accesorios.jpg",
        "subcategorias": [
            {"nombre": "Blusas, Tops y Franelas de Dama", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/blusas_tops_y_franelas_de_dama.jpg"},
            {"nombre": "Vestidos, Faldas y Enterizos", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/vestidos_faldas_y_enterizos.jpg"},
            {"nombre": "Pantalones, Jeans y Leggings de Dama", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/pantalones_jeans_y_leggings_de_dama.jpg"},
            {"nombre": "Franelas, Chemises y Camisas de Caballero", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/franelas_chemises_y_camisas_de_caballero.jpg"},
            {"nombre": "Pantalones, Jeans y Bermudas de Caballero", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/pantalones_jeans_y_bermudas_de_caballero.jpg"},
            {"nombre": "Ropa Deportiva, Monos y Fitness", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_deportiva_y_fitness.jpg"},
            {"nombre": "Trajes de Baño y Ropa Playera", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/trajes_de_bano_y_ropa_playera.jpg"},
            {"nombre": "Ropa Íntima, Lencería y Pijamas", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_intima_y_pijamas.jpg"},
            {"nombre": "Ropa para Niños y Niñas", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_para_ninos_y_ninas.jpg"},
            {"nombre": "Ropa para Bebés", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/ropa_para_bebes.jpg"},
            {"nombre": "Zapatos Deportivos y de Goma", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/zapatos_deportivos_y_de_goma.jpg"},
            {"nombre": "Cholas, Zandalias y Tacones", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/cholas_sandalias_y_tacones.jpg"},
            {"nombre": "Zapatos Casuales y Formales", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/zapatos_casuales_y_formales.jpg"},
            {"nombre": "Bolsos y Carteras", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/bolsos_y_carteras.jpg"},
            {"nombre": "Billeteras y Monederos", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/billeteras_y_monederos.jpg"},
            {"nombre": "Joyería y Bisutería", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/joyeria_y_bisuteria.jpg"},
            {"nombre": "Lentes y Relojes", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/lentes_y_relojes.jpg"},
            {"nombre": "Gorras, Sombreros y Correas", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/gorras_sombreros_y_correas.jpg"},
            {"nombre": "Maletas y Bolsos de Viaje", "imagen": "static/img/categories/sub_categories/ropa_y_accesorios/maletas_y_bolsos_de_viaje.jpg"}
        ]
    },
    {
        "categoria": "Salud y Belleza",
        "imagen": "static/img/categories/salud_y_belleza.jpg",
        "subcategorias": [
            {"nombre": "Cuidado Personal", "imagen": "static/img/categories/sub_categories/salud_y_belleza/cuidado_personal.jpg"},
            {"nombre": "Skincare y Cuidado Facial", "imagen": "static/img/categories/sub_categories/salud_y_belleza/skincare_y_cuidado_facial.jpg"},
            {"nombre": "Maquillaje", "imagen": "static/img/categories/sub_categories/salud_y_belleza/maquillaje.jpg"},
            {"nombre": "Perfumería", "imagen": "static/img/categories/sub_categories/salud_y_belleza/perfumeria.jpg"},
            {"nombre": "Farmacia y Bienestar", "imagen": "static/img/categories/sub_categories/salud_y_belleza/farmacia_y_bienestar.jpg"},
        ],
    },
    {
        "categoria": "Hogar, Muebles y Jardín",
        "imagen": "static/img/categories/hogar_muebles_y_jardin.jpg",
        "subcategorias": [
            {"nombre": "Electrodomésticos", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/electrodomesticos.jpg"},
            {"nombre": "Muebles", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/muebles.jpg"},
            {"nombre": "Dormitorio", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/dormitorio.jpg"},
            {"nombre": "Baño", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/bano.jpg"},
            {"nombre": "Decoración", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/decoracion.jpg"},
            {"nombre": "Jardín y Exteriores", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/jardin_y_exteriores.jpg"},
            {"nombre": "Limpieza del Hogar", "imagen": "static/img/categories/sub_categories/hogar_muebles_y_jardin/limpieza_del_hogar.jpg"},
        ],
    },
    {
        "categoria": "Ferretería y Construcción",
        "imagen": "static/img/categories/ferreteria_y_construccion.jpg",
        "subcategorias": [
            {"nombre": "Herramientas", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/herramientas.jpg"},
            {"nombre": "Electricidad e Iluminación", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/electricidad_e_iluminacion.jpg"},
            {"nombre": "Plomería", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/plomeria.jpg"},
            {"nombre": "Materiales de Construcción", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/materiales_de_construccion.jpg"},
            {"nombre": "Seguridad y Domótica", "imagen": "static/img/categories/sub_categories/ferreteria_y_construccion/seguridad_y_domotica.jpg"},
        ],
    },
    {
        "categoria": "Carros, Motos y Otros",
        "imagen": "static/img/categories/carros_motos_y_otros.jpg",
        "subcategorias": [
            {"nombre": "Venta de Autos", "imagen": "static/img/categories/sub_categories/carros_motos_y_otros/venta_de_autos.jpg"},
            {"nombre": "Venta de Motos", "imagen": "static/img/categories/sub_categories/carros_motos_y_otros/venta_de_motos.jpg"},
            {"nombre": "Repuestos para Autos", "imagen": "static/img/categories/sub_categories/carros_motos_y_otros/repuestos_para_autos.jpg"},
            {"nombre": "Lubricantes y Fluidos", "imagen": "static/img/categories/sub_categories/carros_motos_y_otros/lubricantes_y_fluidos.jpg"},
            {"nombre": "Neumáticos y Rines", "imagen": "static/img/categories/sub_categories/carros_motos_y_otros/neumaticos_y_rines.jpg"},
            {"nombre": "Accesorios para Vehículos", "imagen": "static/img/categories/sub_categories/carros_motos_y_otros/accesorios_para_vehiculos.jpg"},
            {"nombre": "Motos", "imagen": "static/img/categories/sub_categories/carros_motos_y_otros/motos.jpg"},
        ],
    },
    {
        "categoria": "Deportes y Fitness",
        "imagen": "static/img/categories/deportes_y_fitness.jpg",
        "subcategorias": [
            {"nombre": "Fitness y Musculación", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/fitness_y_musculacion.jpg"},
            {"nombre": "Ropa y Calzado Deportivo", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/ropa_y_calzado_deportivo.jpg"},
            {"nombre": "Deportes Específicos", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/deportes_especificos.jpg"},
            {"nombre": "Camping y Outdoors", "imagen": "static/img/categories/sub_categories/deportes_y_fitness/camping_y_outdoors.jpg"},
        ],
    },
    {
        "categoria": "Bebés y Maternidad",
        "imagen": "static/img/categories/bebes_y_maternidad.jpg",
        "subcategorias": [
            {"nombre": "Pañales y Toallitas", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/panales_y_toallitas.jpg"},
            {"nombre": "Lactancia y Alimentación", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/lactancia_y_alimentacion.jpg"},
            {"nombre": "Paseo y Viaje", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/paseo_y_viaje.jpg"},
            {"nombre": "Higiene y Cuidado del Bebé", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/higiene_y_cuidado_del_bebe.jpg"},
            {"nombre": "Cuarto del Bebé", "imagen": "static/img/categories/sub_categories/bebes_y_maternidad/cuarto_del_bebe.jpg"},
        ],
    },
    {
        "categoria": "Juegos y Juguetes",
        "imagen": "static/img/categories/juegos_y_juguetes.jpg",
        "subcategorias": [
            {"nombre": "Juguetes para Bebés", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/juguetes_para_bebes.jpg"},
            {"nombre": "Muñecas y Peluches", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/munecas_y_peluches.jpg"},
            {"nombre": "Figuras de Acción", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/figuras_de_accion.jpg"},
            {"nombre": "Juegos de Mesa y Rompecabezas", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/juegos_de_mesa_y_rompecabezas.jpg"},
            {"nombre": "Bloques y Construcción", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/bloques_y_construccion.jpg"},
            {"nombre": "Juguetes de Exterior", "imagen": "static/img/categories/sub_categories/juegos_y_juguetes/juguetes_de_exterior.jpg"},
        ],
    },
    {
        "categoria": "Mascotas",
        "imagen": "static/img/categories/mascotas.jpg",
        "subcategorias": [
            {"nombre": "Perros", "imagen": "static/img/categories/sub_categories/mascotas/perros.jpg"},
            {"nombre": "Gatos", "imagen": "static/img/categories/sub_categories/mascotas/gatos.jpg"},
            {"nombre": "Higiene y Salud Animal", "imagen": "static/img/categories/sub_categories/mascotas/higiene_y_salud_animal.jpg"},
        ],
    },
    {
        "categoria": "Papelería, Oficina y Libros",
        "imagen": "static/img/categories/papeleria_oficina_y_libros.jpg",
        "subcategorias": [
            {"nombre": "Útiles Escolares", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/utiles_escolares.jpg"},
            {"nombre": "Oficina", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/oficina.jpg"},
            {"nombre": "Libros", "imagen": "static/img/categories/sub_categories/papeleria_oficina_y_libros/libros.jpg"},
        ],
    },
    {
        "categoria": "Instrumentos Musicales",
        "imagen": "static/img/categories/instrumentos_musicales.jpg",
        "subcategorias": [
            {"nombre": "Guitarras y Bajos", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/guitarras_y_bajos.jpg"},
            {"nombre": "Teclados y Pianos", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/teclados_y_pianos.jpg"},
            {"nombre": "Baterías y Percusión", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/baterias_y_percusion.jpg"},
            {"nombre": "Instrumentos de Viento", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/instrumentos_de_viento.jpg"},
            {"nombre": "Instrumentos de Cuerda", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/instrumentos_de_cuerda.jpg"},
            {"nombre": "Audio Profesional y DJ", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/audio_profesional_y_dj.jpg"},
            {"nombre": "Accesorios Musicales", "imagen": "static/img/categories/sub_categories/instrumentos_musicales/accesorios_musicales.jpg"},
        ],
    },
    {
        "categoria": "Otras Categorías",
        "imagen": "static/img/categories/otras_categorias.jpg",
        "subcategorias": [
            {"nombre": "Otros", "imagen": "static/img/categories/sub_categories/otras_categorias/otros.jpg"},
        ],
    },
]

# Mapeo de nombres antiguos/legacy a las 14 categorías oficiales
LEGACY_CATEGORY_TO_OFFICIAL_MAP: Dict[str, str] = {
    "Alimentos y Bebidas (Supermercado)": "Alimentos y Bebidas",
    "Alimentos y Bebidas": "Alimentos y Bebidas",
    "Restaurantes y Comida Preparada": "Alimentos y Bebidas",
    "Hogar y Electrodomésticos": "Hogar, Muebles y Jardín",
    "Automotriz y Repuestos": "Carros, Motos y Otros",
    "Deportes y Aire Libre": "Deportes y Fitness",
    "Juguetes y Entretenimiento": "Juegos y Juguetes",
    "Ferretería y Herramientas": "Ferretería y Construcción",
    "Educación, Libros y Papelería": "Papelería, Oficina y Libros",
    "Servicios Profesionales": "Otras Categorías",
    "Otras Categorías (Varios)": "Otras Categorías",
    "Otros": "Otras Categorías",
}

# Mapeo de subcategorías anteriores/renombradas a las nuevas subcategorías oficiales
LEGACY_SUBCATEGORY_TO_OFFICIAL_MAP: Dict[str, str] = {
    # Alimentos y Bebidas
    "Despensa y Víveres": "Víveres y Granos",
    "Frescos": "Frutas, Verduras y Hortalizas",
    "Charcutería y Lácteos": "Charcutería",
    "Bebidas": "Bebidas, Refrescos y Maltas",
    "Snacks y Dulces": "Chucherías, Snacks y Dulces",
    # Tecnología y Electrónica
    "Celulares y Tablets": "Teléfonos y Tablets",
    "Computación": "Computadoras y Laptops",
    "TV, Audio y Video": "Monitores y Televisores",
    "Videojuegos y Consolas": "Consolas y Videojuegos",
    "Wearables": "Smartwatches y Wearables",
    "Audífonos y Parlantes": "Audífonos y Cornetas",
    "Periféricos y Accesorios": "Teclados y Mouse",
    "Accesorios": "Cargadores, Cables y Powerbanks",
}


# ==============================================================================
# 2. CATÁLOGO DE UNIDADES DE VENTA (SELLING UNITS)
# ==============================================================================

SELLING_UNITS_CATALOG: Dict[str, Dict[str, Any]] = {
    "unit": {
        "code": "unit",
        "label": "Unidad",
        "short_label": "und",
        "price_label": "Precio por unidad",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "kg": {
        "code": "kg",
        "label": "Kilogramo (kg)",
        "short_label": "kg",
        "price_label": "Precio por kg",
        "allow_fractional": True,
        "default_step": 0.25,
        "default_min": 0.25,
    },
    "g": {
        "code": "g",
        "label": "Gramos (g)",
        "short_label": "g",
        "price_label": "Precio por cada 100g / porción en g",
        "allow_fractional": False,
        "default_step": 100.0,
        "default_min": 100.0,
    },
    "lb": {
        "code": "lb",
        "label": "Libra (lb)",
        "short_label": "lb",
        "price_label": "Precio por libra",
        "allow_fractional": True,
        "default_step": 0.5,
        "default_min": 0.5,
    },
    "l": {
        "code": "l",
        "label": "Litro (L)",
        "short_label": "L",
        "price_label": "Precio por litro",
        "allow_fractional": True,
        "default_step": 0.5,
        "default_min": 0.5,
    },
    "ml": {
        "code": "ml",
        "label": "Mililitros (ml)",
        "short_label": "ml",
        "price_label": "Precio por envase / ml",
        "allow_fractional": False,
        "default_step": 100.0,
        "default_min": 100.0,
    },
    "pack": {
        "code": "pack",
        "label": "Empaque / Paquete",
        "short_label": "paq",
        "price_label": "Precio por paquete",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "box": {
        "code": "box",
        "label": "Caja / Bulto",
        "short_label": "caja",
        "price_label": "Precio por caja/bulto",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "portion": {
        "code": "portion",
        "label": "Porción / Ración / Plato",
        "short_label": "porción",
        "price_label": "Precio por porción",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "combo": {
        "code": "combo",
        "label": "Combo / Promoción",
        "short_label": "combo",
        "price_label": "Precio del combo",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "pair": {
        "code": "pair",
        "label": "Par",
        "short_label": "par",
        "price_label": "Precio por par",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "set": {
        "code": "set",
        "label": "Set / Juego",
        "short_label": "set",
        "price_label": "Precio por set",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "m": {
        "code": "m",
        "label": "Metro lineal (m)",
        "short_label": "m",
        "price_label": "Precio por metro",
        "allow_fractional": True,
        "default_step": 0.5,
        "default_min": 0.5,
    },
    "m2": {
        "code": "m2",
        "label": "Metro cuadrado (m²)",
        "short_label": "m²",
        "price_label": "Precio por m²",
        "allow_fractional": True,
        "default_step": 1.0,
        "default_min": 1.0,
    },
    "gal": {
        "code": "gal",
        "label": "Galón / Cuñete",
        "short_label": "gal",
        "price_label": "Precio por galón",
        "allow_fractional": False,
        "default_step": 1.0,
        "default_min": 1.0,
    },
}


def _units(*codes: str) -> List[Dict[str, Any]]:
    return [SELLING_UNITS_CATALOG[c] for c in codes if c in SELLING_UNITS_CATALOG]


# ==============================================================================
# 3. ARQUETIPOS BASE DE ESQUEMAS DINÁMICOS
# ==============================================================================

def _build_schema(
    *,
    archetype: str,
    ui_hint: str,
    buyer_ui_hint: str,
    allowed_units: List[str],
    default_unit: str = "unit",
    supports_variants: bool = True,
    variant_config: Optional[Dict[str, Any]] = None,
    supports_modifier_groups: bool = False,
    modifier_group_presets: Optional[List[Dict[str, Any]]] = None,
    order_notes_enabled: bool = True,
    order_notes_placeholder: str = "Indicaciones adicionales para este producto (opcional)",
    fields: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    default_unit_info = SELLING_UNITS_CATALOG.get(default_unit, SELLING_UNITS_CATALOG["unit"])
    return {
        "schema_version": 1,
        "archetype": archetype,
        "ui_hint": ui_hint,
        "buyer_ui_hint": buyer_ui_hint,
        "allowed_selling_unit_codes": allowed_units,
        "allowed_selling_units": _units(*allowed_units),
        "default_selling_unit": default_unit,
        "default_allow_fractional": default_unit_info["allow_fractional"],
        "default_unit_step": default_unit_info["default_step"],
        "default_min_order_quantity": default_unit_info["default_min"],
        "supports_variants": supports_variants,
        "variant_config": variant_config or {
            "enabled": supports_variants,
            "label": "Variantes / Presentaciones",
            "axes": [],
        },
        "supports_modifier_groups": supports_modifier_groups,
        "modifier_group_presets": modifier_group_presets or [],
        "order_notes_enabled": order_notes_enabled,
        "order_notes_placeholder": order_notes_placeholder,
        "fields": fields or [],
    }


def _warranty_field(placeholder: str = "Ej: 30 días, 6 meses o 1 año") -> Dict[str, Any]:
    return {
        "key": "garantia",
        "label": "Garantía",
        "type": "warranty",
        "required": False,
        "unit_options": ["días", "meses", "años", "sin garantía"],
        "default_unit": "meses",
        "options": [
            "Sin garantía",
            "7 días",
            "15 días",
            "30 días",
            "3 meses",
            "6 meses",
            "1 año",
            "2 años",
            "3 años",
            "5 años",
        ],
        "placeholder": placeholder,
        "helper_text": "Puedes indicar cantidad y unidad (días, meses o años) o seleccionar una opción rápida.",
        "section": "condition",
    }


# ==============================================================================
# 4. DEFINICIÓN ESPECÍFICA POR SUBCATEGORÍA (72 SUBCATEGORÍAS)
# ==============================================================================

SUBCATEGORY_SCHEMAS: Dict[str, Dict[str, Any]] = {
    # --------------------------------------------------------------------------
    # 1. ALIMENTOS Y BEBIDAS (SUPERMERCADO)
    # --------------------------------------------------------------------------
    "Frescos": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Ideal para frutas, verduras, plátanos, cambures, carnes, aves y pescados. Puedes vender por kilogramo (kg), gramos (g), bandeja/paquete o unidad, y ofrecer cortes o niveles de maduración.",
        buyer_ui_hint="Elige el peso en kilogramos/gramos o la presentación, y especifica cómo lo prefieres (ej. maduro, verde, picado).",
        allowed_units=["kg", "g", "lb", "unit", "pack", "portion"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentaciones o Pesos Predefinidos",
            "helper_text": "Opcional: define presentaciones listas para llevar (ej. Bandeja 500g, Paquete 1kg) con su precio exacto.",
            "axes": [
                {
                    "key": "presentation",
                    "label": "Presentación / Peso",
                    "type": "select",
                    "presets": ["250 g", "500 g", "1 kg", "Bandeja", "Unidad", "Mano / Racimo"],
                },
                {
                    "key": "ripeness_or_cut",
                    "label": "Maduración / Tipo de Corte",
                    "type": "select",
                    "presets": ["Verde", "Pintón", "Maduro", "Entero", "Fileteado", "Molido", "En trozos"],
                },
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Preferencia de Maduración",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Verde", "price_delta": 0.0},
                    {"name": "Pintón (Semi-maduro)", "price_delta": 0.0},
                    {"name": "Maduro (Para hoy)", "price_delta": 0.0},
                ],
            },
            {
                "name": "Preparación / Corte",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Entero", "price_delta": 0.0},
                    {"name": "En ruedas / rebanado", "price_delta": 0.0},
                    {"name": "Limpio y fileteado", "price_delta": 0.0},
                ],
            },
        ],
        order_notes_enabled=True,
        order_notes_placeholder="Ej: 2 plátanos maduros y 2 pintones, o carne limpia sin grasa...",
        fields=[
            {
                "key": "tipo_fresco",
                "label": "Tipo de Producto Fresco",
                "type": "select",
                "required": False,
                "options": ["Frutas", "Verduras y Hortalizas", "Carnes Rojas", "Pollo y Aves", "Pescados y Mariscos", "Huevos", "Hierbas y Aliños"],
                "section": "details",
            },
            {
                "key": "estado_conservacion",
                "label": "Estado de Conservación",
                "type": "select",
                "required": False,
                "options": ["Fresco del día", "Refrigerado", "Congelado", "Al vacío"],
                "section": "specs",
            },
            {
                "key": "peso_aproximado_unidad",
                "label": "Peso aproximado por unidad/bandeja",
                "type": "text",
                "required": False,
                "placeholder": "Ej: 200g por unidad aprox.",
                "section": "specs",
            },
            {
                "key": "origen",
                "label": "Origen / Procedencia",
                "type": "text",
                "required": False,
                "placeholder": "Ej: Nacional (Mérida / Colonia Tovar) o Importado",
                "section": "details",
            },
        ],
    ),
    "Charcutería y Lácteos": _build_schema(
        archetype="fresh_weight_and_portion",
        ui_hint="Para quesos, jamones, embutidos y lácteos. Puedes vender por kg, gramos, paquete o unidad, y ofrecer opciones de rebanado o rallado.",
        buyer_ui_hint="Selecciona cuántos gramos o kilos deseas y cómo prefieres el corte (rebanado fino, grueso, entero o rallado).",
        allowed_units=["kg", "g", "unit", "pack", "l"],
        default_unit="kg",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentaciones por Peso",
            "helper_text": "Define precios por peso (ej. 250g, 500g, 1kg) o por pieza entera.",
            "axes": [
                {
                    "key": "weight_option",
                    "label": "Peso / Presentación",
                    "type": "select",
                    "presets": ["200 g", "250 g", "500 g", "1 kg", "Pieza entera", "Empaque sellado"],
                },
                {
                    "key": "cut_style",
                    "label": "Tipo de Corte",
                    "type": "select",
                    "presets": ["Rebanado fino", "Rebanado normal", "Trozos / Taco", "Rallado"],
                },
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Tipo de Corte",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Rebanado fino", "price_delta": 0.0},
                    {"name": "Rebanado mediano", "price_delta": 0.0},
                    {"name": "En trozo / entero", "price_delta": 0.0},
                    {"name": "Rallado", "price_delta": 0.0},
                ],
            }
        ],
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Jamón rebanado bien finito, con separadores...",
        fields=[
            {
                "key": "marca",
                "label": "Marca",
                "type": "text",
                "required": False,
                "placeholder": "Ej: Plumrose, Paisa, Los Andes, Artesanal",
                "section": "details",
            },
            {
                "key": "tipo_producto",
                "label": "Tipo de Lácteo / Charcutería",
                "type": "select",
                "required": False,
                "options": ["Queso Blanco / Fresco", "Queso Amarillo / Madurado", "Jamón y Embutidos", "Leche y Crema", "Yogurt", "Mantequilla y Margarina"],
                "section": "details",
            },
            {
                "key": "requiere_refrigeracion",
                "label": "Requiere Refrigeración",
                "type": "boolean",
                "required": False,
                "section": "specs",
            },
        ],
    ),
    "Despensa y Víveres": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Ideal para harinas, arroz, pasta, granos, aceites, salsas, enlatados y también comida lista/preparada. Puedes vender por unidad, paquete, bulto, kg o porción.",
        buyer_ui_hint="Elige la presentación, versión o adicionales disponibles.",
        allowed_units=["unit", "pack", "box", "kg", "g", "l", "ml", "portion", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Tamaño / Versión",
            "axes": [
                {
                    "key": "presentation",
                    "label": "Contenido / Tamaño",
                    "type": "select",
                    "presets": ["250 g", "500 g", "1 kg", "1 Litro", "Individual", "Mediano", "Familiar", "Bulto"],
                }
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Versión / Proteína",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Clásica / Tradicional", "price_delta": 0.0},
                    {"name": "Especial / Doble", "price_delta": 2.0},
                ],
            },
            {
                "name": "Extras y Adicionales",
                "required": False,
                "min_selections": 0,
                "max_selections": 5,
                "options": [
                    {"name": "Extra Queso", "price_delta": 1.0},
                    {"name": "Extra Tocineta", "price_delta": 1.5},
                    {"name": "Papas Fritas / Contorno", "price_delta": 2.0},
                ],
            },
        ],
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Sin cebolla, salsas aparte, o especificación de marca...",
        fields=[
            {
                "key": "marca",
                "label": "Marca",
                "type": "text",
                "required": False,
                "placeholder": "Ej: PAN, Primor, Mary, Mavesa, Heinz",
                "section": "details",
            },
            {
                "key": "contenido_neto",
                "label": "Contenido Neto",
                "type": "text",
                "required": False,
                "placeholder": "Ej: 1 kg, 500 g, 900 ml",
                "section": "specs",
            },
            {
                "key": "tipo_empaque",
                "label": "Tipo de Empaque",
                "type": "select",
                "required": False,
                "options": ["Paquete / Bolsa", "Caja", "Botella", "Frasco de Vidrio", "Lata", "Envase Plástico", "Bulto Cerrado", "Envase para llevar"],
                "section": "specs",
            },
            {
                "key": "tiempo_preparacion_min",
                "label": "Tiempo de preparación (si es comida preparada)",
                "type": "number",
                "required": False,
                "unit_suffix": "min",
                "placeholder": "Ej: 20",
                "section": "specs",
            },
        ],
    ),
    "Bebidas": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Refrescos, agua, jugos, café, té, malta y batidos. Configura tamaños (ej. 355ml, 1.5L, 2L) o temperatura (frío/natural).",
        buyer_ui_hint="Elige el tamaño o sabor de tu bebida.",
        allowed_units=["unit", "pack", "box", "l", "ml"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Sabor / Empaque",
            "axes": [
                {
                    "key": "volume",
                    "label": "Volumen / Presentación",
                    "type": "select",
                    "presets": ["Lata 355 ml", "Botella 500 ml", "1 Litro", "1.5 Litros", "2 Litros", "Botellón 5L", "Six-Pack", "Caja x24"],
                },
                {
                    "key": "flavor",
                    "label": "Sabor / Variante",
                    "type": "text",
                    "presets": ["Original", "Sin Azúcar / Zero", "Naranja", "Limón", "Durazno", "Manzana"],
                },
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Temperatura",
                "required": False,
                "min_selections": 0,
                "max_selections": 1,
                "options": [
                    {"name": "Bien fría (De nevera)", "price_delta": 0.0},
                    {"name": "Al clima / Natural", "price_delta": 0.0},
                ],
            }
        ],
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pepsi, Coca-Cola, Maltín Polar, Minalba", "section": "details"},
            {"key": "volumen_neto", "label": "Volumen Neto", "type": "text", "required": False, "placeholder": "Ej: 1.5 L, 355 ml", "section": "specs"},
            {"key": "retornable", "label": "Envase Retornable", "type": "boolean", "required": False, "section": "specs"},
            {"key": "sin_azucar", "label": "Sin Azúcar / Light", "type": "boolean", "required": False, "section": "details"},
        ],
    ),
    "Licores": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Cervezas, rones, whiskies, vinos, espumantes y sangrías. Especifica el volumen (ej. 0.70L, 0.75L) o presentación (unidad, six-pack, caja).",
        buyer_ui_hint="Selecciona la presentación (botella, six-pack o caja).",
        allowed_units=["unit", "pack", "box", "l", "ml"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación de Venta",
            "axes": [
                {
                    "key": "presentation",
                    "label": "Presentación",
                    "type": "select",
                    "presets": ["Unidad / Botella", "Lata 355 ml", "Six-Pack (6 und)", "Caja (24 und)", "Caja (36 und)", "Botella 750 ml", "Botella 1 Litro"],
                }
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Preferencia de Entrega",
                "required": False,
                "min_selections": 0,
                "max_selections": 2,
                "options": [
                    {"name": "Frío (Listo para tomar)", "price_delta": 0.0},
                    {"name": "Agregar Bolsa de Hielo", "price_delta": 2.0},
                ],
            }
        ],
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Santa Teresa, Cacique, Polar, Zulia, Buchanan's", "section": "details"},
            {"key": "tipo_licor", "label": "Tipo de Bebida Alcohólica", "type": "select", "required": False, "options": ["Cerveza", "Ron", "Whisky", "Vino Tinto", "Vino Blanco / Rosado", "Espumante / Champagne", "Vodka / Ginebra / Tequila", "Sangría / Ponche"], "section": "details"},
            {"key": "volumen_neto", "label": "Volumen", "type": "text", "required": False, "placeholder": "Ej: 750 ml, 222 ml", "section": "specs"},
            {"key": "grado_alcoholico", "label": "Grado Alcohólico (%)", "type": "text", "required": False, "placeholder": "Ej: 40° GL / 4.5%", "section": "specs"},
        ],
    ),
    "Snacks y Dulces": _build_schema(
        archetype="prepared_or_beverage",
        ui_hint="Chucherías, chocolates, galletas, tortas, postres, helados, comida rápida y snacks. Puedes configurar sabores, tamaños, toppings y extras.",
        buyer_ui_hint="Elige el sabor, tamaño y tus toppings o extras favoritos.",
        allowed_units=["unit", "pack", "box", "portion", "combo", "kg", "g"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Sabores / Tamaños / Versiones",
            "axes": [
                {
                    "key": "flavor_or_version",
                    "label": "Sabor / Versión",
                    "type": "text",
                    "presets": ["Chocolate", "Vainilla", "Fresa", "Arequipe", "Queso", "Mixto", "Original", "Picante"],
                },
                {
                    "key": "size",
                    "label": "Tamaño / Porción",
                    "type": "select",
                    "presets": ["Individual", "Mediano", "Familiar", "Porción", "Torta Completa", "Combo"],
                },
            ],
        },
        supports_modifier_groups=True,
        modifier_group_presets=[
            {
                "name": "Toppings / Extras",
                "required": False,
                "min_selections": 0,
                "max_selections": 4,
                "options": [
                    {"name": "Extra Chocolate / Nutella", "price_delta": 1.5},
                    {"name": "Extra Arequipe", "price_delta": 1.0},
                    {"name": "Lluvia de chocolate / Oreo", "price_delta": 1.0},
                ],
            }
        ],
        order_notes_enabled=True,
        order_notes_placeholder="Ej: Dedicatoria o indicación especial de sabores...",
        fields=[
            {"key": "marca", "label": "Marca / Elaboración", "type": "text", "required": False, "placeholder": "Ej: Savoy, Puig, Frito-Lay, Artesanal", "section": "details"},
            {"key": "contenido_neto", "label": "Peso / Contenido", "type": "text", "required": False, "placeholder": "Ej: 150 g, Porción 250 g", "section": "specs"},
            {"key": "sabor_principal", "label": "Sabor Principal", "type": "text", "required": False, "placeholder": "Ej: Chocolate con Leche, Queso", "section": "details"},
        ],
    ),
    "Limpieza del Hogar": _build_schema(
        archetype="grocery_packaged",
        ui_hint="Detergentes, cloro, desinfectantes, lavaplatos, papel higiénico y bolsas. Puedes vender por unidad, litro/galón (también recarga) o bulto.",
        buyer_ui_hint="Selecciona el aroma y tamaño de presentación.",
        allowed_units=["unit", "l", "ml", "gal", "kg", "g", "pack", "box"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Aroma",
            "axes": [
                {
                    "key": "size",
                    "label": "Tamaño / Contenido",
                    "type": "select",
                    "presets": ["500 ml", "1 Litro", "Galón (3.78L)", "500 g", "1 kg", "2.5 kg", "Paquete 4 rollos", "Paquete 12 rollos"],
                },
                {
                    "key": "scent",
                    "label": "Aroma / Fragancia",
                    "type": "text",
                    "presets": ["Lavanda", "Bebé", "Limón", " Floral", "Pino", "Neutro / Original"],
                },
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Las Llaves, Ace, Ariel, Rosal, Mistolin", "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 1 Litro, 900 g, 4 Rollos", "section": "specs"},
            {"key": "fragancia", "label": "Fragancia", "type": "text", "required": False, "placeholder": "Ej: Lavanda, Limón", "section": "details"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 2. TECNOLOGÍA Y ELECTRÓNICA
    # --------------------------------------------------------------------------
    "Celulares y Tablets": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Especifica marca, modelo, almacenamiento, memoria RAM, estado del equipo y garantía. También puedes agregar variantes por color o capacidad.",
        buyer_ui_hint="Selecciona el color y la capacidad de almacenamiento antes de comprar.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color y Almacenamiento",
            "axes": [
                {
                    "key": "storage",
                    "label": "Almacenamiento",
                    "type": "select",
                    "presets": ["64 GB", "128 GB", "256 GB", "512 GB", "1 TB"],
                },
                {
                    "key": "color",
                    "label": "Color",
                    "type": "text",
                    "presets": ["Negro", "Blanco", "Plata", "Titanio Natural", "Azul", "Morado", "Dorado"],
                },
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "select", "required": True, "options": ["Apple", "Samsung", "Xiaomi / Redmi / POCO", "Motorola", "Infinix", "Tecno", "Honor", "Huawei", "Realme", "Google Pixel", "Otra"], "section": "details"},
            {"key": "modelo", "label": "Modelo Exacto", "type": "text", "required": True, "placeholder": "Ej: iPhone 15 Pro Max / Redmi Note 13 Pro", "section": "details"},
            {"key": "almacenamiento", "label": "Almacenamiento Interno", "type": "select", "required": False, "options": ["32 GB", "64 GB", "128 GB", "256 GB", "512 GB", "1 TB"], "section": "specs"},
            {"key": "ram", "label": "Memoria RAM", "type": "select", "required": False, "options": ["2 GB", "3 GB", "4 GB", "6 GB", "8 GB", "12 GB", "16 GB"], "section": "specs"},
            {"key": "condicion", "label": "Condición del Equipo", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Open Box", "Reacondicionado / Refurbished", "Usado - Como Nuevo", "Usado - Buen Estado"], "section": "condition"},
            {"key": "dual_sim", "label": "SIM / Conectividad", "type": "select", "required": False, "options": ["Dual SIM Física", "SIM Física + eSIM", "Solo eSIM", "Single SIM", "Solo Wi-Fi"], "section": "specs"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Computación": _build_schema(
        archetype="mobile_and_computing",
        ui_hint="Para laptops, PCs de escritorio, monitores, componentes y redes. Detalla procesador, RAM, disco SSD y estado.",
        buyer_ui_hint="Revisa las especificaciones técnicas y elige la configuración deseada.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Configuración (RAM / SSD / Color)",
            "axes": [
                {"key": "config", "label": "Configuración", "type": "text", "presets": ["8GB RAM / 256GB SSD", "16GB RAM / 512GB SSD", "16GB RAM / 1TB SSD", "32GB RAM / 1TB SSD"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Plata", "Gris Espacial", "Negro"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "select", "required": True, "options": ["Apple", "HP", "Dell", "Lenovo", "ASUS", "Acer", "MSI", "Samsung", "LG", "Gigabyte", "Otra"], "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: MacBook Air M3 / ThinkPad T14", "section": "details"},
            {"key": "procesador", "label": "Procesador", "type": "text", "required": False, "placeholder": "Ej: Intel Core i7-13620H / Apple M3 / Ryzen 7", "section": "specs"},
            {"key": "ram", "label": "Memoria RAM", "type": "select", "required": False, "options": ["4 GB", "8 GB", "16 GB", "24 GB", "32 GB", "64 GB"], "section": "specs"},
            {"key": "almacenamiento", "label": "Almacenamiento (SSD/HDD)", "type": "select", "required": False, "options": ["128 GB SSD", "256 GB SSD", "512 GB SSD", "1 TB SSD", "2 TB SSD", "1 TB HDD"], "section": "specs"},
            {"key": "pantalla", "label": "Tamaño de Pantalla", "type": "text", "required": False, "placeholder": "Ej: 15.6 pulgadas FHD 144Hz", "section": "specs"},
            {"key": "tarjeta_grafica", "label": "Tarjeta Gráfica (GPU)", "type": "text", "required": False, "placeholder": "Ej: NVIDIA RTX 4060 8GB / Integrada", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Open Box", "Reacondicionado", "Usado"], "section": "condition"},
            _warranty_field("Ej: 6 meses o 1 año"),
        ],
    ),
    "Periféricos y Accesorios": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Audífonos, cargadores, cables, forros, teclados, mouse, powerbanks y adaptadores. Indica la compatibilidad y tipo de conexión.",
        buyer_ui_hint="Elige el color o tipo de conector compatible con tu dispositivo.",
        allowed_units=["unit", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Conector / Modelo Compatible",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Transparente", "Azul", "Rosa"]},
                {"key": "connector_or_model", "label": "Conector / Compatibilidad", "type": "text", "presets": ["USB-C", "Lightning (iPhone)", "USB-A", "Inalámbrico Bluetooth"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Anker, Logitech, Razer, Apple, Genérico", "section": "details"},
            {"key": "conectividad", "label": "Tipo de Conexión", "type": "select", "required": False, "options": ["Bluetooth / Inalámbrico", "USB-C", "Lightning", "USB-A", "Jack 3.5mm", "HDMI", "No aplica"], "section": "specs"},
            {"key": "compatibilidad", "label": "Dispositivos Compatibles", "type": "text", "required": False, "placeholder": "Ej: iPhone 15 / Android / PC / Mac", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field("Ej: 30 días, 3 meses o 1 año"),
        ],
    ),
    "TV, Audio y Video": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Televisores Smart TV, cornetas, barras de sonido, TV Box y proyectores. Indica pulgadas, resolución y conectividad.",
        buyer_ui_hint="Verifica el tamaño, resolución y especificaciones del equipo.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Versión",
            "axes": [
                {"key": "size", "label": "Pulgadas / Modelo", "type": "text", "presets": ["32\"", "43\"", "50\"", "55\"", "65\"", "75\""]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Samsung, LG, Sony, JBL, Hisense, Xiaomi", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": False, "placeholder": "Ej: Crystal UHD 55CU7000 / JBL Charge 5", "section": "details"},
            {"key": "tamano_pulgadas", "label": "Tamaño de Pantalla (si es TV)", "type": "select", "required": False, "options": ["No aplica", "32 pulgadas", "40-43 pulgadas", "50 pulgadas", "55 pulgadas", "65 pulgadas", "70+ pulgadas"], "section": "specs"},
            {"key": "resolucion", "label": "Resolución", "type": "select", "required": False, "options": ["No aplica", "HD", "Full HD (1080p)", "4K UHD", "8K", "QLED / OLED"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 6 meses o 1 año"),
        ],
    ),
    "Videojuegos y Consolas": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Consolas, videojuegos físicos, controles y accesorios gamer. Especifica plataforma (PS5, Nintendo Switch, Xbox, PC) y condición.",
        buyer_ui_hint="Elige la plataforma o edición disponible.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Plataforma / Edición / Color",
            "axes": [
                {"key": "platform", "label": "Plataforma", "type": "select", "presets": ["PlayStation 5", "PlayStation 4", "Nintendo Switch", "Xbox Series X/S", "PC"]},
                {"key": "edition", "label": "Edición / Color", "type": "text", "presets": ["Estándar", "Edición Disco", "Edición Digital", "OLED", "Blanco", "Negro"]},
            ],
        },
        fields=[
            {"key": "plataforma", "label": "Plataforma", "type": "select", "required": True, "options": ["PlayStation 5", "PlayStation 4", "Nintendo Switch", "Xbox Series X/S", "Xbox One", "PC Gaming", "Retro / Otra"], "section": "details"},
            {"key": "tipo_producto", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Consola", "Videojuego Físico", "Control / Mando", "Accesorios", "Tarjeta de Regalo"], "section": "details"},
            {"key": "almacenamiento", "label": "Capacidad (si es consola)", "type": "text", "required": False, "placeholder": "Ej: 1 TB SSD / 64 GB OLED", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo (Sellado)", "Usado - Como Nuevo", "Usado"], "section": "condition"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Wearables": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Smartwatches, bandas inteligentes y lentes inteligentes. Indica tamaño de caja (mm), color de correa y compatibilidad.",
        buyer_ui_hint="Selecciona el color de correa y tamaño de caja.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño de Caja y Color",
            "axes": [
                {"key": "case_size", "label": "Tamaño", "type": "select", "presets": ["40 mm", "41 mm", "42 mm", "44 mm", "45 mm", "46 mm", "49 mm", "Estándar"]},
                {"key": "color", "label": "Color / Correa", "type": "text", "presets": ["Negro", "Plata", "Blanco Estelar", "Rosa", "Azul"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Apple, Samsung, Xiaomi, Garmin, Huawei", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: Apple Watch Series 9 / Redmi Watch 4", "section": "details"},
            {"key": "compatibilidad", "label": "Compatibilidad", "type": "select", "required": False, "options": ["iOS y Android", "Solo iOS (iPhone)", "Solo Android"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 3 meses, 6 meses o 1 año"),
        ],
    ),
    "Cámaras y Fotografía": _build_schema(
        archetype="electronics_and_gaming",
        ui_hint="Cámaras profesionales, drones, cámaras de acción, lentes, aros de luz y micrófonos para creadores.",
        buyer_ui_hint="Revisa las especificaciones técnicas y accesorios incluidos.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Kit / Paquete",
            "axes": [
                {"key": "kit", "label": "Versión / Kit", "type": "text", "presets": ["Solo Cuerpo (Body)", "Con Lente 18-55mm", "Fly More Combo", "Kit Creador"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Sony, Canon, Nikon, DJI, GoPro, Godox", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: Sony ZV-E10 / DJI Mini 4 Pro", "section": "details"},
            {"key": "resolucion", "label": "Resolución / Sensor", "type": "text", "required": False, "placeholder": "Ej: 24.2 MP / Video 4K 60fps", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 6 meses o 1 año"),
        ],
    ),

    # --------------------------------------------------------------------------
    # 3. MODA Y ACCESORIOS
    # --------------------------------------------------------------------------
    "Ropa Femenina": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Agrega las tallas disponibles (XS, S, M, L, XL o numéricas) y los colores para que la compradora elija su combinación exacta al pedir.",
        buyer_ui_hint="Selecciona tu talla y color antes de agregar al carrito.",
        allowed_units=["unit", "set", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas y Colores Disponibles",
            "helper_text": "Agrega las combinaciones de talla y color en inventario.",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": ["Talla Única", "XS", "S", "M", "L", "XL", "XXL", "26", "28", "30", "32", "34"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Beige", "Rojo", "Azul", "Rosa", "Verde", "Estampado"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Zara, Shein, Bershka, Diseño Nacional", "section": "details"},
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Blusa / Top", "Vestido / Enterizo", "Jean / Pantalón", "Falda / Short", "Chaqueta / Suéter", "Traje de Baño", "Ropa Interior / Pijama", "Conjunto"], "section": "details"},
            {"key": "tela_material", "label": "Material / Tela", "type": "text", "required": False, "placeholder": "Ej: Algodón, Lino, Denim, Licra, Satén", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo con etiqueta", "Nuevo", "Second Hand / Pre-loved"], "section": "condition"},
        ],
    ),
    "Ropa Masculina": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Agrega las tallas (S, M, L, XL, XXL o tallas de pantalón 28-40) y colores disponibles.",
        buyer_ui_hint="Selecciona tu talla y color antes de agregar al carrito.",
        allowed_units=["unit", "set", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas y Colores Disponibles",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": ["S", "M", "L", "XL", "XXL", "28", "30", "32", "34", "36", "38", "40"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Azul Marino", "Gris", "Beige / Caqui", "Verde Oliva", "Vino"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Tommy Hilfiger, Levi's, Polo, Zara, Nacional", "section": "details"},
            {"key": "tipo_prenda", "label": "Tipo de Prenda", "type": "select", "required": False, "options": ["Franela / T-Shirt", "Camisa / Chemise", "Jean / Pantalón", "Bermuda / Short", "Suéter / Hoodie / Chaqueta", "Traje / Formal", "Ropa Interior / Medias"], "section": "details"},
            {"key": "corte_fit", "label": "Corte (Fit)", "type": "select", "required": False, "options": ["Regular Fit", "Slim Fit", "Oversize", "Relaxed Fit"], "section": "specs"},
            {"key": "tela_material", "label": "Material / Tela", "type": "text", "required": False, "placeholder": "Ej: 100% Algodón Pima, Lino, Gabardina", "section": "specs"},
        ],
    ),
    "Ropa Infantil": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Indica las tallas por meses o años (ej. 0-3M, 6-12M, 2T, 4, 6, 8, 10, 12, 14) y colores disponibles.",
        buyer_ui_hint="Elige la talla por edad/meses y el color.",
        allowed_units=["unit", "set", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas Infantiles y Colores",
            "axes": [
                {"key": "size", "label": "Talla (Meses / Años)", "type": "select", "presets": ["RN (Recién Nacido)", "0-3M", "3-6M", "6-9M", "9-12M", "12-18M", "2T", "3T", "4T", "Talla 6", "Talla 8", "Talla 10", "Talla 12", "Talla 14", "Talla 16"]},
                {"key": "color", "label": "Color / Diseño", "type": "text", "presets": ["Azul", "Rosa", "Blanco", "Amarillo", "Multicolor"]},
            ],
        },
        fields=[
            {"key": "genero", "label": "Género", "type": "select", "required": False, "options": ["Niña", "Niño", "Unisex / Bebé"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Carter's, OshKosh, EPK, Nacional", "section": "details"},
            {"key": "tela_material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: Algodón hipoalergénico", "section": "specs"},
        ],
    ),
    "Calzado": _build_schema(
        archetype="footwear",
        ui_hint="Agrega las tallas de calzado disponibles (ej. 35 al 45 EU o 5 al 12 US) y los colores de cada par.",
        buyer_ui_hint="Selecciona tu talla de calzado y color.",
        allowed_units=["pair", "unit"],
        default_unit="pair",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas de Calzado y Colores",
            "helper_text": "Indica los números disponibles y colores.",
            "axes": [
                {"key": "shoe_size", "label": "Talla (EU / Nacional)", "type": "select", "presets": ["35", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Marrón / Cuero", "Beige", "Azul", "Gris", "Multicolor"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Nike, Adidas, New Balance, Converse, Aldo, RS21", "section": "details"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Infantil"], "section": "details"},
            {"key": "sistema_talla", "label": "Sistema de Numeración", "type": "select", "required": False, "options": ["Europea / Nacional (35-45)", "Americana US (5-13)", "Infantil"], "section": "specs"},
            {"key": "material_exterior", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: Cuero, Gamuza, Sintético, Malla textil", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo en caja", "Nuevo sin caja", "Usado"], "section": "condition"},
        ],
    ),
    "Bolsos y Carteras": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Carteras, bandoleras, morrales, billeteras y maletas. Puedes agregar variantes por color o tamaño.",
        buyer_ui_hint="Selecciona el color o modelo disponible.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Colores / Tamaños",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Camel / Marrón", "Beige", "Blanco", "Rojo", "Dorado"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Michael Kors, Coach, Totto, Mario Hernández, Artesanal", "section": "details"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Cuero Genuino", "Cuero Sintético / PU", "Lona / Nylon", "Tela / Tejido", "Policarbonato"], "section": "specs"},
            {"key": "dimensiones", "label": "Dimensiones aproximadas", "type": "text", "required": False, "placeholder": "Ej: 25 x 18 x 10 cm", "section": "specs"},
        ],
    ),
    "Accesorios y Joyería": _build_schema(
        archetype="fashion_accessories",
        ui_hint="Relojes, cadenas, anillos, zarcillos, pulseras, lentes de sol y correas. Especifica el material (plata, oro, acero inoxidable) y talla/largo.",
        buyer_ui_hint="Elige el color/baño o medida.",
        allowed_units=["unit", "pair", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Acabado / Talla / Medida",
            "axes": [
                {"key": "finish", "label": "Color / Baño", "type": "select", "presets": ["Dorado", "Plateado", "Oro Rosa", "Acero", "Negro"]},
                {"key": "size", "label": "Talla / Medida", "type": "text", "presets": ["Ajustable", "Talla 6", "Talla 7", "Talla 8", "45 cm", "50 cm", "60 cm"]},
            ],
        },
        fields=[
            {"key": "material", "label": "Material Principal", "type": "select", "required": False, "options": ["Acero Inoxidable", "Plata 925", "Oro 18k / 10k", "Baño de Oro / Gold Filled", "Bisutería Fina", "Cuero", "Acetato / Metal"], "section": "specs"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Casio, Invicta, Pandora, Ray-Ban, Artesanal", "section": "details"},
            {"key": "resistente_agua", "label": "Resistente al Agua", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 4. SALUD Y BELLEZA
    # --------------------------------------------------------------------------
    "Cuidado Personal": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Shampoo, acondicionador, cremas corporales, desodorantes, tintes y cuidado capilar. Indica contenido en ml/g y tipo de cabello/piel.",
        buyer_ui_hint="Elige el aroma o presentación.",
        allowed_units=["unit", "pack", "set", "ml", "g"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Aroma / Tono",
            "axes": [
                {"key": "presentation", "label": "Presentación / Aroma", "type": "text", "presets": ["250 ml", "400 ml", "1 Litro", "Coco", "Argán", "Keratina"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pantene, Dove, Nivea, L'Oréal, Salerm, Karseell", "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 500 ml, 250 g", "section": "specs"},
            {"key": "tipo_cabello_piel", "label": "Ideal para", "type": "text", "required": False, "placeholder": "Ej: Todo tipo de piel / Cabello seco o teñido", "section": "specs"},
        ],
    ),
    "Skincare y Cuidado Facial": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Limpiadores, serums, hidratantes, protectores solares y mascarillas. Especifica tipo de piel, ingredientes activos y contenido.",
        buyer_ui_hint="Revisa el tipo de piel recomendado y contenido del envase.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Tipo de Piel",
            "axes": [
                {"key": "variant", "label": "Presentación", "type": "text", "presets": ["30 ml", "50 ml", "236 ml", "473 ml", "Piel Grasa", "Piel Seca", "Con Color", "Sin Color"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: CeraVe, La Roche-Posay, The Ordinary, Eucerin, Bioderma", "section": "details"},
            {"key": "tipo_piel", "label": "Tipo de Piel", "type": "select", "required": False, "options": ["Todo tipo de piel", "Piel Grasa / Mixta", "Piel Seca", "Piel Sensible", "Piel con tendencia acnéica"], "section": "specs"},
            {"key": "ingrediente_activo", "label": "Ingrediente Principal / FPS", "type": "text", "required": False, "placeholder": "Ej: Ácido Hialurónico, Niacinamida, Vitamina C, SPF 50+", "section": "specs"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 30 ml, 50 ml, 236 ml", "section": "specs"},
        ],
    ),
    "Maquillaje": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Bases, correctores, labiales, rubores, máscaras de pestañas y paletas. Agrega los tonos disponibles como variantes.",
        buyer_ui_hint="Selecciona tu tono o acabado antes de agregar al carrito.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tonos y Acabados Disponibles",
            "axes": [
                {"key": "shade", "label": "Tono / Número", "type": "text", "presets": ["Claro / Light", "Medio / Medium", "Bronce / Tan", "Rojo", "Nude", "Rosa", "Negro"]},
                {"key": "finish", "label": "Acabado", "type": "select", "presets": ["Mate", "Satinado / Glow", "Brillante / Gloss", "Waterproof (A prueba de agua)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Maybelline, MAC, Salomé, Dolce Bella, NYX, Rare Beauty", "section": "details"},
            {"key": "zona_aplicacion", "label": "Categoría de Maquillaje", "type": "select", "required": False, "options": ["Rostro (Base / Polvo / Corrector)", "Labios", "Ojos y Cejas", "Brochas y Esponjas", "Uñas"], "section": "details"},
            {"key": "acabado", "label": "Acabado", "type": "select", "required": False, "options": ["Mate", "Luminoso / Hidratante", "Natural", "Larga Duración / Waterproof"], "section": "specs"},
        ],
    ),
    "Perfumería": _build_schema(
        archetype="beauty_and_personal_care",
        ui_hint="Perfumes, colonias, splash y decants. Especifica volumen en ml, concentración (EDP, EDT, Parfum, Splash) y familia olfativa.",
        buyer_ui_hint="Elige el tamaño (ml) o presentación (frasco completo o decant).",
        allowed_units=["unit", "ml", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Volumen (ml)",
            "axes": [
                {"key": "volume", "label": "Presentación (ml)", "type": "select", "presets": ["Decant 5 ml", "Decant 10 ml", "30 ml", "50 ml", "100 ml", "200 ml", "250 ml (Splash)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Casa / Marca", "type": "text", "required": True, "placeholder": "Ej: Carolina Herrera, Dior, Lattafa, Victoria's Secret, Yanbal", "section": "details"},
            {"key": "concentracion", "label": "Concentración", "type": "select", "required": False, "options": ["Eau de Parfum (EDP)", "Eau de Toilette (EDT)", "Parfum / Extrait", "Body Mist / Splash", "Colonia"], "section": "specs"},
            {"key": "genero", "label": "Para quién", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex"], "section": "details"},
            {"key": "volumen_ml", "label": "Volumen", "type": "text", "required": False, "placeholder": "Ej: 100 ml", "section": "specs"},
        ],
    ),
    "Farmacia y Bienestar": _build_schema(
        archetype="pharmacy_and_wellness",
        ui_hint="Medicamentos OTC, vitaminas, suplementos, primeros auxilios y equipos médicos (tensiómetros, glucómetros). Especifica presentación y dosis.",
        buyer_ui_hint="Verifica la presentación (tabletas, jarabe, cápsulas) y concentración.",
        allowed_units=["unit", "box", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Concentración",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "text", "presets": ["Blíster x10", "Caja x20", "Caja x30", "Frasco 60 cápsulas", "Jarabe 120 ml"]},
            ],
        },
        fields=[
            {"key": "laboratorio_marca", "label": "Laboratorio / Marca", "type": "text", "required": False, "placeholder": "Ej: Calox, Leti, Genven, Now Foods, Centrum", "section": "details"},
            {"key": "principio_activo", "label": "Componente / Principio Activo", "type": "text", "required": False, "placeholder": "Ej: Vitamina C 500mg, Magnesio, Ibuprofeno", "section": "specs"},
            {"key": "forma_farmaceutica", "label": "Presentación", "type": "select", "required": False, "options": ["Tabletas / Comprimidos", "Cápsulas / Gomitas", "Jarabe / Suspensión", "Crema / Gel / Ungüento", "Gotas", "Polvo / Sobres", "Equipo Médico / Insumo"], "section": "specs"},
            {"key": "requiere_recipe", "label": "Requiere Récipe Médico", "type": "boolean", "required": False, "section": "condition"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 5. HOGAR, MUEBLES Y JARDÍN
    # --------------------------------------------------------------------------
    "Electrodomésticos": _build_schema(
        archetype="home_appliances",
        ui_hint="Neveras, lavadoras, aires acondicionados, cocinas, licuadoras, cafeteras y airfryers. Especifica marca, voltaje (110V/220V), capacidad y garantía.",
        buyer_ui_hint="Verifica el voltaje, capacidad y garantía del equipo.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad / Color / Voltaje",
            "axes": [
                {"key": "capacity_or_color", "label": "Capacidad / Color", "type": "text", "presets": ["12.000 BTU", "18.000 BTU", "Acero Inoxidable", "Blanco", "Negro"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Samsung, LG, Mabe, Frigilux, Oster, Black+Decker, Condesa", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": False, "placeholder": "Ej: Licuadora Clásica BLST4655 / Split 12000 BTU", "section": "details"},
            {"key": "voltaje", "label": "Voltaje", "type": "select", "required": False, "options": ["110V", "220V", "Bivoltaje (110V/220V)", "Recargable / Batería", "A Gas"], "section": "specs"},
            {"key": "capacidad", "label": "Capacidad / Potencia", "type": "text", "required": False, "placeholder": "Ej: 12.000 BTU / 14 Kg / 4 Litros / 600W", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Open Box", "Usado"], "section": "condition"},
            _warranty_field("Ej: 6 meses, 1 año o 2 años"),
        ],
    ),
    "Muebles": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Sofás, comedores, escritorios, sillas, estantes y armarios. Especifica dimensiones (alto x ancho x profundidad), material y colores.",
        buyer_ui_hint="Selecciona el color o tapizado y verifica las medidas.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Acabado / Tamaño",
            "axes": [
                {"key": "color_finish", "label": "Color / Tapizado", "type": "text", "presets": ["Gris", "Beige", "Negro", "Blanco", "Madera Natural", "Wengué", "Roble"]},
            ],
        },
        fields=[
            {"key": "material_principal", "label": "Material Principal", "type": "text", "required": False, "placeholder": "Ej: Madera Pino, MDF Melamina, Tela Antifluidos, Metal", "section": "specs"},
            {"key": "dimensiones", "label": "Dimensiones (Ancho x Alto x Profundidad)", "type": "text", "required": False, "placeholder": "Ej: 180 x 85 x 90 cm", "section": "specs"},
            {"key": "requiere_armado", "label": "Entrega", "type": "select", "required": False, "options": ["Se entrega armado", "En caja (Requiere armado)", "Fabricación bajo pedido"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Dormitorio": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Colchones, juegos de sábanas, edredones, almohadas y camas. Agrega variantes por tamaño de cama (Individual, Matrimonial, Queen, King).",
        buyer_ui_hint="Selecciona el tamaño de cama (Individual, Matrimonial, Queen o King) y color.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño de Cama y Color",
            "axes": [
                {"key": "bed_size", "label": "Tamaño de Cama", "type": "select", "presets": ["Individual", "Matrimonial", "Queen", "King", "Estándar"]},
                {"key": "color", "label": "Color / Diseño", "type": "text", "presets": ["Blanco", "Gris", "Azul", "Beige", "Estampado"]},
            ],
        },
        fields=[
            {"key": "tamano_cama", "label": "Tamaño", "type": "select", "required": False, "options": ["Individual (1.00m)", "Matrimonial (1.40m)", "Queen (1.60m)", "King (2.00m)", "Estándar"], "section": "specs"},
            {"key": "material", "label": "Material / Hilos", "type": "text", "required": False, "placeholder": "Ej: Algodón Egipcio 400 hilos, Microfibra, Ortopédico", "section": "specs"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Paraíso, Simmons, Cannon, Ama de Casa", "section": "details"},
            _warranty_field("Ej: 1 año o 5 años (colchones)"),
        ],
    ),
    "Baño": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Juegos de toallas, alfombras, cortinas de baño, organizadores y accesorios.",
        buyer_ui_hint="Elige el color o tamaño.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Tamaño",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Blanco", "Gris", "Beige", "Azul", "Verde"]},
            ],
        },
        fields=[
            {"key": "material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: 100% Algodón, Acero Inoxidable, Bambú", "section": "specs"},
            {"key": "dimensiones", "label": "Medidas / Piezas incluidas", "type": "text", "required": False, "placeholder": "Ej: Set 3 piezas (Cuerpo, Mano, Facial)", "section": "specs"},
        ],
    ),
    "Decoración": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Lámparas, espejos, cuadros, alfombras, cojines, cortinas, plantas artificiales y artículos de cocina/mesa.",
        buyer_ui_hint="Elige el diseño, color o medida.",
        allowed_units=["unit", "set", "pair"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Medida / Diseño",
            "axes": [
                {"key": "variant", "label": "Color / Medida", "type": "text", "presets": ["Dorado", "Negro", "Blanco", "Pequeño", "Grande"]},
            ],
        },
        fields=[
            {"key": "material", "label": "Material", "type": "text", "required": False, "placeholder": "Ej: Cerámica, Vidrio, Madera, Metal", "section": "specs"},
            {"key": "dimensiones", "label": "Medidas", "type": "text", "required": False, "placeholder": "Ej: 60 x 40 cm", "section": "specs"},
        ],
    ),
    "Jardín y Exteriores": _build_schema(
        archetype="furniture_and_decor",
        ui_hint="Plantas, materos, parrillera/BBQ, mangueras, grama artificial, tierra abonada y muebles de terraza.",
        buyer_ui_hint="Selecciona el tamaño o cantidad requerida.",
        allowed_units=["unit", "set", "kg", "m", "m2", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Presentación",
            "axes": [
                {"key": "size", "label": "Tamaño", "type": "text", "presets": ["Pequeño", "Mediano", "Grande", "Saco 10 kg", "Rollo 15m"]},
            ],
        },
        fields=[
            {"key": "material", "label": "Material / Tipo", "type": "text", "required": False, "placeholder": "Ej: Resina resistente al sol, Hierro forjado, Planta natural", "section": "specs"},
            {"key": "uso_exterior", "label": "Apto para intemperie (Sol/Lluvia)", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 6. FERRETERÍA Y CONSTRUCCIÓN
    # --------------------------------------------------------------------------
    "Herramientas": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Taladros, esmeriles, plantas eléctricas, juegos de llaves, destornilladores y herramientas manuales o eléctricas.",
        buyer_ui_hint="Revisa la potencia, voltaje y accesorios incluidos.",
        allowed_units=["unit", "set", "box"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida / Modelo / Potencia",
            "axes": [
                {"key": "spec", "label": "Medida / Versión", "type": "text", "presets": ["1/2 pulgada", "3/8 pulgada", "110V", "Inalámbrico 20V"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: DeWalt, Makita, Bosch, Truper, Total, Stanley, Ingco", "section": "details"},
            {"key": "tipo_alimentacion", "label": "Alimentación", "type": "select", "required": False, "options": ["Manual", "Eléctrica con Cable (110V)", "Eléctrica (220V)", "Inalámbrica (Batería)", "Gasolina / Diésel", "Neumática"], "section": "specs"},
            {"key": "potencia", "label": "Potencia / Capacidad", "type": "text", "required": False, "placeholder": "Ej: 800W / 20V Max / 3500W", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Electricidad e Iluminación": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Bombillos LED, reflectores, protectores de voltaje, cables (por metro o rollo), breakers, tomacorrientes y lámparas.",
        buyer_ui_hint="Elige la potencia (W), tono de luz (fría/cálida) o cantidad de metros.",
        allowed_units=["unit", "m", "pack", "box"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Potencia / Color de Luz / Calibre",
            "axes": [
                {"key": "wattage_or_gauge", "label": "Potencia / Calibre", "type": "text", "presets": ["9W", "12W", "15W", "50W", "100W", "THW #12", "THW #10"]},
                {"key": "light_tone", "label": "Tono de Luz / Color", "type": "select", "presets": ["Luz Blanca Fría (6500K)", "Luz Cálida (3000K)", "Luz Neutra (4000K)", "No aplica"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Exceline, Sylvania, Hammer, Bticino, Elecon", "section": "details"},
            {"key": "voltaje", "label": "Voltaje", "type": "select", "required": False, "options": ["110V", "220V", "Multivoltaje (85V-265V)", "12V / 24V"], "section": "specs"},
            {"key": "potencia_calibre", "label": "Potencia (W) / Calibre / Amperaje", "type": "text", "required": False, "placeholder": "Ej: 15W / 20A / Calibre 12 AWG", "section": "specs"},
            _warranty_field("Ej: 1 año o 3 años (protectores Exceline)"),
        ],
    ),
    "Plomería": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Griferías, bombas de agua, tanques, tuberías, conexiones PVC/termofusión, llaves de paso y calentadores.",
        buyer_ui_hint="Verifica la medida en pulgadas (ej. 1/2\", 3/4\") y el material.",
        allowed_units=["unit", "m", "set", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Diámetro / Medida",
            "axes": [
                {"key": "diameter", "label": "Medida / Diámetro", "type": "select", "presets": ["1/2\"", "3/4\"", "1\"", "1 1/2\"", "2\"", "4\"", "20 mm", "25 mm"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Griven, Pedrollo, Tubrica, Pavco, Fundición Pacífico", "section": "details"},
            {"key": "medida_pulgadas", "label": "Medida / Diámetro", "type": "text", "required": False, "placeholder": "Ej: 1/2 pulgada, 1/2 HP, 500 Litros", "section": "specs"},
            {"key": "material", "label": "Material", "type": "select", "required": False, "options": ["Acero Inoxidable", "Bronce / Latón", "PVC Aguas Blancas", "PVC Aguas Negras", "PPR Termofusión", "Hierro Galvanizado", "Polietileno"], "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Materiales de Construcción": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Pinturas, impermeabilizantes, cemento, pego, cerámica/porcelanato, discos, tornillería y manto asfáltico. Puedes vender por galón, cuñete, saco, m² o unidad.",
        buyer_ui_hint="Selecciona la unidad (galón, saco, m², unidad) y el color o medida.",
        allowed_units=["unit", "gal", "kg", "m2", "m", "box", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Presentación",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "text", "presets": ["1/4 Galón", "1 Galón", "Cuñete (4 Gal)", "Cuñete (5 Gal)", "Saco 14 kg", "Saco 20 kg", "Saco 42.5 kg"]},
                {"key": "color", "label": "Color / Acabado", "type": "text", "presets": ["Blanco", "Blanco Mate", "Blanco Satinado", "Gris", "Rojo Teja"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Venezolana de Pinturas (VP), Flamuko, Montana, Sika, Cindu", "section": "details"},
            {"key": "rendimiento_medida", "label": "Rendimiento / Contenido", "type": "text", "required": False, "placeholder": "Ej: 3.78 Litros (1 Galón) / Rinde 35 m²", "section": "specs"},
        ],
    ),
    "Seguridad y Domótica": _build_schema(
        archetype="hardware_and_construction",
        ui_hint="Cámaras de seguridad Wi-Fi/CCTV, cerraduras inteligentes, candados, alarmas, cercos eléctricos y enchufes inteligentes.",
        buyer_ui_hint="Revisa la conectividad y funciones del equipo.",
        allowed_units=["unit", "set", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Versión / Resolución",
            "axes": [
                {"key": "version", "label": "Versión", "type": "text", "presets": ["1080p Full HD", "2K / 3MP", "4K", "Con Memoria 64GB"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Hikvision, Ezviz, Dahua, Imou, Yale, Sonoff", "section": "details"},
            {"key": "conectividad", "label": "Conectividad / App", "type": "text", "required": False, "placeholder": "Ej: Wi-Fi 2.4GHz, Tuya Smart, Alexa / Google Home", "section": "specs"},
            {"key": "uso", "label": "Ubicación de Uso", "type": "select", "required": False, "options": ["Interior", "Exterior (Resistente al agua IP65/IP66)", "Interior y Exterior"], "section": "specs"},
            _warranty_field(),
        ],
    ),

    # --------------------------------------------------------------------------
    # 7. CARROS, MOTOS Y OTROS
    # --------------------------------------------------------------------------
    "Venta de Autos": _build_schema(
        archetype="vehicle_listing",
        ui_hint="Ficha completa para vehículos: indica marca, modelo, año, kilometraje, transmisión, tipo de combustible y estado legal de documentos.",
        buyer_ui_hint="Revisa la ficha técnica del vehículo (año, kilometraje, transmisión y estado).",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Toyota, Chevrolet, Ford, Hyundai, Jeep, Chery, Mitsubishi", "section": "details"},
            {"key": "modelo", "label": "Modelo y Versión", "type": "text", "required": True, "placeholder": "Ej: Corolla SE / 4Runner Limited / Aveo LT", "section": "details"},
            {"key": "ano", "label": "Año", "type": "number", "required": True, "placeholder": "Ej: 2020", "section": "specs"},
            {"key": "kilometraje", "label": "Kilometraje", "type": "number", "required": True, "unit_suffix": "km", "placeholder": "Ej: 65000", "section": "specs"},
            {"key": "transmision", "label": "Transmisión", "type": "select", "required": True, "options": ["Automática", "Sincrónica (Manual)", "Secuencial / CVT", "4x4 Automática", "4x4 Sincrónica"], "section": "specs"},
            {"key": "combustible", "label": "Combustible", "type": "select", "required": False, "options": ["Gasolina", "Diésel / Gasoil", "Híbrido", "Eléctrico", "Dual (Gasolina/Gas)"], "section": "specs"},
            {"key": "color", "label": "Color", "type": "text", "required": False, "placeholder": "Ej: Blanco Perla, Plata, Negro", "section": "details"},
            {"key": "condicion", "label": "Estado / Documentación", "type": "select", "required": False, "options": ["0 km (Nuevo)", "Usado - Único Dueño", "Usado - Papeles al día (Listo para firmar)"], "section": "condition"},
        ],
    ),
    "Venta de Motos": _build_schema(
        archetype="vehicle_listing",
        ui_hint="Ficha técnica de motocicletas: indica marca, modelo, cilindrada (cc), año y kilometraje.",
        buyer_ui_hint="Revisa el año, cilindrada y kilometraje de la moto.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color Disponible",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Rojo", "Azul", "Blanco", "Gris"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Bera, Empire Keeway, Toro, Suzuki, Yamaha, Honda, Haojue", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": True, "placeholder": "Ej: SBR 150 / Horse KW-150 / KLR 650", "section": "details"},
            {"key": "cilindrada_cc", "label": "Cilindrada (cc)", "type": "text", "required": False, "placeholder": "Ej: 150 cc, 200 cc, 250 cc", "section": "specs"},
            {"key": "ano", "label": "Año", "type": "number", "required": True, "placeholder": "Ej: 2024", "section": "specs"},
            {"key": "kilometraje", "label": "Kilometraje", "type": "number", "required": False, "unit_suffix": "km", "placeholder": "Ej: 0", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nueva (0 km)", "Usada - Papeles al día"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Repuestos para Autos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Pastillas de freno, amortiguadores, filtros, bombas, correas, baterías y tren delantero. Indica marca del repuesto, vehículos compatibles y código OEM.",
        buyer_ui_hint="Verifica la compatibilidad con la marca, modelo y año de tu vehículo.",
        allowed_units=["unit", "pair", "set", "box"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Posición / Lado / Medida",
            "axes": [
                {"key": "position", "label": "Posición / Lado", "type": "select", "presets": ["Delantero", "Trasero", "Izquierdo (Piloto)", "Derecho (Copiloto)", "Juego Completo", "Estándar (STD)"]},
            ],
        },
        fields=[
            {"key": "marca_repuesto", "label": "Marca del Repuesto", "type": "text", "required": True, "placeholder": "Ej: Original (OEM), ACDelco, Motorcraft, Gabriel, Bosch, Denso, KYB", "section": "details"},
            {"key": "compatibilidad", "label": "Vehículos y Años Compatibles", "type": "text", "required": True, "placeholder": "Ej: Toyota Corolla 2009-2014 / Aveo todos los años", "section": "specs"},
            {"key": "numero_parte_oem", "label": "Número de Parte / Código OEM", "type": "text", "required": False, "placeholder": "Ej: 04465-02220 / PH3614", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo Original", "Nuevo Reemplazo (Aftermarket)", "Importado (Chivera / Usado)"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Lubricantes y Fluidos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Aceites de motor (15W-40, 20W-50, 10W-30, 5W-30), valvulina, liga de frenos y refrigerantes. Puedes vender por litro/cuarto, galón o caja.",
        buyer_ui_hint="Selecciona la viscosidad o presentación (litro, galón o caja).",
        allowed_units=["unit", "l", "gal", "box"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Viscosidad y Presentación",
            "axes": [
                {"key": "viscosity", "label": "Viscosidad", "type": "select", "presets": ["20W-50", "15W-40", "10W-30", "10W-40", "5W-30", "5W-20", "ATF Dexron III", "DOT 3 / DOT 4"]},
                {"key": "presentation", "label": "Envase", "type": "select", "presets": ["Pinta / Cuarto (946 ml)", "1 Litro", "Galón (3.78L)", "Caja x12 Litros"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Shell, Castrol, Valvoline, Venoco, Inca, Mobil, Motul", "section": "details"},
            {"key": "viscosidad", "label": "Viscosidad / Especificación", "type": "text", "required": False, "placeholder": "Ej: 15W-40 Semi-Sintético / 5W-30 Full Sintético", "section": "specs"},
            {"key": "tipo_aceite", "label": "Base / Tipo", "type": "select", "required": False, "options": ["Mineral", "Semi-Sintético", "100% Sintético (Full Synthetic)", "Hidráulico / Transmisión", "Refrigerante / Coolant", "Liga de Frenos"], "section": "specs"},
        ],
    ),
    "Neumáticos y Rines": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Cauchos, tripas y rines. Especifica la medida exacta del neumático (ej. 195/65 R15 o 265/70 R16) y marca.",
        buyer_ui_hint="Verifica la medida exacta del caucho o rin antes de pedir.",
        allowed_units=["unit", "pair", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Medida Disponible",
            "axes": [
                {"key": "tire_size", "label": "Medida", "type": "text", "presets": ["175/70 R13", "185/65 R14", "195/65 R15", "205/55 R16", "265/70 R16", "265/65 R17"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Pirelli, Goodyear, Bridgestone, Dunlop, Kumho, Linglong", "section": "details"},
            {"key": "medida_caucho_rin", "label": "Medida (Ancho/Perfil/Rin)", "type": "text", "required": True, "placeholder": "Ej: 195/65 R15", "section": "specs"},
            {"key": "tipo_terreno", "label": "Tipo de Terreno", "type": "select", "required": False, "options": ["Pista / Ciudad (H/T)", "Todo Terreno (A/T)", "Pantano (M/T)", "Carga"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado (Media vida)"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Accesorios para Vehículos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Luces LED, reproductores Android/CarPlay, forros de asiento, alfombras, alarmas, papel ahumado y productos de autolavado/detailing.",
        buyer_ui_hint="Selecciona el conector o versión compatible.",
        allowed_units=["unit", "pair", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Modelo / Conector / Color",
            "axes": [
                {"key": "socket_or_model", "label": "Conector / Versión", "type": "text", "presets": ["H4", "H7", "H11", "9005", "9006", "Universal"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pioneer, Meguiar's, 3M, Sparco, Genérico", "section": "details"},
            {"key": "compatibilidad", "label": "Compatibilidad", "type": "text", "required": False, "placeholder": "Ej: Universal / Específico por modelo", "section": "specs"},
            _warranty_field(),
        ],
    ),
    "Motos": _build_schema(
        archetype="auto_parts_and_fluids",
        ui_hint="Repuestos de motos, cascos, guantes, cauchos de moto, baterías, kits de arrastre e impermeables.",
        buyer_ui_hint="Selecciona la talla (si es casco/indumentaria) o el modelo de moto compatible.",
        allowed_units=["unit", "pair", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla / Modelo Compatible / Color",
            "axes": [
                {"key": "variant", "label": "Talla / Modelo", "type": "text", "presets": ["S", "M", "L", "XL", "SBR / Horse / Owen", "TX 200 / KLR"]},
            ],
        },
        fields=[
            {"key": "tipo_articulo", "label": "Tipo de Producto", "type": "select", "required": False, "options": ["Repuesto de Moto", "Casco / Seguridad", "Caucho / Tripa de Moto", "Accesorios / Luces", "Impermeable / Indumentaria"], "section": "details"},
            {"key": "compatibilidad", "label": "Motos Compatibles / Talla", "type": "text", "required": False, "placeholder": "Ej: Bera SBR, Empire Horse 150, Universal", "section": "specs"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 8. DEPORTES Y FITNESS
    # --------------------------------------------------------------------------
    "Fitness y Musculación": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Mancuernas, discos, bandas elásticas, mats de yoga, máquinas de gimnasio y suplementos deportivos (proteínas, creatina).",
        buyer_ui_hint="Selecciona el peso, resistencia o sabor.",
        allowed_units=["unit", "pair", "set", "kg", "lb"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Peso / Resistencia / Sabor",
            "axes": [
                {"key": "weight_or_flavor", "label": "Peso / Sabor / Nivel", "type": "text", "presets": ["2 kg", "5 kg", "10 kg", "15 lb", "25 lb", "Vainilla", "Chocolate", "Sin Sabor"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Optimum Nutrition, Sascha Fitness, Everlast, Nike", "section": "details"},
            {"key": "peso_contenido", "label": "Peso / Contenido", "type": "text", "required": False, "placeholder": "Ej: Par de 10 lb / Tarro 2 lb (900g)", "section": "specs"},
        ],
    ),
    "Ropa y Calzado Deportivo": _build_schema(
        archetype="apparel_fashion",
        ui_hint="Conjuntos deportivos, leggings, franelas dry-fit, zapatos para correr y tacos. Configura las tallas y colores disponibles.",
        buyer_ui_hint="Selecciona tu talla y color.",
        allowed_units=["unit", "pair", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tallas y Colores",
            "axes": [
                {"key": "size", "label": "Talla", "type": "select", "presets": ["XS", "S", "M", "L", "XL", "XXL", "36", "37", "38", "39", "40", "41", "42", "43", "44"]},
                {"key": "color", "label": "Color", "type": "text", "presets": ["Negro", "Blanco", "Azul", "Gris", "Verde", "Rosa"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Nike, Adidas, Under Armour, Puma, Gymshark", "section": "details"},
            {"key": "disciplina", "label": "Deporte / Uso", "type": "select", "required": False, "options": ["Gym / Training", "Running", "Fútbol", "Pádel / Tenis", "Béisbol", "Natación", "Ciclismo"], "section": "details"},
            {"key": "genero", "label": "Género", "type": "select", "required": False, "options": ["Dama", "Caballero", "Unisex", "Infantil"], "section": "details"},
        ],
    ),
    "Deportes Específicos": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Palas de pádel, raquetas, balones de fútbol/basket/voleibol, guantes de béisbol, bates y bicicletas.",
        buyer_ui_hint="Revisa la talla o especificaciones técnicas del implemento.",
        allowed_units=["unit", "pair", "set", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla / Medida / Modelo",
            "axes": [
                {"key": "size", "label": "Talla / Medida", "type": "text", "presets": ["Talla 5", "Talla 4", "Rin 29", "Rin 26", "Adulto", "Juvenil"]},
            ],
        },
        fields=[
            {"key": "deporte", "label": "Deporte", "type": "select", "required": False, "options": ["Pádel / Tenis / Beach Tennis", "Fútbol", "Béisbol / Sóftbol", "Baloncesto", "Ciclismo", "Voleibol", "Natación", "Boxeo / Artes Marciales"], "section": "details"},
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Babolat, Bullpadel, Wilson, Spalding, Rawlings, Shimano", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
        ],
    ),
    "Camping y Outdoors": _build_schema(
        archetype="sports_and_fitness",
        ui_hint="Cavitas/coolers, termos, carpas, sillas plegables, linternas y artículos de playa o montaña.",
        buyer_ui_hint="Selecciona la capacidad (litros/oz) o color.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Capacidad / Color",
            "axes": [
                {"key": "capacity_color", "label": "Capacidad / Color", "type": "text", "presets": ["20 oz", "30 oz", "40 oz", "24 Latas", "48 Quart", "Negro", "Azul", "Verde"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Coleman, Igloo, Stanley, Yeti, Victorinox", "section": "details"},
            {"key": "capacidad", "label": "Capacidad / Personas", "type": "text", "required": False, "placeholder": "Ej: 40 oz / 50 Litros / 4 Personas", "section": "specs"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 9. BEBÉS Y MATERNIDAD
    # --------------------------------------------------------------------------
    "Pañales y Toallitas": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Pañales desechables, ecológicos y toallitas húmedas. Agrega las tallas de pañal (RN, P, M, G, XG, XXG) y cantidad por paquete.",
        buyer_ui_hint="Selecciona la talla del bebé (RN, P, M, G, XG, XXG) y el empaque.",
        allowed_units=["pack", "box", "unit"],
        default_unit="pack",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Talla de Pañal y Cantidad",
            "axes": [
                {"key": "diaper_size", "label": "Talla", "type": "select", "presets": ["RN (Recién Nacido)", "Talla P (Etapa 1)", "Talla M (Etapa 2-3)", "Talla G (Etapa 4)", "Talla XG (Etapa 5)", "Talla XXG (Etapa 6)"]},
                {"key": "count", "label": "Unidades por Paquete", "type": "text", "presets": ["Paquete x20", "Paquete x40", "Paquete x80", "Bulto"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Huggies, Pampers, Pequeñín, Babysec", "section": "details"},
            {"key": "unidades_por_empaque", "label": "Unidades por Empaque", "type": "number", "required": False, "placeholder": "Ej: 40", "section": "specs"},
        ],
    ),
    "Lactancia y Alimentación": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Fórmulas infantiles, teteros, chupones, extractores de leche, compotas y cereales infantiles.",
        buyer_ui_hint="Verifica la etapa/edad recomendada y contenido.",
        allowed_units=["unit", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Etapa / Capacidad (oz)",
            "axes": [
                {"key": "stage_or_size", "label": "Etapa / Tamaño", "type": "text", "presets": ["Etapa 1 (0-6m)", "Etapa 2 (6-12m)", "Etapa 3 (+1 año)", "4 oz", "8 oz", "9 oz"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Philips Avent, Dr. Brown's, Enfamil, NAN, Nestum, Gerber", "section": "details"},
            {"key": "edad_etapa", "label": "Etapa / Edad Recomendada", "type": "text", "required": False, "placeholder": "Ej: 0 a 6 meses / +1 año", "section": "specs"},
            {"key": "contenido_neto", "label": "Contenido / Capacidad", "type": "text", "required": False, "placeholder": "Ej: 400 g, 800 g, 9 oz", "section": "specs"},
        ],
    ),
    "Paseo y Viaje": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Coches, sillas de carro (car seats), pañaleras y portabebés.",
        buyer_ui_hint="Elige el color y revisa el peso máximo soportado.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Modelo",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Gris", "Negro", "Azul", "Rosa", "Beige"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Graco, Chicco, Evenflo, Infanti", "section": "details"},
            {"key": "peso_maximo_kg", "label": "Peso Máximo Soportado", "type": "text", "required": False, "placeholder": "Ej: Hasta 20 kg", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado - Excelente estado"], "section": "condition"},
        ],
    ),
    "Higiene y Cuidado del Bebé": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Colonia de bebé, crema antipañalitis, shampoo sin lágrimas, bañeras y kits de cuidado.",
        buyer_ui_hint="Selecciona el tamaño o aroma.",
        allowed_units=["unit", "set", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Presentación",
            "axes": [
                {"key": "size", "label": "Contenido", "type": "text", "presets": ["100 ml", "200 ml", "400 ml", "800 ml"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Johnson's, Arrurú, Mustela, Desitin, Chicco", "section": "details"},
            {"key": "contenido_neto", "label": "Contenido Neto", "type": "text", "required": False, "placeholder": "Ej: 400 ml", "section": "specs"},
        ],
    ),
    "Cuarto del Bebé": _build_schema(
        archetype="baby_and_maternity",
        ui_hint="Cunas, corrales, mecedoras, monitores de bebé y lencería de cuna.",
        buyer_ui_hint="Selecciona el color o diseño.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Diseño",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Blanco", "Madera", "Gris", "Rosa", "Azul"]},
            ],
        },
        fields=[
            {"key": "dimensiones", "label": "Dimensiones", "type": "text", "required": False, "placeholder": "Ej: 130 x 70 cm", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 10. JUEGOS Y JUGUETES
    # --------------------------------------------------------------------------
    "Juguetes para Bebés": _build_schema(
        archetype="toys_and_games",
        ui_hint="Gimnasios, sonajeros, mordedores, juguetes sensoriales y didácticos.",
        buyer_ui_hint="Revisa la edad recomendada.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Fisher-Price, VTech, Melissa & Doug", "section": "details"},
            {"key": "edad_recomendada", "label": "Edad Recomendada", "type": "select", "required": False, "options": ["0 a 6 meses", "6 a 12 meses", "1 a 3 años", "+3 años"], "section": "specs"},
        ],
    ),
    "Muñecas y Peluches": _build_schema(
        archetype="toys_and_games",
        ui_hint="Muñecas, peluches, coches de juguete y casas de muñecas. Indica tamaño en cm o modelo.",
        buyer_ui_hint="Selecciona el modelo, personaje o tamaño.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Personaje / Tamaño / Color",
            "axes": [
                {"key": "character_or_size", "label": "Personaje / Tamaño", "type": "text", "presets": ["30 cm", "50 cm", "Gigante 1m", "Rosa", "Marrón"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca / Franquicia", "type": "text", "required": False, "placeholder": "Ej: Barbie, Disney, LOL Surprise, Sanrio", "section": "details"},
            {"key": "tamano_cm", "label": "Tamaño / Altura", "type": "text", "required": False, "placeholder": "Ej: 30 cm", "section": "specs"},
        ],
    ),
    "Figuras de Acción": _build_schema(
        archetype="toys_and_games",
        ui_hint="Figuras coleccionables, Funko Pop, carros a escala (Hot Wheels) y superhéroes.",
        buyer_ui_hint="Elige el personaje o modelo.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Personaje / Modelo",
            "axes": [
                {"key": "character", "label": "Personaje / Edición", "type": "text", "presets": ["Edición Estándar", "Edición Especial"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Funko, Marvel, Hasbro, Mattel, Bandai, Hot Wheels", "section": "details"},
            {"key": "franquicia", "label": "Franquicia / Serie", "type": "text", "required": False, "placeholder": "Ej: Spider-Man, Star Wars, Anime, Pokémon", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo en caja sellada", "Colección (Abierto)"], "section": "condition"},
        ],
    ),
    "Juegos de Mesa y Rompecabezas": _build_schema(
        archetype="toys_and_games",
        ui_hint="Juegos familiares, cartas (UNO, Pokémon), ajedrez, dominó y rompecabezas.",
        buyer_ui_hint="Revisa el número de jugadores y edad recomendada.",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Hasbro, Mattel, Ronda, Ravensburger", "section": "details"},
            {"key": "jugadores", "label": "Cantidad de Jugadores / Piezas", "type": "text", "required": False, "placeholder": "Ej: 2 a 6 jugadores / 1000 piezas", "section": "specs"},
            {"key": "edad_recomendada", "label": "Edad Recomendada", "type": "text", "required": False, "placeholder": "Ej: +8 años", "section": "specs"},
        ],
    ),
    "Bloques y Construcción": _build_schema(
        archetype="toys_and_games",
        ui_hint="Sets de LEGO, bloques armables y pistas. Indica el número de piezas y edad recomendada.",
        buyer_ui_hint="Verifica la cantidad de piezas y modelo del set.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: LEGO, Mega Bloks, Sluban", "section": "details"},
            {"key": "cantidad_piezas", "label": "Cantidad de Piezas", "type": "number", "required": False, "placeholder": "Ej: 450", "section": "specs"},
            {"key": "edad_recomendada", "label": "Edad Recomendada", "type": "text", "required": False, "placeholder": "Ej: +6 años", "section": "specs"},
        ],
    ),
    "Juguetes de Exterior": _build_schema(
        archetype="toys_and_games",
        ui_hint="Monopatines, patines, bicicletas infantiles, carros eléctricos montables, piscinas inflables y lanzadores.",
        buyer_ui_hint="Elige el color o talla.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Talla",
            "axes": [
                {"key": "color", "label": "Color", "type": "text", "presets": ["Azul", "Rosa", "Rojo", "Verde", "Negro"]},
            ],
        },
        fields=[
            {"key": "edad_recomendada", "label": "Edad / Peso Recomendado", "type": "text", "required": False, "placeholder": "Ej: 3 a 8 años (Hasta 35 kg)", "section": "specs"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 11. MASCOTAS
    # --------------------------------------------------------------------------
    "Perros": _build_schema(
        archetype="pets",
        ui_hint="Perrarina/alimento concentrado (por kg o saco), snacks, collares, pecheras, camas y juguetes para perros.",
        buyer_ui_hint="Elige el peso en kg, saco o la talla del accesorio (S, M, L).",
        allowed_units=["kg", "g", "unit", "pack", "box"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación de Peso / Talla",
            "axes": [
                {"key": "presentation", "label": "Peso / Talla", "type": "select", "presets": ["1 kg (Detal)", "2 kg", "4 kg", "10 kg", "Saco 18-20 kg", "Talla S", "Talla M", "Talla L", "Talla XL"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Dog Chow, Dogourmet, Protinal, Kantal, Pedigree", "section": "details"},
            {"key": "etapa_mascota", "label": "Etapa / Tamaño de Raza", "type": "select", "required": False, "options": ["Cachorro (Puppy)", "Adulto Raza Pequeña", "Adulto Raza Mediana/Grande", "Todas las etapas"], "section": "specs"},
            {"key": "peso_contenido", "label": "Peso / Contenido", "type": "text", "required": False, "placeholder": "Ej: 1 kg, 4 kg, 20 kg", "section": "specs"},
        ],
    ),
    "Gatos": _build_schema(
        archetype="pets",
        ui_hint="Gatarina/alimento (por kg o empaque), arena sanitaria, rascadores, juguetes y accesorios para gatos.",
        buyer_ui_hint="Selecciona el peso o presentación deseada.",
        allowed_units=["kg", "g", "unit", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación de Peso / Sabor",
            "axes": [
                {"key": "presentation", "label": "Presentación", "type": "select", "presets": ["500 g", "1 kg", "3 kg", "8 kg", "Arena 4 kg", "Arena 10 kg", "Pescado / Salmón", "Pollo / Carne"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Cat Chow, Gatsy, Félix, Mirringo, Tidy Cats", "section": "details"},
            {"key": "peso_contenido", "label": "Peso / Contenido", "type": "text", "required": False, "placeholder": "Ej: 1 kg, 4 kg", "section": "specs"},
        ],
    ),
    "Higiene y Salud Animal": _build_schema(
        archetype="pets",
        ui_hint="Antipulgas/garrapatas (pipetas, pastillas masticables), desparasitantes, vitaminas, shampoo y peluquería.",
        buyer_ui_hint="Selecciona el rango de peso de tu mascota (ej. 2-4.5 kg, 10-20 kg).",
        allowed_units=["unit", "pack"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Rango de Peso de la Mascota",
            "axes": [
                {"key": "pet_weight_range", "label": "Peso de la Mascota", "type": "select", "presets": ["2 a 4.5 kg", "4.5 a 10 kg", "10 a 20 kg", "20 a 40 kg", "40 a 56 kg", "Uso General"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca / Laboratorio", "type": "text", "required": False, "placeholder": "Ej: Bravecto, NexGard, Simparica, Frontline, Drontal", "section": "details"},
            {"key": "especie", "label": "Especie", "type": "select", "required": False, "options": ["Perros", "Gatos", "Perros y Gatos", "Aves / Otros"], "section": "specs"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 12. PAPELERÍA, OFICINA Y LIBROS
    # --------------------------------------------------------------------------
    "Útiles Escolares": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Cuadernos, lápices, colores, marcadores, morrales escolares, plastilina, pega y cartulinas.",
        buyer_ui_hint="Selecciona el color, tipo de línea o presentación (unidad/caja).",
        allowed_units=["unit", "pack", "box", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Presentación / Tipo / Color",
            "axes": [
                {"key": "variant", "label": "Tipo / Cantidad", "type": "text", "presets": ["Una Línea", "Doble Línea", "Cuadriculado", "Caja x12", "Caja x24", "Unidad"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Norma, Prismacolor, Faber-Castell, Kores, Solita, Caribe", "section": "details"},
            {"key": "unidades_por_empaque", "label": "Unidades / Hojas", "type": "text", "required": False, "placeholder": "Ej: 100 hojas / Caja de 12 colores", "section": "specs"},
        ],
    ),
    "Oficina": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Resmas de papel, impresoras, tóners/tintas, carpetas, calculadoras, pizarras y sillas de oficina.",
        buyer_ui_hint="Elige el tamaño (Carta / Oficio) o modelo.",
        allowed_units=["unit", "pack", "box"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Presentación",
            "axes": [
                {"key": "size", "label": "Tamaño / Tipo", "type": "text", "presets": ["Tamaño Carta", "Tamaño Oficio", "Resma (500 hojas)", "Bulto (10 resmas)"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Alpes, HP, Epson, Casio, Ofimak", "section": "details"},
        ],
    ),
    "Libros": _build_schema(
        archetype="books_and_stationery",
        ui_hint="Libros de lectura, textos escolares, novelas, desarrollo personal y cómics. Indica autor, editorial y formato.",
        buyer_ui_hint="Revisa el autor, idioma y estado del ejemplar.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Edición / Tapa",
            "axes": [
                {"key": "cover", "label": "Encuadernación", "type": "select", "presets": ["Tapa Blanda (Rústica)", "Tapa Dura"]},
            ],
        },
        fields=[
            {"key": "autor", "label": "Autor", "type": "text", "required": True, "placeholder": "Ej: Gabriel García Márquez / James Clear", "section": "details"},
            {"key": "editorial", "label": "Editorial", "type": "text", "required": False, "placeholder": "Ej: Planeta, Penguin Random House, Santillana", "section": "details"},
            {"key": "idioma", "label": "Idioma", "type": "select", "required": False, "options": ["Español", "Inglés", "Bilingüe / Otro"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado - Excelente estado", "Usado"], "section": "condition"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 13. INSTRUMENTOS MUSICALES
    # --------------------------------------------------------------------------
    "Guitarras y Bajos": _build_schema(
        archetype="musical_instruments",
        ui_hint="Guitarras acústicas, clásicas, eléctricas, electroacústicas y bajos. Indica marca, modelo y número de cuerdas.",
        buyer_ui_hint="Elige el color o acabado disponible.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Color / Acabado",
            "axes": [
                {"key": "color", "label": "Color / Acabado", "type": "text", "presets": ["Natural", "Sunburst", "Negro", "Blanco", "Rojo"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Fender, Squier, Yamaha, Ibanez, Epiphone, Cort", "section": "details"},
            {"key": "tipo_instrumento", "label": "Tipo", "type": "select", "required": False, "options": ["Guitarra Clásica (Nylon)", "Guitarra Acústica / Electroacústica", "Guitarra Eléctrica", "Bajo Eléctrico (4 cuerdas)", "Bajo Eléctrico (5 cuerdas)"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Teclados y Pianos": _build_schema(
        archetype="musical_instruments",
        ui_hint="Teclados musicales, pianos digitales, sintetizadores y controladores MIDI. Indica la cantidad de teclas (61, 76, 88).",
        buyer_ui_hint="Verifica la cantidad de teclas y accesorios incluidos.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Yamaha, Casio, Roland, Korg, Arturia, M-Audio", "section": "details"},
            {"key": "cantidad_teclas", "label": "Cantidad de Teclas", "type": "select", "required": False, "options": ["25 teclas", "49 teclas", "61 teclas (5 octavas)", "76 teclas", "88 teclas ( Acción Martillo)"], "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": True, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Baterías y Percusión": _build_schema(
        archetype="musical_instruments",
        ui_hint="Baterías acústicas/electrónicas, platillos, timbales, congas, bongós, maracas y charrascas.",
        buyer_ui_hint="Revisa las piezas incluidas y medidas.",
        allowed_units=["unit", "set", "pair"],
        default_unit="unit",
        supports_variants=True,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Pearl, Tama, Mapex, LP, Zildjian, Sabian, Roland", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
        ],
    ),
    "Instrumentos de Viento": _build_schema(
        archetype="musical_instruments",
        ui_hint="Flautas, saxofones, trompetas, clarinetes, armónicas y trombones.",
        buyer_ui_hint="Verifica la afinación y accesorios incluidos (estuche, boquilla).",
        allowed_units=["unit"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: Yamaha, Hohner, Selmer, Jupiter", "section": "details"},
            {"key": "afinacion", "label": "Afinación / Tipo", "type": "text", "required": False, "placeholder": "Ej: Mi Bemol (Eb) / Si Bemol (Bb)", "section": "specs"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
        ],
    ),
    "Instrumentos de Cuerda": _build_schema(
        archetype="musical_instruments",
        ui_hint="Cuatros venezolanos, violines, ukeleles, mandolinas, arpas y violonchelos.",
        buyer_ui_hint="Verifica el tamaño (ej. 4/4, Concierto, Profesional) y si incluye forro/estuche.",
        allowed_units=["unit", "set"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Tamaño / Modelo",
            "axes": [
                {"key": "size", "label": "Tamaño / Tipo", "type": "text", "presets": ["Estándar (14 trastes)", "Concierto (17 trastes)", "Violín 4/4", "Violín 3/4", "Violín 1/2", "Soprano"]},
            ],
        },
        fields=[
            {"key": "instrumento", "label": "Instrumento", "type": "select", "required": False, "options": ["Cuatro Venezolano", "Violín", "Ukelele", "Mandolina", "Arpa", "Violonchelo"], "section": "details"},
            {"key": "luthier_marca", "label": "Marca / Luthier", "type": "text", "required": False, "placeholder": "Ej: Luthier Nacional, Cremona, Kala, Yamaha", "section": "details"},
            {"key": "incluye_forro", "label": "Incluye Forro / Estuche", "type": "boolean", "required": False, "section": "specs"},
        ],
    ),
    "Audio Profesional y DJ": _build_schema(
        archetype="musical_instruments",
        ui_hint="Interfaces de audio, micrófonos de estudio/en vivo, consolas mezcladoras, monitores, cornetas activas y controladores DJ.",
        buyer_ui_hint="Revisa la potencia y conectores del equipo.",
        allowed_units=["unit", "pair", "set"],
        default_unit="unit",
        supports_variants=False,
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": True, "placeholder": "Ej: Shure, Focusrite, Behringer, Pioneer DJ, JBL, Electro-Voice", "section": "details"},
            {"key": "modelo", "label": "Modelo", "type": "text", "required": False, "placeholder": "Ej: Shure SM58 / Scarlett 2i2 / DDJ-FLX4", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado"], "section": "condition"},
            _warranty_field(),
        ],
    ),
    "Accesorios Musicales": _build_schema(
        archetype="musical_instruments",
        ui_hint="Encordados (cuerdas de guitarra/cuatro/violín), cables plug/XLR, atriles, capotrastes, púas, baquetas y forros.",
        buyer_ui_hint="Selecciona el calibre o medida.",
        allowed_units=["unit", "set", "pack", "pair"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Calibre / Medida",
            "axes": [
                {"key": "gauge", "label": "Calibre / Medida", "type": "text", "presets": [".009", ".010", "Tensión Normal", "Tensión Alta", "5A", "5B", "3 metros", "6 metros"]},
            ],
        },
        fields=[
            {"key": "marca", "label": "Marca", "type": "text", "required": False, "placeholder": "Ej: D'Addario, Ernie Ball, Elixir, Vic Firth, Proel", "section": "details"},
        ],
    ),

    # --------------------------------------------------------------------------
    # 14. OTRAS CATEGORÍAS (VARIOS)
    # --------------------------------------------------------------------------
    "Otros": _build_schema(
        archetype="general",
        ui_hint="Configura libremente la unidad de venta, presentaciones, variantes o grupos de opciones adicionales según tu producto o servicio.",
        buyer_ui_hint="Selecciona las opciones disponibles.",
        allowed_units=["unit", "pack", "box", "set", "kg", "g", "l", "ml", "portion", "combo"],
        default_unit="unit",
        supports_variants=True,
        variant_config={
            "enabled": True,
            "label": "Variantes / Opciones",
            "axes": [
                {"key": "option", "label": "Opción / Presentación", "type": "text", "presets": ["Estándar", "Especial", "Combo"]},
            ],
        },
        supports_modifier_groups=True,
        order_notes_enabled=True,
        fields=[
            {"key": "marca", "label": "Marca / Proveedor", "type": "text", "required": False, "placeholder": "Opcional", "section": "details"},
            {"key": "condicion", "label": "Condición", "type": "select", "required": False, "options": ["Nuevo", "Usado", "Servicio / Bajo Pedido"], "section": "condition"},
            _warranty_field(),
        ],
    ),
}

# Registrar esquemas especializados para las nuevas subcategorías de Alimentos y Bebidas y Tecnología y Electrónica
_NEW_SUBCATEGORY_BASE_MAPPING: Dict[str, str] = {
    # Alimentos y Bebidas (15 subcategorías)
    "Víveres y Granos": "Despensa y Víveres",
    "Frutas, Verduras y Hortalizas": "Frescos",
    "Carnicería y Aves": "Frescos",
    "Pescadería y Mariscos": "Frescos",
    "Charcutería": "Charcutería y Lácteos",
    "Lácteos y Huevos": "Charcutería y Lácteos",
    "Panadería y Pastelería": "Snacks y Dulces",
    "Enlatados y Conservas": "Despensa y Víveres",
    "Salsas, Condimentos y Aceites": "Despensa y Víveres",
    "Café, Té e Infusiones": "Despensa y Víveres",
    "Bebidas, Refrescos y Maltas": "Bebidas",
    "Chucherías, Snacks y Dulces": "Snacks y Dulces",
    "Congelados y Pasapalos": "Snacks y Dulces",
    "Avena y Cereales": "Despensa y Víveres",
    # Tecnología y Electrónica (17 subcategorías)
    "Teléfonos y Tablets": "Celulares y Tablets",
    "Computadoras y Laptops": "Computación",
    "Componentes de PC y Hardware": "Computación",
    "Almacenamiento y Memorias": "Computación",
    "Monitores y Televisores": "TV, Audio y Video",
    "Impresoras y Escaners": "Computación",
    "Smartwatches y Wearables": "Wearables",
    "Audífonos y Cornetas": "Periféricos y Accesorios",
    "Teclados y Mouse": "Periféricos y Accesorios",
    "Redes, Routers y Conectividad": "Computación",
    "Consolas y Videojuegos": "Videojuegos y Consolas",
    "Cargadores, Cables y Powerbanks": "Periféricos y Accesorios",
    "Reguladores, Protectores y UPS": "Periféricos y Accesorios",
    "Smart Home y Domótica": "Seguridad y Domótica",
    "Seguridad y Cámaras de Vigilancia": "Seguridad y Domótica",
    "Proyectores y Video Beam": "TV, Audio y Video",
}
for _new_sub_name, _base_sub_name in _NEW_SUBCATEGORY_BASE_MAPPING.items():
    if _new_sub_name not in SUBCATEGORY_SCHEMAS and _base_sub_name in SUBCATEGORY_SCHEMAS:
        SUBCATEGORY_SCHEMAS[_new_sub_name] = SUBCATEGORY_SCHEMAS[_base_sub_name]


# Esquemas por defecto a nivel de Categoría Principal (cuando no se especifica subcategoría)
CATEGORY_DEFAULT_SUBCATEGORY_MAP: Dict[str, str] = {
    "Alimentos y Bebidas": "Víveres y Granos",
    "Alimentos y Bebidas (Supermercado)": "Víveres y Granos",
    "Tecnología y Electrónica": "Teléfonos y Tablets",
    "Moda y Accesorios": "Ropa Femenina",
    "Salud y Belleza": "Cuidado Personal",
    "Hogar, Muebles y Jardín": "Electrodomésticos",
    "Ferretería y Construcción": "Herramientas",
    "Carros, Motos y Otros": "Repuestos para Autos",
    "Deportes y Fitness": "Fitness y Musculación",
    "Bebés y Maternidad": "Pañales y Toallitas",
    "Juegos y Juguetes": "Juguetes para Bebés",
    "Mascotas": "Perros",
    "Papelería, Oficina y Libros": "Útiles Escolares",
    "Instrumentos Musicales": "Guitarras y Bajos",
    "Otras Categorías": "Otros",
    "Otras Categorías (Varios)": "Otros",
}


def get_subcategory_schema(
    subcategory_name: Optional[str] = None,
    parent_category_name: Optional[str] = None,
    custom_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Devuelve el esquema dinámico completo para una subcategoría o categoría.
    Si el registro SubCategory tiene `schema_config` en BD, hace merge con el esquema base.
    """
    base_schema: Optional[Dict[str, Any]] = None

    if subcategory_name:
        clean_sub = subcategory_name.strip()
        base_schema = SUBCATEGORY_SCHEMAS.get(clean_sub)
        if not base_schema:
            for key, val in SUBCATEGORY_SCHEMAS.items():
                if key.lower() == clean_sub.lower():
                    base_schema = val
                    break

    if not base_schema and parent_category_name:
        clean_cat = parent_category_name.strip()
        mapped_cat = LEGACY_CATEGORY_TO_OFFICIAL_MAP.get(clean_cat, clean_cat)
        default_sub = CATEGORY_DEFAULT_SUBCATEGORY_MAP.get(mapped_cat)
        if default_sub:
            base_schema = SUBCATEGORY_SCHEMAS.get(default_sub)

    if not base_schema:
        base_schema = SUBCATEGORY_SCHEMAS["Otros"]

    result = json.loads(json.dumps(base_schema))
    if custom_override and isinstance(custom_override, dict):
        # Solo sobreescribir el esquema oficial en código si el admin marcó explícitamente `is_custom_override: True`
        if custom_override.get("is_custom_override"):
            result.update(custom_override)

    result["subcategory_name"] = subcategory_name or ""
    result["parent_category_name"] = parent_category_name or ""

    return result


# ==============================================================================
# 5. VALIDACIÓN Y NORMALIZACIÓN DE DATOS DINÁMICOS DE PRODUCTO
# ==============================================================================

def _parse_json_or_value(raw_val: Any, default: Any) -> Any:
    if raw_val is None or raw_val == "":
        return default
    if isinstance(raw_val, (dict, list)):
        return raw_val
    if isinstance(raw_val, str):
        raw_str = raw_val.strip()
        if not raw_str:
            return default
        try:
            return json.loads(raw_str)
        except Exception:
            return default
    return default


def _to_float(val: Any, default: float) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_bool(val: Any, default: bool) -> bool:
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1", "yes", "si", "sí"):
            return True
        if v in ("false", "0", "no"):
            return False
    return default


def normalize_variants(raw_variants: Any, base_price: float = 0.0) -> List[Dict[str, Any]]:
    """
    Normaliza la lista de variantes de un producto:
    Cada variante tiene:
      - id: str
      - name / label: str (ej. 'Talla M - Negro' o '500g' o '42')
      - options / attributes: dict (ej. {'size': 'M', 'color': 'Negro'})
      - price: float | None (precio absoluto opcional; si es None se usa base_price + price_delta)
      - price_delta: float (diferencia sobre el precio base, default 0.0)
      - effective_price: float (precio calculado final de la variante)
      - stock: int | None (inventario opcional de la variante)
      - sku: str (opcional)
      - is_available: bool (default True)
    """
    parsed = _parse_json_or_value(raw_variants, [])
    if not isinstance(parsed, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue

        var_id = str(item.get("id") or item.get("uid") or f"var_{idx + 1}_{uuid.uuid4().hex[:6]}")
        options = item.get("options") if isinstance(item.get("options"), dict) else (
            item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        )
        # Soportar claves directas comunes como size, color, presentation, weight
        for direct_key in ("size", "talla", "color", "presentation", "presentacion", "weight", "peso", "storage", "almacenamiento"):
            if direct_key in item and item[direct_key] not in (None, "") and direct_key not in options:
                options[direct_key] = str(item[direct_key])

        name = str(item.get("name") or item.get("label") or item.get("title") or "").strip()
        if not name and options:
            name = " / ".join(str(v) for v in options.values() if v not in (None, ""))
        if not name:
            name = f"Opción {idx + 1}"

        raw_abs_price = item.get("price")
        price_delta = _to_float(item.get("price_delta", item.get("extra_price", 0.0)), 0.0)

        abs_price: Optional[float] = None
        if raw_abs_price not in (None, ""):
            try:
                abs_price = round(max(0.0, float(raw_abs_price)), 2)
            except (ValueError, TypeError):
                abs_price = None

        if abs_price is not None:
            effective_price = abs_price
            if base_price > 0 and price_delta == 0.0:
                price_delta = round(abs_price - base_price, 2)
        else:
            effective_price = round(max(0.0, base_price + price_delta), 2)

        raw_stock = item.get("stock", item.get("quantity"))
        stock_val: Optional[int] = None
        if raw_stock not in (None, ""):
            try:
                stock_val = max(0, int(float(raw_stock)))
            except (ValueError, TypeError):
                stock_val = None

        is_available = _to_bool(item.get("is_available", True), True)
        if stock_val is not None and stock_val <= 0 and "is_available" not in item:
            is_available = False

        normalized.append({
            "id": var_id,
            "name": name,
            "label": name,
            "options": options,
            "price": abs_price,
            "price_delta": round(price_delta, 2),
            "effective_price": effective_price,
            "stock": stock_val,
            "sku": str(item.get("sku") or "").strip(),
            "is_available": is_available,
        })

    return normalized


def normalize_modifier_groups(raw_groups: Any) -> List[Dict[str, Any]]:
    """
    Normaliza grupos de modificadores/extras (estilo PedidosYa):
    Cada grupo tiene:
      - id: str
      - name: str (ej. 'Elige tu contorno', 'Extras', 'Tipo de corte')
      - required: bool
      - min_selections: int
      - max_selections: int
      - options: [{id, name, price_delta, is_available}]
    """
    parsed = _parse_json_or_value(raw_groups, [])
    if not isinstance(parsed, list):
        return []

    normalized_groups: List[Dict[str, Any]] = []
    for g_idx, group in enumerate(parsed):
        if not isinstance(group, dict):
            continue

        group_name = str(group.get("name") or group.get("title") or group.get("label") or "").strip()
        if not group_name:
            continue

        group_id = str(group.get("id") or f"mod_grp_{g_idx + 1}_{uuid.uuid4().hex[:6]}")
        required = _to_bool(group.get("required", False), False)
        min_sel = max(0, int(_to_float(group.get("min_selections", 1 if required else 0), 1 if required else 0)))
        max_sel = max(1, int(_to_float(group.get("max_selections", 1), 1)))
        if max_sel < min_sel and min_sel > 0:
            max_sel = min_sel

        raw_options = group.get("options") if isinstance(group.get("options"), list) else (
            group.get("items") if isinstance(group.get("items"), list) else []
        )
        normalized_options: List[Dict[str, Any]] = []
        for o_idx, opt in enumerate(raw_options):
            if not isinstance(opt, dict):
                continue
            opt_name = str(opt.get("name") or opt.get("label") or opt.get("title") or "").strip()
            if not opt_name:
                continue
            opt_id = str(opt.get("id") or f"mod_opt_{g_idx + 1}_{o_idx + 1}_{uuid.uuid4().hex[:5]}")
            price_delta = round(max(0.0, _to_float(opt.get("price_delta", opt.get("price", 0.0)), 0.0)), 2)
            is_avail = _to_bool(opt.get("is_available", True), True)
            normalized_options.append({
                "id": opt_id,
                "name": opt_name,
                "price_delta": price_delta,
                "is_available": is_avail,
            })

        if normalized_options:
            normalized_groups.append({
                "id": group_id,
                "name": group_name,
                "required": required,
                "min_selections": min_sel,
                "max_selections": max_sel,
                "options": normalized_options,
            })

    return normalized_groups


def _format_warranty_label(value: Any, unit: str) -> str:
    """Formatea un valor numérico + unidad de garantía en español limpio (ej. '1 año', '6 meses', '30 días')."""
    u = str(unit or "meses").strip().lower()
    if u in ("sin garantía", "sin garantia", "ninguna", "no", "none", "0"):
        return "Sin garantía"
    try:
        num = float(value)
        num_int = int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        return str(value).strip()

    if num <= 0:
        return "Sin garantía"

    if u in ("año", "años", "ano", "anos", "year", "years", "yr"):
        return f"{num_int} {'año' if num_int == 1 else 'años'}"
    if u in ("día", "días", "dia", "dias", "day", "days"):
        return f"{num_int} {'día' if num_int == 1 else 'días'}"
    return f"{num_int} {'mes' if num_int == 1 else 'meses'}"


def normalize_attributes(raw_attributes: Any) -> Dict[str, Any]:
    """
    Normaliza el diccionario de atributos dinámicos del producto (ej. marca, modelo, talla, garantía, etc.).
    Soporta garantías flexibles en días, meses o años:
      - Preset o texto: {"garantia": "1 año"} o {"garantia": "6 meses"}
      - Número + unidad separados: {"garantia_valor": 1, "garantia_unidad": "años"} o {"garantia": 6, "garantia_unidad": "meses"}
      - Objeto estructurado: {"garantia": {"value": 1, "unit": "años"}}
      - Legacy en meses: {"garantia_meses": 6}
    """
    parsed = _parse_json_or_value(raw_attributes, {})
    if not isinstance(parsed, dict):
        return {}

    cleaned: Dict[str, Any] = {}
    for k, v in parsed.items():
        key_str = str(k).strip()
        if not key_str or v is None or v == "":
            continue
        cleaned[key_str] = v

    # Normalización inteligente de Garantía (días / meses / años / sin garantía)
    raw_garantia = cleaned.get("garantia")
    raw_garantia_valor = cleaned.get("garantia_valor")
    raw_garantia_unidad = cleaned.get("garantia_unidad")
    raw_garantia_meses = cleaned.get("garantia_meses")

    if isinstance(raw_garantia, dict):
        w_val = raw_garantia.get("value", raw_garantia.get("valor"))
        w_unit = str(raw_garantia.get("unit", raw_garantia.get("unidad", "meses"))).strip().lower()
        if w_unit in ("sin garantía", "sin garantia", "ninguna") or w_val in (0, "0", None, ""):
            cleaned["garantia"] = "Sin garantía"
            cleaned["garantia_valor"] = 0
            cleaned["garantia_unidad"] = "sin garantía"
        else:
            cleaned["garantia"] = _format_warranty_label(w_val, w_unit)
            try:
                cleaned["garantia_valor"] = int(float(w_val)) if float(w_val).is_integer() else float(w_val)
            except (ValueError, TypeError):
                pass
            cleaned["garantia_unidad"] = w_unit
    elif raw_garantia_valor is not None or raw_garantia_unidad is not None:
        w_unit = str(raw_garantia_unidad or "meses").strip().lower()
        w_val = raw_garantia_valor if raw_garantia_valor is not None else raw_garantia
        if w_unit in ("sin garantía", "sin garantia", "ninguna") or w_val in (0, "0"):
            cleaned["garantia"] = "Sin garantía"
            cleaned["garantia_valor"] = 0
            cleaned["garantia_unidad"] = "sin garantía"
        elif w_val is not None:
            cleaned["garantia"] = _format_warranty_label(w_val, w_unit)
    elif isinstance(raw_garantia, (int, float)):
        cleaned["garantia"] = _format_warranty_label(raw_garantia, "meses")
        cleaned["garantia_valor"] = int(raw_garantia) if float(raw_garantia).is_integer() else float(raw_garantia)
        cleaned["garantia_unidad"] = "meses"
    elif isinstance(raw_garantia, str):
        g_str = raw_garantia.strip()
        if g_str.isdigit():
            num_val = int(g_str)
            cleaned["garantia"] = _format_warranty_label(num_val, "meses")
            cleaned["garantia_valor"] = num_val
            cleaned["garantia_unidad"] = "meses"
    elif raw_garantia is None and raw_garantia_meses is not None:
        cleaned["garantia"] = _format_warranty_label(raw_garantia_meses, "meses")
        try:
            cleaned["garantia_valor"] = int(float(raw_garantia_meses))
            cleaned["garantia_unidad"] = "meses"
        except (ValueError, TypeError):
            pass

    return cleaned


def validate_and_normalize_product_dynamic_data(
    data: Dict[str, Any],
    *,
    subcategory_name: Optional[str] = None,
    category_name: Optional[str] = None,
    base_price: float = 0.0,
    existing_product: Any = None,
) -> Dict[str, Any]:
    """
    Recibe un payload de creación o actualización de Producto (JSON o Multipart) y devuelve
    los campos dinámicos limpios y normalizados listos para asignar al modelo `Product`.
    """
    schema = get_subcategory_schema(subcategory_name=subcategory_name, parent_category_name=category_name)

    # 1. Selling Unit
    raw_unit = data.get("selling_unit")
    if raw_unit is None and existing_product is not None:
        raw_unit = getattr(existing_product, "selling_unit", None)
    selling_unit = str(raw_unit or schema.get("default_selling_unit") or "unit").strip().lower()
    if selling_unit not in SELLING_UNITS_CATALOG:
        selling_unit = schema.get("default_selling_unit", "unit")

    unit_meta = SELLING_UNITS_CATALOG.get(selling_unit, SELLING_UNITS_CATALOG["unit"])

    # 2. Unit Label
    raw_unit_label = data.get("unit_label")
    if raw_unit_label is None and existing_product is not None and data.get("selling_unit") is None:
        raw_unit_label = getattr(existing_product, "unit_label", None)
    unit_label = str(raw_unit_label if raw_unit_label is not None else unit_meta["short_label"]).strip()

    # 3. Allow Fractional Quantity
    raw_fractional = data.get("allow_fractional_quantity")
    if raw_fractional is not None:
        allow_fractional = _to_bool(raw_fractional, unit_meta["allow_fractional"])
    elif existing_product is not None and data.get("selling_unit") is None:
        allow_fractional = bool(getattr(existing_product, "allow_fractional_quantity", unit_meta["allow_fractional"]))
    else:
        allow_fractional = bool(unit_meta["allow_fractional"])

    # 4. Unit Step & Min Order Quantity
    raw_step = data.get("unit_step")
    if raw_step is not None:
        unit_step = max(0.01, _to_float(raw_step, unit_meta["default_step"]))
    elif existing_product is not None and data.get("selling_unit") is None:
        unit_step = max(0.01, _to_float(getattr(existing_product, "unit_step", unit_meta["default_step"]), unit_meta["default_step"]))
    else:
        unit_step = unit_meta["default_step"]

    raw_min = data.get("min_order_quantity")
    if raw_min is not None:
        min_order_quantity = max(0.01, _to_float(raw_min, unit_meta["default_min"]))
    elif existing_product is not None and data.get("selling_unit") is None:
        min_order_quantity = max(0.01, _to_float(getattr(existing_product, "min_order_quantity", unit_meta["default_min"]), unit_meta["default_min"]))
    else:
        min_order_quantity = unit_meta["default_min"]

    # 5. Attributes, Variants, Modifier Groups
    if "attributes" in data:
        attributes = normalize_attributes(data.get("attributes"))
    elif existing_product is not None:
        attributes = normalize_attributes(getattr(existing_product, "attributes", {}))
    else:
        attributes = {}

    if "variants" in data:
        variants = normalize_variants(data.get("variants"), base_price=base_price)
    elif existing_product is not None:
        variants = normalize_variants(getattr(existing_product, "variants", []), base_price=base_price)
    else:
        variants = []

    if "modifier_groups" in data:
        modifier_groups = normalize_modifier_groups(data.get("modifier_groups"))
    elif existing_product is not None:
        modifier_groups = normalize_modifier_groups(getattr(existing_product, "modifier_groups", []))
    else:
        modifier_groups = []

    return {
        "selling_unit": selling_unit,
        "unit_label": unit_label,
        "allow_fractional_quantity": allow_fractional,
        "min_order_quantity": round(min_order_quantity, 3),
        "unit_step": round(unit_step, 3),
        "attributes": attributes,
        "variants": variants,
        "modifier_groups": modifier_groups,
    }


def resolve_cart_item_dynamic_pricing(
    product: Any,
    item_payload: Dict[str, Any],
) -> Tuple[float, Dict[str, Any]]:
    """
    Calcula el precio unitario efectivo de un ítem en el carrito tomando en cuenta:
    - Variante seleccionada (`selected_variant_id` o `selected_variant`)
    - Modificadores/extras seleccionados (`selected_modifiers`: lista de IDs o dicts)
    - Notas u opciones seleccionadas (`selected_options`, `customer_notes`)
    Devuelve `(effective_unit_price, selection_metadata_dict)`.
    """
    base_price = round(float(getattr(product, "price", 0.0) or 0.0), 2)
    effective_unit_price = base_price

    variants = normalize_variants(getattr(product, "variants", []), base_price=base_price)
    modifier_groups = normalize_modifier_groups(getattr(product, "modifier_groups", []))

    # 1. Resolver Variante seleccionada
    selected_variant_input = item_payload.get("selected_variant_id") or item_payload.get("selected_variant") or item_payload.get("variant_id")
    matched_variant: Optional[Dict[str, Any]] = None

    if selected_variant_input and variants:
        if isinstance(selected_variant_input, dict):
            target_id = str(selected_variant_input.get("id") or "").strip()
            target_name = str(selected_variant_input.get("name") or selected_variant_input.get("label") or "").strip().lower()
        else:
            target_id = str(selected_variant_input).strip()
            target_name = target_id.lower()

        for v in variants:
            if (target_id and v["id"] == target_id) or (target_name and v["name"].lower() == target_name):
                matched_variant = v
                break

    if matched_variant is not None:
        effective_unit_price = float(matched_variant.get("effective_price", base_price))

    # 2. Resolver Modificadores / Extras seleccionados
    raw_selected_mods = item_payload.get("selected_modifiers") or item_payload.get("modifiers") or []
    if isinstance(raw_selected_mods, str):
        raw_selected_mods = _parse_json_or_value(raw_selected_mods, [])
    if not isinstance(raw_selected_mods, list):
        raw_selected_mods = []

    # Construir índice de opciones válidas del producto
    valid_mod_options: Dict[str, Dict[str, Any]] = {}
    valid_mod_by_name: Dict[str, Dict[str, Any]] = {}
    for grp in modifier_groups:
        for opt in grp.get("options", []):
            opt_entry = {
                "group_id": grp["id"],
                "group_name": grp["name"],
                "id": opt["id"],
                "name": opt["name"],
                "price_delta": float(opt.get("price_delta", 0.0)),
            }
            valid_mod_options[str(opt["id"])] = opt_entry
            valid_mod_by_name[opt["name"].lower()] = opt_entry

    matched_modifiers: List[Dict[str, Any]] = []
    modifiers_total_delta = 0.0

    # Expandir formatos agrupados {"group_id": "...", "option_ids": ["..."]} y formatos planos
    flattened_mod_requests: List[Any] = []
    for mod_req in raw_selected_mods:
        if isinstance(mod_req, dict) and ("option_ids" in mod_req or "options" in mod_req):
            sub_opts = mod_req.get("option_ids") or mod_req.get("options") or []
            if isinstance(sub_opts, list):
                flattened_mod_requests.extend(sub_opts)
        else:
            flattened_mod_requests.append(mod_req)

    for mod_req in flattened_mod_requests:
        matched_opt: Optional[Dict[str, Any]] = None
        qty_multiplier = 1
        if isinstance(mod_req, dict):
            m_id = str(mod_req.get("id") or mod_req.get("option_id") or "").strip()
            m_name = str(mod_req.get("name") or mod_req.get("label") or "").strip().lower()
            qty_multiplier = max(1, int(_to_float(mod_req.get("quantity", 1), 1)))
            if m_id and m_id in valid_mod_options:
                matched_opt = valid_mod_options[m_id]
            elif m_name and m_name in valid_mod_by_name:
                matched_opt = valid_mod_by_name[m_name]
        elif isinstance(mod_req, str):
            m_key = mod_req.strip()
            if m_key in valid_mod_options:
                matched_opt = valid_mod_options[m_key]
            elif m_key.lower() in valid_mod_by_name:
                matched_opt = valid_mod_by_name[m_key.lower()]

        if matched_opt is not None:
            delta = round(matched_opt["price_delta"] * qty_multiplier, 2)
            modifiers_total_delta += delta
            matched_modifiers.append({
                "group_id": matched_opt["group_id"],
                "group_name": matched_opt["group_name"],
                "id": matched_opt["id"],
                "name": matched_opt["name"],
                "price_delta": matched_opt["price_delta"],
                "quantity": qty_multiplier,
                "total_delta": delta,
            })

    effective_unit_price = round(max(0.0, effective_unit_price + modifiers_total_delta), 2)

    # 3. Opciones libres seleccionadas (ej. talla/color si el producto las tiene en attributes o opciones simples)
    selected_options = _parse_json_or_value(item_payload.get("selected_options"), {})
    if not isinstance(selected_options, dict):
        selected_options = {}
    if matched_variant and matched_variant.get("options"):
        merged_opts = dict(matched_variant["options"])
        merged_opts.update(selected_options)
        selected_options = merged_opts

    customer_notes = str(item_payload.get("customer_notes") or item_payload.get("notes") or "").strip()[:300]
    selling_unit = getattr(product, "selling_unit", "unit") or "unit"
    unit_label = getattr(product, "unit_label", "") or SELLING_UNITS_CATALOG.get(selling_unit, SELLING_UNITS_CATALOG["unit"])["short_label"]

    selection_meta = {
        "selling_unit": selling_unit,
        "unit_label": unit_label,
        "base_price": base_price,
        "effective_unit_price": effective_unit_price,
        "selected_variant": {
            "id": matched_variant["id"],
            "name": matched_variant["name"],
            "options": matched_variant.get("options", {}),
            "price_delta": matched_variant.get("price_delta", 0.0),
            "effective_price": matched_variant.get("effective_price", base_price),
        } if matched_variant else None,
        "selected_modifiers": matched_modifiers,
        "modifiers_total_delta": round(modifiers_total_delta, 2),
        "selected_options": selected_options,
        "customer_notes": customer_notes,
    }

    return effective_unit_price, selection_meta
