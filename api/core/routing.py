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
