"""
Cliente de OSRM nativo (servicios systemd `osrm-car` / `osrm-bike`, ver `scripts/osrm/`).

Instancias:
- `settings.OSRM_CAR_URL`  (:5000, perfil car.lua)      -> moto y carro.
- `settings.OSRM_BIKE_URL` (:5001, perfil bicycle.lua)  -> bicicleta y a pie.

APIs usadas:
- `route(origin, dest, profile)`  -> geometría (polyline6), distancia, duración y perfil de tiempos
  acumulado por punto (`cum_dist` / `cum_time`), base de la predicción (Dead Reckoning).
- `table(sources, destination, profile)` -> segundos reales por calle desde N orígenes a un destino.
- `match(points, timestamps, profile)`  -> ajuste de una traza GPS a la red vial.

Convenciones:
- Todas las coordenadas de entrada/salida de este módulo son `(lat, lng)`.
  OSRM usa `lng,lat`: la conversión se hace aquí adentro.
- Los errores de red o de OSRM se lanzan como `RoutingError` (nunca se cuelga: hay timeouts).
"""
import logging
import math
from typing import Iterable, List, Optional, Sequence, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

LatLng = Tuple[float, float]

PROFILE_CAR = 'car'
PROFILE_BIKE = 'bike'

# Velocidades medias de respaldo (m/s) cuando se usa el fallback geodésico o ajuste de perfil
_FALLBACK_SPEED_MPS = {
    PROFILE_CAR: 8.33,   # ~30 km/h promedio urbano moto/carro
    PROFILE_BIKE: 4.17,  # ~15 km/h promedio urbano bici
}

# VehicleType (api.models): MOTO=0, BICI=1, CARRO=2, PIE=3
_VEHICLE_PROFILE = {
    0: PROFILE_CAR,   # Moto: car.lua (ajustado para moto)
    1: PROFILE_BIKE,  # Bicicleta
    2: PROFILE_CAR,   # Carro
    3: PROFILE_BIKE,  # A pie: instancia de bici/pie
}

DEFAULT_TIMEOUT = 4.0
MAX_TABLE_SOURCES = 100
MAX_MATCH_POINTS = 500


class RoutingError(Exception):
    """ Error al consultar OSRM (red caída, timeout, respuesta inválida o sin ruta). """

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code


# =========================================================================
# PERFILES
# =========================================================================
def profile_for_vehicle(vehicle_type) -> str:
    """ Perfil OSRM según `Employee.vehicle_type` (None -> carro/moto). """
    try:
        return _VEHICLE_PROFILE.get(int(vehicle_type), PROFILE_CAR)
    except (TypeError, ValueError):
        return PROFILE_CAR


def _base_url(profile: str) -> str:
    if profile == PROFILE_BIKE:
        return getattr(settings, 'OSRM_BIKE_URL', 'http://127.0.0.1:5001').rstrip('/')
    return getattr(settings, 'OSRM_CAR_URL', 'http://127.0.0.1:5000').rstrip('/')


def _timeout() -> float:
    try:
        return float(getattr(settings, 'OSRM_TIMEOUT_SECONDS', DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT


# =========================================================================
# POLYLINE6
# =========================================================================
def decode_polyline(encoded: str, precision: int = 6) -> List[LatLng]:
    """
    Decodifica un polyline de Google con la precisión indicada (OSRM `geometries=polyline6` -> 6).
    Retorna una lista de `(lat, lng)`.
    """
    if not encoded:
        return []
    factor = float(10 ** precision)
    coords: List[LatLng] = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)

    while index < length:
        deltas = []
        for _axis in range(2):
            shift = 0
            result = 0
            while True:
                if index >= length:
                    raise RoutingError("Polyline corrupto o truncado.", code='invalid_polyline')
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if (result & 1) else (result >> 1))
        lat += deltas[0]
        lng += deltas[1]
        coords.append((lat / factor, lng / factor))
    return coords


def encode_polyline(points: Iterable[LatLng], precision: int = 6) -> str:
    """ Codifica `(lat, lng)` como polyline (útil para pruebas y para reenviar rutas recortadas). """
    factor = 10 ** precision
    output = []
    prev_lat = 0
    prev_lng = 0
    for lat, lng in points:
        ilat = int(round(lat * factor))
        ilng = int(round(lng * factor))
        for delta in (ilat - prev_lat, ilng - prev_lng):
            value = ~(delta << 1) if delta < 0 else (delta << 1)
            while value >= 0x20:
                output.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            output.append(chr(value + 63))
        prev_lat = ilat
        prev_lng = ilng
    return ''.join(output)


