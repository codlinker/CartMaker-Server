"""
Calendario de campañas / eventos estacionales del Home (`GET /api/v1/cache/home`).

Fuente de verdad ÚNICA de qué subcategorías oficiales (`CATALOGO_ESTRUCTURA`) se protagonizan en cada
fecha del año. Es 100 % reactivo: el backend resuelve el evento activo con la fecha local del servidor
(America/Caracas), así que nunca hay que tocarlo a mano salvo para añadir/ajustar una campaña.

Los nombres de subcategoría DEBEN coincidir exactamente con `CATALOGO_ESTRUCTURA`
(lo valida `api/tests.py::HomeSeasonsCatalogConsistencyTests`).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# (mes, día) inclusive. Una campaña puede tener varias ventanas (ej. Navidad).
_Window = Tuple[Tuple[int, int], Tuple[int, int]]

SEASONAL_CAMPAIGNS: List[Dict[str, Any]] = [
    {
        "id": "halloween",
        "name": "Halloween",
        "windows": [((10, 12), (11, 2))],
        "subcategories": [
            "Chucherías, Snacks y Dulces",
            "Piñatas, Cotillones y Globos",
            "Maquillaje de Rostro, Ojos y Labios",
            "Tortas, Postres, Donas y Dulcería",
            "Combos de Comida Rápida y Menús Compartir",
            "Bebidas, Refrescos y Maltas",
            "Licores",
        ],
    },
    {
        "id": "black_friday",
        "name": "Black Friday & Cyber Days",
        "windows": [((11, 20), (11, 30))],
        "subcategories": [
            "Teléfonos y Tablets",
            "Monitores y Televisores",
            "Línea Blanca, Neveras y Lavadoras",
            "Computadoras y Laptops",
            "Consolas y Videojuegos",
            "Aires Acondicionados y Ventiladores",
            "Zapatos Deportivos y de Goma",
            "Herramientas Eléctricas, Taladros y Esmeriles",
        ],
    },
    {
        "id": "navidad",
        "name": "Navidad y Fin de Año",
        "windows": [((11, 3), (11, 19)), ((12, 1), (12, 31))],
        "subcategories": [
            "Muñecas, Barbies y Bebés",
            "Figuras de Acción y Superhéroes",
            "Bloques, Legos y Armables",
            "Consolas y Videojuegos",
            "Vestidos, Faldas y Enterizos",
            "Franelas, Chemises y Camisas de Caballero",
            "Licores",
            "Carnicería y Aves",
            "Panadería y Pastelería",
            "Perfumería, Splash y Fragancias",
        ],
    },
    {
        "id": "reyes_magos",
        "name": "Reyes Magos",
        "windows": [((1, 1), (1, 10))],
        "subcategories": [
            "Muñecas, Barbies y Bebés",
            "Figuras de Acción y Superhéroes",
            "Bloques, Legos y Armables",
            "Consolas y Videojuegos",
            "Juguetes de Exterior, Patinetas y Triciclos",
            "Bicicletas y Ciclismo",
        ],
    },
    {
        "id": "san_valentin",
        "name": "San Valentín",
        "windows": [((2, 1), (2, 16))],
        "subcategories": [
            "Perfumería, Splash y Fragancias",
            "Peluches",
            "Joyería y Bisutería",
            "Chucherías, Snacks y Dulces",
            "Tortas, Postres, Donas y Dulcería",
            "Sushi, Rolls y Comida Asiática",
            "Bolsos y Carteras",
            "Lentes y Relojes",
        ],
    },
    {
        "id": "carnaval_playa",
        "name": "Carnaval, Semana Santa y Playa",
        "windows": [((2, 17), (4, 15))],
        "subcategories": [
            "Trajes de Baño y Ropa Playera",
            "Cavas, Coolers y Termos",
            "Camping, Carpas y Colchones Inflables",
            "Juguetes de Piscina, Playa e Inflables",
            "Pescadería y Mariscos",
            "Pescados Fritos, Mariscos y Ceviches",
            "Cholas, Sandalias y Tacones",
        ],
    },
    {
        "id": "dia_de_la_madre",
        "name": "Día de las Madres",
        "windows": [((4, 25), (5, 18))],
        "subcategories": [
            "Perfumería, Splash y Fragancias",
            "Skincare y Cuidado Facial",
            "Bolsos y Carteras",
            "Joyería y Bisutería",
            "Blusas, Tops y Franelas de Dama",
            "Vestidos, Faldas y Enterizos",
            "Tortas, Postres, Donas y Dulcería",
            "Pequeños Electrodomésticos y Cocina",
        ],
    },
    {
        "id": "dia_del_padre",
        "name": "Día del Padre",
        "windows": [((6, 1), (6, 24))],
        "subcategories": [
            "Herramientas Eléctricas, Taladros y Esmeriles",
            "Lentes y Relojes",
            "Licores",
            "Parrillas, Carnes y Asados",
            "Franelas, Chemises y Camisas de Caballero",
            "Smartwatches y Wearables",
            "Billeteras y Monederos",
            "Sonido para Carros, Reproductores y Plantas",
        ],
    },
    {
        "id": "dia_del_nino",
        "name": "Día del Niño",
        "windows": [((7, 1), (7, 24))],
        "subcategories": [
            "Muñecas, Barbies y Bebés",
            "Figuras de Acción y Superhéroes",
            "Bloques, Legos y Armables",
            "Consolas y Videojuegos",
            "Juguetes de Exterior, Patinetas y Triciclos",
            "Bicicletas y Ciclismo",
            "Helados, Merengadas, Waffles y Crepes",
            "Chucherías, Snacks y Dulces",
        ],
    },
    {
        "id": "regreso_a_clases",
        "name": "Regreso a Clases",
        "windows": [((8, 15), (9, 30))],
        "subcategories": [
            "Cuadernos, Libretas y Blocks",
            "Morrales Escolares y Cartucheras",
            "Lápices, Colores, Bolígrafos y Marcadores",
            "Computadoras y Laptops",
            "Impresoras y Escaners",
            "Zapatos Deportivos y de Goma",
            "Libros Escolares, Novelas y Literatura",
        ],
    },
]

# Modo diario (cuando no hay campaña activa): protagonismo según la hora local.
DAILY_MODES: List[Dict[str, Any]] = [
    {
        "id": "daily_morning",
        "name": "Mañana de Desayunos y Mercado",
        "hours": (5, 11),
        "subcategories": [
            "Arepas, Cachapas y Desayunos Criollos",
            "Empanadas, Pastelitos y Frituras",
            "Panadería y Pastelería",
            "Café, Té e Infusiones",
        ],
    },
    {
        "id": "daily_afternoon",
        "name": "Almuerzos y Antojos de la Tarde",
        "hours": (11, 18),
        "subcategories": [
            "Almuerzos, Comida Criolla y Ejecutivos",
            "Pollo en Brasa, Broaster y Alitas",
            "Parrillas, Carnes y Asados",
            "Tortas, Postres, Donas y Dulcería",
        ],
    },
    {
        "id": "daily_night",
        "name": "Noche de Burgers, Pizzas y Antojos",
        "hours": None,  # resto del día (18:00 – 05:00)
        "subcategories": [
            "Perros Calientes, Hamburguesas y Pepitos",
            "Pizzas, Pastas y Comida Italiana",
            "Sushi, Rolls y Comida Asiática",
            "Shawarmas, Falafel y Comida Árabe",
        ],
    },
]


def _in_window(day: date, window: _Window) -> bool:
    (m1, d1), (m2, d2) = window
    return (m1, d1) <= (day.month, day.day) <= (m2, d2)


def resolve_active_campaign(now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Devuelve la campaña activa: {id, name, kind ('seasonal'|'daily'), subcategories}.
    `now` debe estar en hora local (por defecto `timezone.localtime()`).
    """
    if now is None:
        from django.utils import timezone
        now = timezone.localtime()

    day = now.date()
    for camp in SEASONAL_CAMPAIGNS:
        if any(_in_window(day, w) for w in camp["windows"]):
            return {
                "id": camp["id"],
                "name": camp["name"],
                "kind": "seasonal",
                "subcategories": list(camp["subcategories"]),
            }

    hour = now.hour
    fallback = DAILY_MODES[-1]
    for mode in DAILY_MODES:
        hours = mode["hours"]
        if hours and hours[0] <= hour < hours[1]:
            fallback = mode
            break
    return {
        "id": fallback["id"],
        "name": fallback["name"],
        "kind": "daily",
        "subcategories": list(fallback["subcategories"]),
    }
