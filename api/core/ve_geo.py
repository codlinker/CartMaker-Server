"""Gazetario ligero de Venezuela para deducir la zona (ciudad) de unas coordenadas.

No depende de servicios externos: se usa la ciudad conocida más cercana por
distancia haversine. Pensado para que Atlas pueda decir "en Guatire no conseguí,
lo más cercano estuvo en Caracas" sin geocodificación de pago.
"""

import math
from typing import List, Optional, Tuple

# (nombre, latitud, longitud)
VE_PLACES: List[Tuple[str, float, float]] = [
    # Miranda / Distrito Capital / La Guaira
    ('Caracas', 10.4806, -66.9036),
    ('Petare', 10.4764, -66.8097),
    ('Guarenas', 10.4693, -66.6102),
    ('Guatire', 10.4736, -66.5413),
    ('Higuerote', 10.4833, -66.0983),
    ('Río Chico', 10.3167, -65.9833),
    ('Los Teques', 10.3447, -67.0431),
    ('Charallave', 10.2433, -66.8575),
    ('Cúa', 10.1667, -66.8833),
    ('Ocumare del Tuy', 10.1144, -66.7753),
    ('Santa Teresa del Tuy', 10.2339, -66.6611),
    ('San Antonio de los Altos', 10.3836, -66.9614),
    ('La Guaira', 10.6000, -66.9333),
    ('Catia La Mar', 10.6000, -67.0300),
    ('Altagracia de Orituco', 9.8667, -66.3833),
    # Aragua / Carabobo / Yaracuy / Cojedes
    ('Maracay', 10.2469, -67.5958),
    ('Turmero', 10.2272, -67.4750),
    ('Cagua', 10.1869, -67.4594),
    ('La Victoria', 10.2272, -67.3331),
    ('Villa de Cura', 10.0356, -67.4825),
    ('Valencia', 10.1620, -68.0077),
    ('Guacara', 10.2264, -67.8833),
    ('Puerto Cabello', 10.4731, -68.0125),
    ('San Felipe', 10.3399, -68.7425),
    ('San Carlos', 9.6611, -68.5828),
    ('Tinaquillo', 9.9167, -68.3000),
    # Guárico / Apure / Barinas / Portuguesa
    ('San Juan de los Morros', 9.9094, -67.3544),
    ('Calabozo', 8.9242, -67.4294),
    ('Valle de la Pascua', 9.2153, -66.0072),
    ('San Fernando de Apure', 7.8878, -67.4728),
    ('Barinas', 8.6226, -70.2075),
    ('Guanare', 9.0418, -69.7421),
    ('Acarigua', 9.5597, -69.2008),
    # Occidente
    ('Barquisimeto', 10.0678, -69.3467),
    ('Carora', 10.1667, -70.0833),
    ('Coro', 11.4045, -69.6734),
    ('Punto Fijo', 11.6910, -70.1990),
    ('Maracaibo', 10.6544, -71.6405),
    ('Cabimas', 10.3883, -71.4439),
    ('Trujillo', 9.3667, -70.4333),
    ('Valera', 9.3178, -70.6036),
    ('Mérida', 8.5897, -71.1561),
    ('San Cristóbal', 7.7669, -72.2250),
    # Oriente
    ('Barcelona', 10.1333, -64.7000),
    ('Puerto La Cruz', 10.2136, -64.6322),
    ('Clarines', 9.9333, -65.1667),
    ('El Tigre', 8.8920, -64.2530),
    ('Cumaná', 10.4536, -64.1675),
    ('Maturín', 9.7457, -63.1832),
    ('Porlamar', 10.9577, -63.8497),
    # Guayana / Amazonas
    ('Ciudad Bolívar', 8.1292, -63.5497),
    ('Ciudad Guayana', 8.3597, -62.6528),
    ('Tucupita', 9.0614, -62.0517),
    ('Puerto Ayacucho', 5.6639, -67.6236),
]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def nearest_place(lat: float, lng: float) -> Optional[Tuple[str, float]]:
    """(nombre, distancia_km) de la ciudad conocida más cercana, o None si no hay gazetario."""
    best = None
    for name, p_lat, p_lng in VE_PLACES:
        dist = haversine_km(lat, lng, p_lat, p_lng)
        if best is None or dist < best[1]:
            best = (name, dist)
    return best


def describe_zone(lat: float, lng: float, near_threshold_km: float = 12.0) -> str:
    """
    Nombre legible de la zona: 'Guatire' si está dentro del umbral de la ciudad;
    'la zona de Guatire' si queda más lejos pero esa es la referencia más cercana.
    """
    place = nearest_place(lat, lng)
    if not place:
        return 'tu zona'
    name, dist_km = place
    if dist_km <= near_threshold_km:
        return name
    return f'la zona de {name}'