# =========================================================================
# HTTP
# =========================================================================
def _validate_point(point, name: str = 'punto') -> LatLng:
    try:
        lat = float(point[0])
        lng = float(point[1])
    except (TypeError, ValueError, IndexError):
        raise RoutingError(f"Coordenada inválida en {name}.", code='invalid_coordinate')
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        raise RoutingError(f"Coordenada fuera de rango en {name}.", code='invalid_coordinate')
    return lat, lng


def _coords_param(points: Sequence[LatLng]) -> str:
    # OSRM espera "lng,lat;lng,lat"
    return ';'.join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)


def _get(profile: str, service: str, coords: str, params: dict) -> dict:
    url = f"{_base_url(profile)}/{service}/v1/driving/{coords}"
    try:
        response = requests.get(url, params=params, timeout=_timeout())
    except requests.Timeout:
        raise RoutingError("El servicio de rutas no respondió a tiempo.", code='timeout')
    except requests.RequestException as e:
        logger.warning(f"OSRM ({profile}) no disponible: {e}")
        raise RoutingError("El servicio de rutas no está disponible.", code='unavailable')

    try:
        data = response.json()
    except ValueError:
        raise RoutingError("Respuesta inválida del servicio de rutas.", code='invalid_response')

    osrm_code = data.get('code')
    if response.status_code != 200 or osrm_code != 'Ok':
        message = data.get('message') or "No se pudo calcular la ruta."
        logger.info(f"OSRM ({profile}) {service} -> {response.status_code} {osrm_code}: {message}")
        raise RoutingError(message, code=str(osrm_code or response.status_code))
    return data


