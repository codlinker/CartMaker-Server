"""Centros comerciales de Venezuela (api/static/json/malls.json) para que Atlas
pueda decir en qué centro comercial está un producto.

El JSON se carga una sola vez por proceso. La detección geográfica sirve de
respaldo cuando una tienda no tiene `StoreLocation.mall` asignado en la BD.
"""

import json
import os
from functools import lru_cache
from typing import Dict, List, Optional

from django.conf import settings

from api.core.ve_geo import haversine_km

# Una tienda dentro de un centro comercial queda a menos de esta distancia de sus coordenadas.
MALL_MATCH_RADIUS_M = 120.0


def display_mall_name(name: str) -> str:
    """'CC Sambil Chacao' -> 'Sambil Chacao' (el prefijo 'CC' no se dice en voz alta)."""
    clean = (name or '').strip()
    if clean.upper().startswith('CC '):
        clean = clean[3:].strip()
    return clean


@lru_cache(maxsize=1)
def load_malls() -> List[Dict]:
    """Lista plana de centros comerciales con estado y municipio/ciudad."""
    json_path = os.path.join(settings.BASE_DIR, 'api', 'static', 'json', 'malls.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []

    malls: List[Dict] = []
    for estado, ciudades in raw.items():
        for ciudad, entries in ciudades.items():
            for entry in entries:
                try:
                    lat = float(entry['lat'])
                    lng = float(entry['lng'])
                except (KeyError, TypeError, ValueError):
                    continue
                malls.append({
                    'name': display_mall_name(entry.get('name', '')),
                    'lat': lat,
                    'lng': lng,
                    'floors_quantity': entry.get('floors_quantity'),
                    'estado': estado,
                    'ciudad': ciudad,
                })
    return malls


def find_mall_near(lat: float, lng: float, radius_m: float = MALL_MATCH_RADIUS_M) -> Optional[Dict]:
    """Centro comercial más cercano dentro del radio dado, o None."""
    best = None
    best_dist_m = None
    for mall in load_malls():
        dist_m = haversine_km(lat, lng, mall['lat'], mall['lng']) * 1000.0
        if dist_m <= radius_m and (best_dist_m is None or dist_m < best_dist_m):
            best, best_dist_m = mall, dist_m
    return best
