"""
Matemática del protocolo de predicción (Dead Reckoning sobre la ruta).

Modelo compartido entre el servidor (Node, `node_chat_server/index.js`), el teléfono del repartidor
y los mapas del cliente y del comerciante:

- La ruta planificada es una polilínea `points = [(lat, lng), ...]` con distancia acumulada
  `cum_dist[i]` (m) y tiempo esperado acumulado `cum_time[i]` (s) por punto (perfil por tramo de OSRM).
- `T(s)`: función lineal por tramos que da el tiempo esperado para llegar a la distancia `s`.
- Un ancla `(t_a, s_a, k)` permite predecir la distancia recorrida en cualquier instante:

      ŝ(t) = T⁻¹( T(s_a) + k · (t − t_a) )

  y `P̂(t)` es el punto de la ruta a distancia `ŝ(t)`.

Todas las funciones son puras (sin Django ni red) para poder probarlas con SimpleTestCase.
La implementación en JavaScript (Node y Flutter) debe ser idéntica.
"""
import bisect
import math
from typing import List, Optional, Sequence, Tuple

EARTH_RADIUS_M = 6371000.0
MIN_PACE_K = 0.25
MAX_PACE_K = 2.5

LatLng = Tuple[float, float]


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """ Distancia (m) sobre la esfera entre dos coordenadas. """
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def time_at_distance(cum_dist: Sequence[float], cum_time: Sequence[float], s: float) -> float:
    """ T(s): tiempo esperado (s) para llegar a la distancia `s` (m) sobre la ruta. """
    n = min(len(cum_dist), len(cum_time))
    if n == 0:
        return 0.0
    if n == 1:
        return float(cum_time[0])
    s = _clamp(float(s), float(cum_dist[0]), float(cum_dist[n - 1]))
    i = bisect.bisect_right(cum_dist, s, 0, n) - 1
    i = int(_clamp(i, 0, n - 2))
    d0, d1 = float(cum_dist[i]), float(cum_dist[i + 1])
    t0, t1 = float(cum_time[i]), float(cum_time[i + 1])
    if d1 - d0 <= 1e-9:
        return t1 if s >= d1 else t0
    return t0 + (s - d0) / (d1 - d0) * (t1 - t0)


def distance_at_time(cum_dist: Sequence[float], cum_time: Sequence[float], tau: float) -> float:
    """ T⁻¹(τ): distancia (m) sobre la ruta a la que se llega en el tiempo esperado `τ` (s). """
    n = min(len(cum_dist), len(cum_time))
    if n == 0:
        return 0.0
    if n == 1:
        return float(cum_dist[0])
    tau = _clamp(float(tau), float(cum_time[0]), float(cum_time[n - 1]))
    i = bisect.bisect_right(cum_time, tau, 0, n) - 1
    i = int(_clamp(i, 0, n - 2))
    d0, d1 = float(cum_dist[i]), float(cum_dist[i + 1])
    t0, t1 = float(cum_time[i]), float(cum_time[i + 1])
    if t1 - t0 <= 1e-9:
        return d1 if tau >= t1 else d0
    return d0 + (tau - t0) / (t1 - t0) * (d1 - d0)


def predict_distance(cum_dist: Sequence[float], cum_time: Sequence[float], s_a: float, k: float,
                     t_a_ms: int, t_ms: int) -> float:
    """ ŝ(t) = T⁻¹(T(s_a) + k·(t − t_a)). Los tiempos van en milisegundos UNIX. """
    k = _clamp(float(k or 1.0), MIN_PACE_K, MAX_PACE_K)
    elapsed_s = max(0.0, (float(t_ms) - float(t_a_ms)) / 1000.0)
    return distance_at_time(cum_dist, cum_time, time_at_distance(cum_dist, cum_time, s_a) + k * elapsed_s)


def point_at_distance(points: Sequence[LatLng], cum_dist: Sequence[float], s: float) -> Optional[LatLng]:
    """ Punto (lat, lng) de la ruta a distancia `s`, interpolando linealmente dentro del tramo. """
    n = min(len(points), len(cum_dist))
    if n == 0:
        return None
    if n == 1:
        return (float(points[0][0]), float(points[0][1]))
    s = _clamp(float(s), float(cum_dist[0]), float(cum_dist[n - 1]))
    i = bisect.bisect_right(cum_dist, s, 0, n) - 1
    i = int(_clamp(i, 0, n - 2))
    d0, d1 = float(cum_dist[i]), float(cum_dist[i + 1])
    frac = 0.0 if d1 - d0 <= 1e-9 else (s - d0) / (d1 - d0)
    lat = float(points[i][0]) + (float(points[i + 1][0]) - float(points[i][0])) * frac
    lng = float(points[i][1]) + (float(points[i + 1][1]) - float(points[i][1])) * frac
    return (lat, lng)