# =========================================================================
# FALLBACKS PARA ENTORNOS SIN OSRM LOCAL (AWS EC2 MICRO / DESARROLLO)
# =========================================================================
def _haversine_m(p1: LatLng, p2: LatLng) -> float:
    """ Distancia en metros sobre la esfera terrestre entre dos `(lat, lng)`. """
    r = 6371000.0
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _mapbox_route_fallback(origin: LatLng, dest: LatLng, profile: str) -> Optional[dict]:
    """
    Si el contenedor OSRM local no está levantado (p. ej. en una EC2 micro sin Docker),
    intenta calcular la ruta real por calle usando `settings.MAPBOX_APIKEY` (cuyo formato
    de respuesta es idéntico a OSRM v5).
    """
    api_key = getattr(settings, 'MAPBOX_APIKEY', None)
    if not api_key:
        return None
    mb_profile = 'cycling' if profile == PROFILE_BIKE else 'driving'
    coords = _coords_param([origin, dest])
    url = f"https://api.mapbox.com/directions/v5/mapbox/{mb_profile}/{coords}"
    try:
        resp = requests.get(
            url,
            params={
                'access_token': api_key,
                'overview': 'full',
                'geometries': 'polyline6',
                'annotations': 'duration,distance',
                'steps': 'false',
                'alternatives': 'false',
            },
            timeout=_timeout(),
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        routes = data.get('routes') or []
        if not routes:
            return None
        best = routes[0]
        encoded = best.get('geometry') or ''
        points = decode_polyline(encoded, precision=6)
        cum_dist, cum_time = _build_cumulative_profile(best, len(points))
        return {
            'polyline6': encoded,
            'points': points,
            'distance_m': float(best.get('distance') or 0.0),
            'duration_s': float(best.get('duration') or 0.0),
            'cum_dist': cum_dist,
            'cum_time': cum_time,
            'profile': profile,
        }
    except Exception as e:
        logger.debug(f"Mapbox route fallback falló: {e}")
        return None


def _geodesic_route_fallback(origin: LatLng, dest: LatLng, profile: str) -> dict:
    """
    Último respaldo (0 RAM, 0 llamadas externas): interpola una polilínea suave de N segmentos
    con factor de tortuosidad urbana (1.28x) para que Dead Reckoning y ETA funcionen siempre.
    """
    straight_m = _haversine_m(origin, dest)
    road_dist_m = round(straight_m * 1.28, 2)
    speed = _FALLBACK_SPEED_MPS.get(profile, _FALLBACK_SPEED_MPS[PROFILE_CAR])
    duration_s = round(road_dist_m / speed, 2) if road_dist_m > 0 else 0.0

    steps = max(2, min(40, int(road_dist_m // 50) + 2))
    points: List[LatLng] = []
    cum_dist: List[float] = []
    cum_time: List[float] = []
    for i in range(steps):
        frac = i / float(steps - 1)
        lat = origin[0] + (dest[0] - origin[0]) * frac
        lng = origin[1] + (dest[1] - origin[1]) * frac
        points.append((round(lat, 6), round(lng, 6)))
        cum_dist.append(round(road_dist_m * frac, 2))
        cum_time.append(round(duration_s * frac, 2))

    return {
        'polyline6': encode_polyline(points, precision=6),
        'points': points,
        'distance_m': road_dist_m,
        'duration_s': duration_s,
        'cum_dist': cum_dist,
        'cum_time': cum_time,
        'profile': profile,
    }


# =========================================================================
# /route
# =========================================================================
def _build_cumulative_profile(route: dict, n_points: int) -> Tuple[List[float], List[float]]:
    """
    Arma `cum_dist` (m) y `cum_time` (s) por punto de la geometría a partir de
    `legs[].annotation.distance/duration` (un valor por segmento entre puntos consecutivos).
    """
    seg_dist: List[float] = []
    seg_time: List[float] = []
    for leg in route.get('legs', []) or []:
        annotation = leg.get('annotation') or {}
        seg_dist.extend(float(x or 0.0) for x in (annotation.get('distance') or []))
        seg_time.extend(float(x or 0.0) for x in (annotation.get('duration') or []))

    cum_dist = [0.0]
    cum_time = [0.0]
    for d, t in zip(seg_dist, seg_time):
        cum_dist.append(round(cum_dist[-1] + d, 2))
        cum_time.append(round(cum_time[-1] + t, 2))

    # Con overview=full y una sola pierna, len(segmentos) == n_points - 1.
    # Si no cuadra (p. ej. waypoints intermedios duplicados), se ajusta para no romper la predicción.
    if len(cum_dist) > n_points:
        cum_dist = cum_dist[:n_points]
        cum_time = cum_time[:n_points]
    while len(cum_dist) < n_points:
        cum_dist.append(cum_dist[-1])
        cum_time.append(cum_time[-1])
    return cum_dist, cum_time


def route(origin: LatLng, dest: LatLng, profile: str = PROFILE_CAR) -> dict:
    """
    Calcula la ruta entre dos puntos `(lat, lng)`.
    Si el servicio OSRM local no está activo, usa automáticamente Mapbox Directions API
    o interpolación geodésica urbana.

    Returns:
        dict: {
            'polyline6': str,              # geometría codificada (precisión 6)
            'points': [(lat, lng), ...],   # geometría decodificada
            'distance_m': float,
            'duration_s': float,
            'cum_dist': [float, ...],      # metros acumulados por punto (len == len(points))
            'cum_time': [float, ...],      # segundos esperados acumulados por punto
            'profile': 'car' | 'bike',
        }
    """
    o = _validate_point(origin, 'origen')
    d = _validate_point(dest, 'destino')
    req_params = {
        'overview': 'full',
        'geometries': 'polyline6',
        'annotations': 'duration,distance',
        'steps': 'false',
        'alternatives': 'false',
    }
    try:
        data = _get(profile, 'route', _coords_param([o, d]), req_params)
        scale_time = 1.0
    except RoutingError as err:
        # Si pidió 'bike' y solo el servicio 'osrm-car' (:5000) está encendido en la EC2 micro:
        if profile == PROFILE_BIKE and err.code in ('unavailable', 'timeout'):
            try:
                data = _get(PROFILE_CAR, 'route', _coords_param([o, d]), req_params)
                scale_time = 1.8  # ajusta tiempos de carro a ritmo de bici
            except RoutingError:
                data = None
        else:
            data = None

        if data is None:
            mb = _mapbox_route_fallback(o, d, profile)
            if mb is not None:
                return mb
            return _geodesic_route_fallback(o, d, profile)

    routes = data.get('routes') or []
    if not routes:
        return _geodesic_route_fallback(o, d, profile)

    best = routes[0]
    encoded = best.get('geometry') or ''
    points = decode_polyline(encoded, precision=6)
    cum_dist, cum_time = _build_cumulative_profile(best, len(points))
    if scale_time != 1.0:
        cum_time = [round(t * scale_time, 2) for t in cum_time]
    return {
        'polyline6': encoded,
        'points': points,
        'distance_m': float(best.get('distance') or 0.0),
        'duration_s': round(float(best.get('duration') or 0.0) * scale_time, 2),
        'cum_dist': cum_dist,
        'cum_time': cum_time,
        'profile': profile,
    }


# =========================================================================
# /table
# =========================================================================
def table(sources: Sequence[LatLng], destination: LatLng, profile: str = PROFILE_CAR) -> List[Optional[float]]:
    """
    Tiempo real por calle (segundos) desde cada origen hasta `destination`.
    Si OSRM no está levantado, estima los tiempos con distancia urbana (1.28x Haversine).

    Returns:
        list: Un valor por origen, en el mismo orden. `None` si ese origen no tiene ruta.
    """
    if not sources:
        return []
    if len(sources) > MAX_TABLE_SOURCES:
        raise RoutingError(f"Máximo {MAX_TABLE_SOURCES} orígenes por consulta.", code='too_many_sources')

    clean_sources = [_validate_point(p, f'origen {i}') for i, p in enumerate(sources)]
    dest = _validate_point(destination, 'destino')
    all_points = clean_sources + [dest]
    dest_index = len(all_points) - 1
    req_params = {
        'sources': ';'.join(str(i) for i in range(len(clean_sources))),
        'destinations': str(dest_index),
        'annotations': 'duration',
    }

    try:
        data = _get(profile, 'table', _coords_param(all_points), req_params)
        scale_time = 1.0
    except RoutingError:
        if profile == PROFILE_BIKE:
            try:
                data = _get(PROFILE_CAR, 'table', _coords_param(all_points), req_params)
                scale_time = 1.8
            except RoutingError:
                data = None
        else:
            data = None

        if data is None:
            speed = _FALLBACK_SPEED_MPS.get(profile, _FALLBACK_SPEED_MPS[PROFILE_CAR])
            return [round((_haversine_m(src, dest) * 1.28) / speed, 2) for src in clean_sources]

    durations = data.get('durations') or []
    result: List[Optional[float]] = []
    for i in range(len(clean_sources)):
        row = durations[i] if i < len(durations) else None
        value = row[0] if row else None
        result.append(round(float(value) * scale_time, 2) if value is not None else None)
    return result


# =========================================================================
# /match
# =========================================================================
def match(points: Sequence[LatLng], timestamps: Optional[Sequence[int]] = None,
          profile: str = PROFILE_CAR, radiuses: Optional[Sequence[float]] = None) -> dict:
    """
    Ajusta una traza GPS cruda a la red vial (map matching).

    Args:
        points: Lista de `(lat, lng)` (2 a 500 puntos).
        timestamps: Segundos UNIX por punto (opcional, mejora el ajuste).
        radiuses: Precisión GPS en metros por punto (opcional).

    Returns:
        dict: {
            'matchings': [{'polyline6', 'points', 'distance_m', 'duration_s', 'confidence'}],
            'tracepoints': [(lat, lng) | None, ...],   # punto ajustado por cada punto de entrada
        }
    """
    if not points or len(points) < 2:
        raise RoutingError("Se necesitan al menos 2 puntos para ajustar una traza.", code='too_few_points')
    if len(points) > MAX_MATCH_POINTS:
        raise RoutingError(f"Máximo {MAX_MATCH_POINTS} puntos por consulta.", code='too_many_points')

    clean_points = [_validate_point(p, f'punto {i}') for i, p in enumerate(points)]
    params = {
        'overview': 'full',
        'geometries': 'polyline6',
        'tidy': 'true',
        'gaps': 'split',
    }
    if timestamps is not None:
        if len(timestamps) != len(clean_points):
            raise RoutingError("La cantidad de timestamps no coincide con la de puntos.", code='invalid_timestamps')
        params['timestamps'] = ';'.join(str(int(t)) for t in timestamps)
    if radiuses is not None:
        if len(radiuses) != len(clean_points):
            raise RoutingError("La cantidad de radios no coincide con la de puntos.", code='invalid_radiuses')
        params['radiuses'] = ';'.join(f"{max(1.0, float(r)):.1f}" for r in radiuses)

    try:
        data = _get(profile, 'match', _coords_param(clean_points), params)
    except RoutingError:
        if profile == PROFILE_BIKE:
            try:
                data = _get(PROFILE_CAR, 'match', _coords_param(clean_points), params)
            except RoutingError:
                data = None
        else:
            data = None

        if data is None:
            total_dist = sum(
                _haversine_m(clean_points[i], clean_points[i + 1])
                for i in range(len(clean_points) - 1)
            )
            speed = _FALLBACK_SPEED_MPS.get(profile, _FALLBACK_SPEED_MPS[PROFILE_CAR])
            duration = (
                float(timestamps[-1] - timestamps[0])
                if timestamps and len(timestamps) >= 2 and timestamps[-1] > timestamps[0]
                else round(total_dist / speed, 2)
            )
            return {
                'matchings': [{
                    'polyline6': encode_polyline(clean_points, precision=6),
                    'points': list(clean_points),
                    'distance_m': round(total_dist, 2),
                    'duration_s': round(duration, 2),
                    'confidence': 0.5,
                }],
                'tracepoints': list(clean_points),
            }

    matchings = []
    for m in data.get('matchings') or []:
        encoded = m.get('geometry') or ''
        matchings.append({
            'polyline6': encoded,
            'points': decode_polyline(encoded, precision=6),
            'distance_m': float(m.get('distance') or 0.0),
            'duration_s': float(m.get('duration') or 0.0),
            'confidence': float(m.get('confidence') or 0.0),
        })

    tracepoints = []
    for tp in data.get('tracepoints') or []:
        if tp and tp.get('location'):
            lng, lat = tp['location'][0], tp['location'][1]
            tracepoints.append((float(lat), float(lng)))
        else:
            tracepoints.append(None)

    return {'matchings': matchings, 'tracepoints': tracepoints}


# =========================================================================
# /nearest + Geocodificación Inversa Local (Ahorro de Mapbox Geocoding)
# =========================================================================
# Principales zonas urbanas y ciudades de Venezuela (lat, lng, radio_km, ciudad, estado)
_VE_CITIES_REFERENCE = (
    # Gran Caracas y sub-zonas
    (10.4960, -66.8530, 4.5, "Chacao, Caracas", "Miranda"),
    (10.4800, -66.8560, 5.5, "Baruta, Caracas", "Miranda"),
    (10.4830, -66.8030, 6.0, "Sucre (Petare), Caracas", "Miranda"),
    (10.4360, -66.8220, 5.5, "El Hatillo, Caracas", "Miranda"),
    (10.5000, -66.9170, 9.0, "Libertador, Caracas", "Distrito Capital"),
    (10.4806, -66.9036, 18.0, "Caracas", "Distrito Capital"),
    # Miranda / Vargas / Aragua / Carabobo
    (10.5990, -66.9540, 12.0, "La Guaira / Maiquetía", "La Guaira"),
    (10.3445, -67.0433, 10.0, "Los Teques", "Miranda"),
    (10.4760, -66.6180, 10.0, "Guarenas / Guatire", "Miranda"),
    (10.2353, -66.8586, 12.0, "Charallave / Valles del Tuy", "Miranda"),
    (10.2469, -67.5958, 15.0, "Maracay", "Aragua"),
    (10.2289, -67.4750, 9.0, "Turmero / Cagua", "Aragua"),
    (10.1620, -68.0077, 16.0, "Valencia", "Carabobo"),
    (10.2540, -68.0110, 7.0, "Naguanagua", "Carabobo"),
    (10.2400, -67.9600, 7.0, "San Diego", "Carabobo"),
    (10.4731, -68.0125, 10.0, "Puerto Cabello", "Carabobo"),
    # Occidente y Andes
    (10.0678, -69.3474, 16.0, "Barquisimeto", "Lara"),
    (10.0331, -69.2633, 8.0, "Cabudare", "Lara"),
    (10.6427, -71.6125, 18.0, "Maracaibo", "Zulia"),
    (10.5500, -71.6400, 10.0, "San Francisco", "Zulia"),
    (10.3980, -71.4450, 10.0, "Cabimas", "Zulia"),
    (10.1960, -71.3090, 10.0, "Ciudad Ojeda", "Zulia"),
    (11.6915, -70.1996, 12.0, "Punto Fijo", "Falcón"),
    (11.4045, -69.6734, 10.0, "Coro", "Falcón"),
    (10.3353, -68.7425, 10.0, "San Felipe", "Yaracuy"),
    (9.5597, -69.2017, 12.0, "Acarigua / Araure", "Portuguesa"),
    (9.0419, -69.7422, 10.0, "Guanare", "Portuguesa"),
    (8.6226, -70.2075, 12.0, "Barinas", "Barinas"),
    (8.5983, -71.1444, 12.0, "Mérida", "Mérida"),
    (9.3178, -70.6031, 10.0, "Valera", "Trujillo"),
    (7.7669, -72.2250, 14.0, "San Cristóbal", "Táchira"),
    # Oriente, Llanos y Sur
    (10.1363, -64.6862, 12.0, "Barcelona", "Anzoátegui"),
    (10.1880, -64.6930, 6.0, "Lechería", "Anzoátegui"),
    (10.2142, -64.6328, 10.0, "Puerto La Cruz", "Anzoátegui"),
    (8.8875, -64.2454, 12.0, "El Tigre", "Anzoátegui"),
    (10.4539, -64.1826, 12.0, "Cumaná", "Sucre"),
    (10.9577, -63.8697, 15.0, "Porlamar / Pampatar", "Nueva Esparta"),
    (9.7457, -63.1832, 15.0, "Maturín", "Monagas"),
    (8.2969, -62.7117, 18.0, "Puerto Ordaz / Ciudad Guayana", "Bolívar"),
    (8.1222, -63.5497, 14.0, "Ciudad Bolívar", "Bolívar"),
    (9.9115, -67.3538, 10.0, "San Juan de los Morros", "Guárico"),
    (7.8878, -67.4724, 10.0, "San Fernando de Apure", "Apure"),
)


def _resolve_ve_city_and_state(lat: float, lng: float) -> Tuple[str, str]:
    """Determina la ciudad/municipio y estado venezolano más cercano en memoria (< 0.1 ms)."""
    best_within = None
    best_within_dist = float("inf")
    nearest_any = ("Venezuela", "")
    nearest_any_dist = float("inf")

    pt = (lat, lng)
    for ref_lat, ref_lng, radius_km, city, state in _VE_CITIES_REFERENCE:
        dist_km = _haversine_m(pt, (ref_lat, ref_lng)) / 1000.0
        if dist_km <= radius_km and dist_km < best_within_dist:
            best_within = (city, state)
            best_within_dist = dist_km
        if dist_km < nearest_any_dist:
            nearest_any_dist = dist_km
            nearest_any = (city, state)

    if best_within is not None:
        return best_within
    if nearest_any_dist <= 45.0:
        return nearest_any
    return ("Venezuela", "")


def nearest(point: LatLng, number: int = 3, profile: str = PROFILE_CAR) -> dict:
    """
    Consulta el endpoint `/nearest/v1/{profile}/{lng},{lat}` de `cartmaker-osrm`
    para obtener el segmento vial más cercano y el nombre de la calle o avenida.
    """
    pt = _validate_point(point, 'punto')
    n = max(1, min(10, int(number or 1)))
    try:
        data = _get(profile, 'nearest', _coords_param([pt]), {'number': str(n)})
    except RoutingError:
        if profile == PROFILE_BIKE:
            data = _get(PROFILE_CAR, 'nearest', _coords_param([pt]), {'number': str(n)})
        else:
            raise

    waypoints = data.get('waypoints') or []
    parsed_waypoints = []
    for wp in waypoints:
        loc = wp.get('location') or [pt[1], pt[0]]
        name = (wp.get('name') or '').strip()
        dist = float(wp.get('distance') or 0.0)
        parsed_waypoints.append({
            'name': name,
            'lat': round(float(loc[1]), 6),
            'lng': round(float(loc[0]), 6),
            'distance_m': round(dist, 2),
        })

    primary = parsed_waypoints[0] if parsed_waypoints else {
        'name': '',
        'lat': round(pt[0], 6),
        'lng': round(pt[1], 6),
        'distance_m': 0.0,
    }

    # Si el segmento más cercano es un callejón sin nombre pero a menos de 40 m hay una calle con nombre, la usamos
    street_name = primary['name']
    intersection_name = ''
    for wp in parsed_waypoints:
        if not street_name and wp['name'] and wp['distance_m'] <= 60.0:
            street_name = wp['name']
        elif street_name and wp['name'] and wp['name'].lower() != street_name.lower() and wp['distance_m'] <= 40.0:
            intersection_name = wp['name']
            break

    return {
        'street': street_name,
        'intersection': intersection_name,
        'snapped_lat': primary['lat'],
        'snapped_lng': primary['lng'],
        'distance_to_road_m': primary['distance_m'],
        'waypoints': parsed_waypoints,
    }


def reverse_geocode(point: LatLng, allow_mapbox_fallback: bool = False) -> dict:
    """
    Geocodificación inversa rápida y gratuita basada en `cartmaker-osrm` (`/nearest`) +
    caché por cuadrícula de ~22 metros en Redis (TTL 30 días).

    Permite que Flutter obtenga el nombre de la calle/avenida y ciudad al mover el pin
    sin gastar peticiones de Mapbox Geocoding API.
    """
    from django.core.cache import cache

    pt = _validate_point(point, 'coordenada')
    lat, lng = pt[0], pt[1]

    # Cuadrícula de 0.0002 grados (~22 metros)
    grid_lat = round(round(lat / 0.0002) * 0.0002, 4)
    grid_lng = round(round(lng / 0.0002) * 0.0002, 4)
    cache_key = f"cartmaker:revgeo:v1:{grid_lat:.4f}:{grid_lng:.4f}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    city, state = _resolve_ve_city_and_state(lat, lng)
    street = ''
    intersection = ''
    snapped_lat = round(lat, 6)
    snapped_lng = round(lng, 6)
    distance_to_road_m = 0.0
    source = 'osrm_local'

    try:
        near = nearest((lat, lng), number=3, profile=PROFILE_CAR)
        street = near.get('street') or ''
        intersection = near.get('intersection') or ''
        snapped_lat = near.get('snapped_lat', snapped_lat)
        snapped_lng = near.get('snapped_lng', snapped_lng)
        distance_to_road_m = near.get('distance_to_road_m', 0.0)
    except Exception as exc:
        logger.debug("OSRM nearest no disponible (%s).", exc)
        source = 'local_city_fallback'

    # Fallback opcional a Mapbox Geocoding únicamente si se solicitó explícitamente y OSRM no devolvió calle
    if not street and allow_mapbox_fallback:
        token = getattr(settings, 'MAPBOX_APIKEY', None)
        if token:
            try:
                mb_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{lng:.6f},{lat:.6f}.json"
                resp = requests.get(
                    mb_url,
                    params={'access_token': token, 'language': 'es', 'types': 'address,street,neighborhood,locality,place'},
                    timeout=2.5,
                )
                if resp.status_code == 200:
                    features = (resp.json() or {}).get('features') or []
                    if features:
                        street = (features[0].get('text') or '').strip()
                        source = 'mapbox_cached'
            except Exception:
                pass

    if street and intersection:
        street_display = f"{street} con {intersection}"
    elif street:
        street_display = street
    else:
        street_display = "Vía sin nombre registrado"

    parts = [p for p in (street_display if street else None, city, state) if p]
    formatted_address = ", ".join(parts) if parts else street_display

    result = {
        'lat': round(lat, 6),
        'lng': round(lng, 6),
        'snapped_lat': snapped_lat,
        'snapped_lng': snapped_lng,
        'distance_to_road_m': distance_to_road_m,
        'street': street or street_display,
        'intersection': intersection,
        'street_display': street_display,
        'city': city,
        'state': state,
        'country': 'Venezuela',
        'formatted_address': formatted_address,
        'source': source,
    }

    # Cacheamos por 30 días en Redis cuando proviene de OSRM/Mapbox con calle, o 60s si fue fallback temporal
    ttl_seconds = 2592000 if (source in ('osrm_local', 'mapbox_cached') and street) else 60
    cache.set(cache_key, result, timeout=ttl_seconds)
    return result
