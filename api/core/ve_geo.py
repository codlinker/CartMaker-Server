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
    # Sectores y urbanizaciones de Caracas (para hablar en nombres de zona, no en distancias)
    ('Altamira, Caracas', 10.4967, -66.8486),
    ('La Castellana, Caracas', 10.5010, -66.8530),
    ('Los Palos Grandes, Caracas', 10.4980, -66.8420),
    ('Chacao, Caracas', 10.4958, -66.8531),
    ('El Rosal, Caracas', 10.4925, -66.8590),
    ('Chacaíto, Caracas', 10.4900, -66.8700),
    ('Las Mercedes, Caracas', 10.4846, -66.8648),
    ('Sabana Grande, Caracas', 10.4890, -66.8750),
    ('Colinas de Bello Monte, Caracas', 10.4750, -66.8870),
    ('Plaza Venezuela, Caracas', 10.4910, -66.8920),
    ('El Cafetal, Caracas', 10.4560, -66.8500),
    ('Prados del Este, Caracas', 10.4430, -66.8650),
    ('La Trinidad, Caracas', 10.4400, -66.8700),
    ('Santa Fe, Caracas', 10.4560, -66.8700),
    ('Los Ruices, Caracas', 10.4900, -66.8195),
    ('La Urbina, Caracas', 10.4700, -66.8190),
    ('Boleíta, Caracas', 10.4975, -66.8180),
    ('El Marqués, Caracas', 10.4930, -66.8070),
    ('Macaracuay, Caracas', 10.4700, -66.8120),
    ('El Hatillo', 10.4222, -66.8247),
    ('Baruta', 10.4333, -66.8750),
    ('Centro de Caracas', 10.5061, -66.9146),
    ('La Candelaria, Caracas', 10.5050, -66.9040),
    ('El Paraíso, Caracas', 10.4950, -66.9300),
    ('Catia, Caracas', 10.5150, -66.9500),
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


def proximity_label(meters: Optional[float]) -> str:
    """
    Cercanía en lenguaje humano, SIN cifras ni unidades (Atlas tiene prohibido hablar
    en metros o kilómetros). Se usa junto al nombre de la zona.
    """
    if meters is None:
        return ''
    if meters < 1000:
        return 'muy cerca de tu ubicación, prácticamente en tu misma zona'
    if meters < 4000:
        return 'cerca, en tu misma zona'
    if meters < 12000:
        return 'en otra zona de tu misma ciudad o área'
    if meters < 45000:
        return 'en otra ciudad cercana (hay que trasladarse)'
    return 'lejos de tu zona, en otra región del país'