def heading_at_distance(points: Sequence[LatLng], cum_dist: Sequence[float], s: float) -> float:
    """ Rumbo (grados, 0 = norte) del tramo de la ruta que contiene la distancia `s`. """
    n = min(len(points), len(cum_dist))
    if n < 2:
        return 0.0
    s = _clamp(float(s), float(cum_dist[0]), float(cum_dist[n - 1]))
    i = int(_clamp(bisect.bisect_right(cum_dist, s, 0, n) - 1, 0, n - 2))
    lat1, lng1 = math.radians(points[i][0]), math.radians(points[i][1])
    lat2, lng2 = math.radians(points[i + 1][0]), math.radians(points[i + 1][1])
    y = math.sin(lng2 - lng1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lng2 - lng1)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def project_on_route(points: Sequence[LatLng], cum_dist: Sequence[float], lat: float, lng: float,
                     s_hint: Optional[float] = None) -> dict:
    """
    Proyecta `(lat, lng)` sobre la polilínea de la ruta.

    Usa una proyección equirectangular local (precisa a escala urbana). La distancia recorrida se
    expresa en la escala de `cum_dist` (la de OSRM), para que sea coherente con `cum_time`.
    Si dos tramos quedan a menos de 10 m de diferencia (rutas que se cruzan o regresan), gana el
    más cercano a `s_hint` (la última distancia conocida).

    Returns:
        dict: {'s': float, 'd_perp': float, 'segment': int, 'lat': float, 'lng': float}
    """
    n = min(len(points), len(cum_dist))
    if n == 0:
        return {'s': 0.0, 'd_perp': float('inf'), 'segment': 0, 'lat': lat, 'lng': lng}
    if n == 1:
        return {
            's': float(cum_dist[0]),
            'd_perp': haversine_m(lat, lng, points[0][0], points[0][1]),
            'segment': 0,
            'lat': float(points[0][0]),
            'lng': float(points[0][1]),
        }

    cos_lat = math.cos(math.radians(lat))
    m_per_deg = math.pi * EARTH_RADIUS_M / 180.0

    def to_xy(p_lat: float, p_lng: float) -> Tuple[float, float]:
        return ((p_lng - lng) * cos_lat * m_per_deg, (p_lat - lat) * m_per_deg)

    candidates = []
    prev_xy = to_xy(points[0][0], points[0][1])
    for i in range(n - 1):
        next_xy = to_xy(points[i + 1][0], points[i + 1][1])
        ax, ay = prev_xy
        bx, by = next_xy
        dx, dy = bx - ax, by - ay
        seg_len2 = dx * dx + dy * dy
        if seg_len2 <= 1e-9:
            t = 0.0
        else:
            t = _clamp(-(ax * dx + ay * dy) / seg_len2, 0.0, 1.0)
        px, py = ax + t * dx, ay + t * dy
        dist = math.hypot(px, py)
        s_val = float(cum_dist[i]) + t * (float(cum_dist[i + 1]) - float(cum_dist[i]))
        candidates.append((dist, s_val, i, t))
        prev_xy = next_xy

    best = min(candidates, key=lambda c: c[0])
    if s_hint is not None:
        near = [c for c in candidates if c[0] <= best[0] + 10.0]
        if len(near) > 1:
            best = min(near, key=lambda c: abs(c[1] - float(s_hint)))

    dist, s_val, i, t = best
    p_lat = float(points[i][0]) + (float(points[i + 1][0]) - float(points[i][0])) * t
    p_lng = float(points[i][1]) + (float(points[i + 1][1]) - float(points[i][1])) * t
    return {'s': s_val, 'd_perp': dist, 'segment': i, 'lat': p_lat, 'lng': p_lng}


def eta_remaining_s(cum_dist: Sequence[float], cum_time: Sequence[float], s_a: float, k: float) -> float:
    """ Segundos restantes estimados desde `s_a` hasta el final de la ruta, con el ritmo `k`. """
    if not cum_time:
        return 0.0
    remaining = float(cum_time[-1]) - time_at_distance(cum_dist, cum_time, s_a)
    return max(0.0, remaining / _clamp(float(k or 1.0), MIN_PACE_K, MAX_PACE_K))


def expected_speed_at(cum_dist: Sequence[float], cum_time: Sequence[float], s: float) -> float:
    """ Velocidad esperada (m/s) del tramo que contiene `s` según el perfil de OSRM. """
    n = min(len(cum_dist), len(cum_time))
    if n < 2:
        return 0.0
    s = _clamp(float(s), float(cum_dist[0]), float(cum_dist[n - 1]))
    i = int(_clamp(bisect.bisect_right(cum_dist, s, 0, n) - 1, 0, n - 2))
    dd = float(cum_dist[i + 1]) - float(cum_dist[i])
    dt = float(cum_time[i + 1]) - float(cum_time[i])
    return dd / dt if dt > 1e-6 else 0.0
