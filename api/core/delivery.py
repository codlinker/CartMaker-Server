"""
Motor de Delivery en tiempo real de CartMaker (Fases 2, 3 y 4).

Responsabilidades (Django):
- Turnos de repartidores (`RiderShift`) y su posición caliente en Redis (`rider:{emp_id}:loc`, TTL 120 s).
- Auto-asignación al repartidor libre más cercano de la sucursal (OSRM `/table`), ofertas de 45 s,
  asignación / reasignación manual y desasignación.
- Ciclo de vida: ACCEPTED -> AT_STORE -> PICKED_UP -> ARRIVING -> DELIVERED (PIN) / FAILED / CANCELLED,
  integrado con `Order` vía `ship_order_service` y `complete_order_service`.
- Estado compartido con Node (`dlv:{id}:meta`, `dlv:{id}:live`, `dlv:{id}:trace`, `dlv:roll:{window}`).
- Buffer offline (subida de traza msgpack+gzip) y retransmisión BLE (paquetes de 24 bytes).

La ruta caliente (cada posición del repartidor) NO pasa por Django: la procesa Node con el filtro de
Kalman y la difunde. Django solo maneja la lógica de negocio y avisa a Node por `/internal/delivery-*`.

REDIS: Django y Node comparten la MISMA base (`settings.REALTIME_REDIS_URL`, por defecto
`redis://127.0.0.1:6379/2`) mediante una conexión directa (sin el prefijo `:1:` de django-redis).
Todas las operaciones de Redis son de mejor esfuerzo: si Redis cae, la base de datos sigue siendo
la fuente de la verdad.
"""
import gzip
import hashlib
import hmac
import json
import logging
import math
import secrets
import struct
import time
import uuid
import zlib
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from ..models import (
    CompanyStore,
    DeliveryAssignment,
    DeliveryStatus,
    DeliveryTrace,
    DELIVERY_ACTIVE_STATUSES,
    DELIVERY_MAX_PIN_ATTEMPTS,
    DELIVERY_TERMINAL_STATUSES,
    Employee,
    EmployeeRole,
    EmployeeStatus,
    FixSource,
    NotificationCategory,
    NotificationSection,
    Order,
    OrderStatus,
    RiderShift,
    WithdrawalType,
)
from . import routing
from .dead_reckoning import haversine_m
from .order_services import OrderServiceError, complete_order_service, ship_order_service

logger = logging.getLogger(__name__)

# =========================================================================
# CONSTANTES
# =========================================================================
OFFER_TTL_S = 45
HEARTBEAT_MAX_AGE_S = 120
RIDER_LOC_TTL_S = 120
TIE_WINDOW_S = 60
STORE_GEOFENCE_M = 100
ARRIVING_RADIUS_M = 150
OFFLINE_DELIVERY_RADIUS_M = 150
META_TTL_S = 6 * 3600
LIVE_TTL_S = 6 * 3600
TERMINAL_META_TTL_S = 30 * 60
TRACE_STREAM_MAXLEN = 20000
MAX_TRACE_POINTS = 20000
MAX_TRACE_DECOMPRESSED_BYTES = 16 * 1024 * 1024
MAX_MATCH_POINTS = 500
MAX_BACKFILL_POINTS = 3000
REROUTE_COOLDOWN_S = 15
NO_RIDER_NOTIFY_COOLDOWN_S = 10 * 60
MAX_TABLE_CANDIDATES = 100
BLE_WINDOW_S = 600
BLE_WINDOWS_AHEAD = 12
BLE_PACKET_LEN = 24
BLE_MAX_BATCH = 30
BLE_MAX_AGE_S = 30 * 60
STATUS_FROM_ACCEPTED = (
    DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE, DeliveryStatus.PICKED_UP, DeliveryStatus.ARRIVING,
)
IN_TRANSIT_STATUSES = (DeliveryStatus.PICKED_UP, DeliveryStatus.ARRIVING)

# Flags del rider_fix binario (byte 19)
FIX_FLAG_STOPPED = 0x01
FIX_FLAG_OFF_ROUTE = 0x02
FIX_FLAG_FROM_BUFFER = 0x04
FIX_FLAG_LOW_BATTERY = 0x08


class DeliveryError(Exception):
    """ Error de negocio del delivery. Las vistas lo traducen a `{'error', 'code'}` con `status_code`. """

    def __init__(self, message: str, status_code: int = 400, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class BlePacketError(ValueError):
    """ Paquete BLE inválido (longitud, firma o contenido). """


# =========================================================================
# 1. UTILIDADES PURAS: TIEMPO, COORDENADAS, CRIPTOGRAFÍA Y FORMATOS BINARIOS
# =========================================================================
def now_ms() -> int:
    return int(time.time() * 1000)


def dt_ms(value) -> int:
    return int(value.timestamp() * 1000) if value else 0


def parse_lat_lng(lat, lng, required: bool = True):
    """ Valida y convierte coordenadas. Retorna `(lat, lng)` o None si no son obligatorias y faltan. """
    if (lat is None or lat == '') and (lng is None or lng == ''):
        if required:
            raise DeliveryError("Debes enviar tu ubicación ('lat' y 'lng').", code='location_required')
        return None
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        raise DeliveryError("Coordenadas inválidas.", code='invalid_coordinates')
    if math.isnan(lat_f) or math.isnan(lng_f) or not (-90.0 <= lat_f <= 90.0) or not (-180.0 <= lng_f <= 180.0):
        raise DeliveryError("Coordenadas fuera de rango.", code='invalid_coordinates')
    return lat_f, lng_f


def make_point(lat: float, lng: float) -> Point:
    return Point(float(lng), float(lat), srid=4326)


def _key_bytes(tracking_key: str) -> bytes:
    return bytes.fromhex(tracking_key or '')


def hash_handoff_pin(tracking_key: str, pin: str) -> str:
    """ HMAC-SHA256(tracking_key, pin) en hex. El hash del PIN nunca se manda al teléfono. """
    return hmac.new(_key_bytes(tracking_key), str(pin).strip().encode('utf-8'), hashlib.sha256).hexdigest()


def verify_handoff_pin(tracking_key: str, pin_hash: str, pin) -> bool:
    """ Verifica el PIN en tiempo constante. """
    if not pin_hash or pin is None:
        return False
    candidate = hash_handoff_pin(tracking_key, str(pin).strip())
    return hmac.compare_digest(candidate, str(pin_hash))


def offline_signature_message(delivery_id, pin, t_ms, lat, lng) -> str:
    """ Mensaje firmado por la app del repartidor para la entrega offline. """
    return f"{int(delivery_id)}:{str(pin).strip()}:{int(t_ms)}:{float(lat):.6f}:{float(lng):.6f}"


def compute_offline_signature(tracking_key: str, delivery_id, pin, t_ms, lat, lng) -> str:
    """
    offline_signature = hex(HMAC_SHA256(bytes.fromhex(tracking_key),
                                        f"{delivery_id}:{pin}:{t_ms}:{lat:.6f}:{lng:.6f}"))
    """
    message = offline_signature_message(delivery_id, pin, t_ms, lat, lng).encode('utf-8')
    return hmac.new(_key_bytes(tracking_key), message, hashlib.sha256).hexdigest()


def verify_offline_signature(tracking_key: str, signature, delivery_id, pin, t_ms, lat, lng) -> bool:
    if not signature:
        return False
    try:
        expected = compute_offline_signature(tracking_key, delivery_id, pin, t_ms, lat, lng)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, str(signature).strip().lower())


# ---------- rider_fix binario (20 bytes, little-endian, sección 4.3) ----------
RIDER_FIX_STRUCT = struct.Struct('<IiiHHHBB')


def pack_rider_fix(t_ms: int, lat: float, lng: float, speed_mps: float = 0.0, heading_deg: float = 0.0,
                   accuracy_m: float = 0.0, seq: int = 0, flags: int = 0) -> bytes:
    """
    Empaqueta un rider_fix de 20 bytes:
    t_ms uint32 | lat×1e7 int32 | lng×1e7 int32 | velocidad cm/s uint16 | rumbo×100 uint16 |
    precisión dm uint16 | seq uint8 | flags uint8.
    """
    return RIDER_FIX_STRUCT.pack(
        int(t_ms) & 0xFFFFFFFF,
        int(round(float(lat) * 1e7)),
        int(round(float(lng) * 1e7)),
        min(65535, max(0, int(round(float(speed_mps or 0.0) * 100)))),
        int(round((float(heading_deg or 0.0) % 360.0) * 100)) % 36000,
        min(65535, max(0, int(round(float(accuracy_m or 0.0) * 10)))),
        int(seq) & 0xFF,
        int(flags) & 0xFF,
    )


def unpack_rider_fix(buf: bytes) -> dict:
    if buf is None or len(buf) != RIDER_FIX_STRUCT.size:
        raise ValueError("El rider_fix debe medir exactamente 20 bytes.")
    t_ms, lat_e7, lng_e7, v_cms, hdg_cd, acc_dm, seq, flags = RIDER_FIX_STRUCT.unpack(bytes(buf))
    return {
        't_ms': t_ms,
        'lat': lat_e7 / 1e7,
        'lng': lng_e7 / 1e7,
        'speed_mps': v_cms / 100.0,
        'heading': hdg_cd / 100.0,
        'accuracy_m': acc_dm / 10.0,
        'seq': seq,
        'flags': flags,
    }


# ---------- Paquete BLE de 24 bytes (sección 4.5) ----------
_BLE_PLAIN_STRUCT = struct.Struct('<iiHH')  # 12 bytes


def ble_window(ts_s: Optional[float] = None) -> int:
    """ Ventana de 10 minutos: int(unix_ts // 600). """
    return int((time.time() if ts_s is None else float(ts_s)) // BLE_WINDOW_S)


def ble_rolling_id(tracking_key: str, window: int) -> bytes:
    """ rolling_id = HMAC_SHA256(bytes.fromhex(tracking_key), uint32_le(window))[:4] """
    return hmac.new(_key_bytes(tracking_key), struct.pack('<I', int(window) & 0xFFFFFFFF), hashlib.sha256).digest()[:4]


def _ble_counter_block(rolling_id: bytes, seq: int) -> bytes:
    """ Bloque contador inicial de AES-CTR (16 bytes): rolling_id(4) + uint16_le(seq)(2) + 10 bytes en cero. """
    return bytes(rolling_id) + struct.pack('<H', int(seq) & 0xFFFF) + b'\x00' * 10


def _aes128_ctr(key16: bytes, counter_block: bytes, data: bytes) -> bytes:
    """
    AES-128-CTR (cifrar y descifrar son la misma operación).
    Usa `cryptography`. Si no estuviera instalada, usa un keystream SHA-256 de respaldo
    (NO interoperable con la app: solo para que el servidor no se caiga; se registra una advertencia).
    """
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        logger.warning("Delivery BLE: 'cryptography' no está disponible; usando keystream SHA-256 de respaldo.")
        keystream = b''
        counter = 0
        while len(keystream) < len(data):
            keystream += hashlib.sha256(key16 + counter_block + struct.pack('<I', counter)).digest()
            counter += 1
        return bytes(a ^ b for a, b in zip(data, keystream))
    encryptor = Cipher(algorithms.AES(key16), modes.CTR(counter_block)).encryptor()
    return encryptor.update(data) + encryptor.finalize()


def pack_speed_heading(speed_mps: float, heading_deg: float) -> int:
    """ uint16: 10 bits de velocidad en dm/s (0..102.3 m/s) + 6 bits de rumbo (heading // 6). """
    speed_dm = min(1023, max(0, int(round(float(speed_mps or 0.0) * 10))))
    hdg6 = int((float(heading_deg or 0.0) % 360.0) // 6) & 0x3F
    return speed_dm | (hdg6 << 10)


def unpack_speed_heading(value: int):
    return (value & 0x3FF) / 10.0, float(((value >> 10) & 0x3F) * 6)


def build_ble_packet(tracking_key: str, lat: float, lng: float, speed_mps: float, heading_deg: float,
                     t_rel_s: int, seq: int, window: Optional[int] = None) -> bytes:
    """
    Construye el anuncio BLE de 24 bytes del repartidor:
      [0:4]   rolling_id = HMAC_SHA256(K, uint32_le(window))[:4]
      [4:6]   seq (uint16 LE)
      [6:18]  AES-128-CTR(K[:16], IV = rolling_id + uint16_le(seq) + 0x00*10) de '<iiHH':
              lat_e7, lng_e7, speed_dm|hdg6<<10, t_rel_s (segundos desde assigned_at mod 65536)
      [18:24] tag = HMAC_SHA256(K, packet[0:18])[:6]
    donde K = bytes.fromhex(tracking_key) (32 bytes).
    """
    key = _key_bytes(tracking_key)
    win = ble_window() if window is None else int(window)
    rid = ble_rolling_id(tracking_key, win)
    plain = _BLE_PLAIN_STRUCT.pack(
        int(round(float(lat) * 1e7)),
        int(round(float(lng) * 1e7)),
        pack_speed_heading(speed_mps, heading_deg),
        int(t_rel_s) % 65536,
    )
    cipher = _aes128_ctr(key[:16], _ble_counter_block(rid, seq), plain)
    head = rid + struct.pack('<H', int(seq) & 0xFFFF) + cipher
    tag = hmac.new(key, head, hashlib.sha256).digest()[:6]
    return head + tag


def parse_ble_packet(tracking_key: str, packet: bytes, expected_window: Optional[int] = None) -> dict:
    """ Verifica la firma, (opcionalmente) el rolling_id de la ventana y descifra un paquete BLE de 24 bytes. """
    packet = bytes(packet or b'')
    if len(packet) != BLE_PACKET_LEN:
        raise BlePacketError("El paquete BLE debe medir 24 bytes.")
    key = _key_bytes(tracking_key)
    expected_tag = hmac.new(key, packet[0:18], hashlib.sha256).digest()[:6]
    if not hmac.compare_digest(expected_tag, packet[18:24]):
        raise BlePacketError("Firma BLE inválida.")
    rid = packet[0:4]
    if expected_window is not None and not hmac.compare_digest(rid, ble_rolling_id(tracking_key, expected_window)):
        raise BlePacketError("rolling_id no corresponde a la ventana.")
    seq = struct.unpack('<H', packet[4:6])[0]
    plain = _aes128_ctr(key[:16], _ble_counter_block(rid, seq), packet[6:18])
    lat_e7, lng_e7, speed_hdg, t_rel_s = _BLE_PLAIN_STRUCT.unpack(plain)
    speed_mps, heading = unpack_speed_heading(speed_hdg)
    lat = lat_e7 / 1e7
    lng = lng_e7 / 1e7
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        raise BlePacketError("Coordenadas BLE fuera de rango.")
    return {
        'rolling_id': rid.hex(),
        'seq': seq,
        'lat': lat,
        'lng': lng,
        'speed_mps': speed_mps,
        'heading': heading,
        't_rel_s': t_rel_s,
    }


# ---------- Traza comprimida (DeliveryTrace) ----------
def pack_trace_points(points: List[tuple]) -> bytes:
    """ gzip(msgpack([[t_ms, lat_e7, lng_e7, v_cms, heading_cd, acc_dm, source], ...])) """
    import msgpack
    return gzip.compress(msgpack.packb([list(p) for p in points], use_bin_type=True))


def unpack_trace_points(blob) -> List[tuple]:
    if not blob:
        return []
    import msgpack
    raw = gzip.decompress(bytes(blob))
    data = msgpack.unpackb(raw, raw=False, strict_map_key=False) or []
    return [tuple(int(x) for x in p[:7]) for p in data if isinstance(p, (list, tuple)) and len(p) >= 3]


def _safe_gunzip(raw: bytes) -> bytes:
    """ Descomprime gzip con límite de tamaño (protección contra zip bombs). """
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = decompressor.decompress(raw, MAX_TRACE_DECOMPRESSED_BYTES)
    if decompressor.unconsumed_tail:
        raise DeliveryError("La traza descomprimida es demasiado grande.", status_code=413, code='trace_too_large')
    return out


def normalize_trace_point(p, default_source: int = FixSource.OFFLINE_BUFFER) -> Optional[tuple]:
    """
    Convierte un punto (dict o lista) al formato canónico
    `(t_ms, lat_e7, lng_e7, v_cms, heading_cd, acc_dm, source)`. Retorna None si es inválido.

    Dict: {t_ms, lat, lng, v_cms?|speed_mps?, heading_cd?|heading?, acc_dm?|accuracy_m?, source?}
    Lista: [t_ms, lat, lng, v_cms, heading_cd, acc_dm, source] (lat/lng en grados o ×1e7).
    """
    try:
        if isinstance(p, dict):
            t_ms = int(p.get('t_ms', p.get('t')))
            if 'lat_e7' in p:
                lat = int(p['lat_e7']) / 1e7
                lng = int(p['lng_e7']) / 1e7
            else:
                lat = float(p['lat'])
                lng = float(p['lng'])
            if p.get('v_cms') is not None:
                v_cms = int(p['v_cms'])
            else:
                v_cms = int(round(float(p.get('speed_mps') or 0.0) * 100))
            if p.get('heading_cd') is not None:
                heading_cd = int(p['heading_cd'])
            else:
                heading_cd = int(round(float(p.get('heading') or 0.0) * 100))
            if p.get('acc_dm') is not None:
                acc_dm = int(p['acc_dm'])
            else:
                acc_dm = int(round(float(p.get('accuracy_m') or 0.0) * 10))
            source = int(p.get('source', default_source) if p.get('source') is not None else default_source)
        elif isinstance(p, (list, tuple)) and len(p) >= 3:
            t_ms = int(p[0])
            lat = float(p[1])
            lng = float(p[2])
            if abs(lat) > 90.0 or abs(lng) > 180.0:
                lat = lat / 1e7
                lng = lng / 1e7
            v_cms = int(p[3]) if len(p) > 3 and p[3] is not None else 0
            heading_cd = int(p[4]) if len(p) > 4 and p[4] is not None else 0
            acc_dm = int(p[5]) if len(p) > 5 and p[5] is not None else 0
            source = int(p[6]) if len(p) > 6 and p[6] is not None else int(default_source)
        else:
            return None
    except (TypeError, ValueError, KeyError):
        return None
    if t_ms < 0 or t_ms > 0xFFFFFFFF:
        return None
    if math.isnan(lat) or math.isnan(lng) or not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return None
    if source not in FixSource.values:
        source = int(default_source)
    return (
        t_ms,
        int(round(lat * 1e7)),
        int(round(lng * 1e7)),
        max(0, min(65535, v_cms)),
        max(0, min(35999, heading_cd)),
        max(0, min(65535, acc_dm)),
        source,
    )


def merge_trace_points(*point_lists) -> List[tuple]:
    """ Une listas de puntos canónicos, deduplica por `t_ms` (gana el primero) y ordena. """
    merged = {}
    for plist in point_lists:
        for p in plist or []:
            if p is not None and p[0] not in merged:
                merged[p[0]] = p
    return [merged[k] for k in sorted(merged)]


def trace_max_gap_s(points: List[tuple]) -> float:
    gap = 0.0
    for i in range(1, len(points)):
        gap = max(gap, (points[i][0] - points[i - 1][0]) / 1000.0)
    return round(gap, 3)


# =========================================================================
# 2. REDIS COMPARTIDO CON NODE
# =========================================================================
_realtime_redis = None


def get_realtime_redis():
    """ Cliente Redis directo (sin prefijos) sobre la misma DB que usa node_chat_server. """
    global _realtime_redis
    if _realtime_redis is None:
        try:
            import redis
            _realtime_redis = redis.Redis.from_url(
                getattr(settings, 'REALTIME_REDIS_URL', 'redis://127.0.0.1:6379/2'),
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        except Exception as e:
            logger.warning(f"Delivery: no se pudo crear el cliente Redis en tiempo real: {e}")
            return None
    return _realtime_redis


def key_meta(delivery_id) -> str:
    return f"dlv:{delivery_id}:meta"


def key_live(delivery_id) -> str:
    return f"dlv:{delivery_id}:live"


def key_trace(delivery_id) -> str:
    return f"dlv:{delivery_id}:trace"


def key_roll(window: int) -> str:
    return f"dlv:roll:{window}"


def key_rider_loc(emp_id) -> str:
    return f"rider:{emp_id}:loc"


def key_rider_online(emp_id) -> str:
    return f"rider:{emp_id}:online"


def _rider_loc_set(emp_id, lat: float, lng: float, store_id, battery=None) -> None:
    r = get_realtime_redis()
    if r is None:
        return
    try:
        r.set(key_rider_loc(emp_id), json.dumps({
            'lat': lat, 'lng': lng, 'ts': now_ms(), 'store_id': str(store_id) if store_id else None,
            'battery': battery,
        }), ex=RIDER_LOC_TTL_S)
    except Exception as e:
        logger.warning(f"Delivery: no se pudo guardar rider:{emp_id}:loc: {e}")


def _rider_loc_get(emp_id) -> Optional[dict]:
    r = get_realtime_redis()
    if r is None:
        return None
    try:
        raw = r.get(key_rider_loc(emp_id))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _rider_loc_delete(emp_id) -> None:
    r = get_realtime_redis()
    if r is None:
        return
    try:
        r.delete(key_rider_loc(emp_id))
    except Exception:
        pass


def _rider_is_online(emp_id) -> bool:
    r = get_realtime_redis()
    if r is None:
        return False
    try:
        return bool(r.exists(key_rider_online(emp_id)))
    except Exception:
        return False


def _staff_user_ids_for_store(store) -> List[str]:
    """ Asistentes ACTIVOS asignados a la sucursal (también pueden seguir la entrega como comercio). """
    ids = (
        Employee.objects.filter(
            company_id=store.company_id, status=EmployeeStatus.ACTIVE, role=EmployeeRole.ASSISTANT,
        )
        .filter(Q(employeestoreassignment__store=store) | Q(permissions__allowed_stores=store))
        .values_list('user_id', flat=True)
        .distinct()
    )
    return [str(uid) for uid in ids]


def _merchant_user_ids(delivery) -> List[str]:
    store = delivery.store
    ids = [str(store.company.owner_id)]
    for uid in _staff_user_ids_for_store(store):
        if uid not in ids:
            ids.append(uid)
    return ids


def build_meta_mapping(delivery) -> dict:
    """ Contenido del HASH `dlv:{id}:meta` (todo como string; las listas en JSON). """
    order = delivery.order
    store = delivery.store
    rider = delivery.rider
    points = []
    if delivery.route_polyline6:
        try:
            points = [[round(lat, 6), round(lng, 6)] for lat, lng in routing.decode_polyline(delivery.route_polyline6, 6)]
        except Exception:
            points = []
    merchant_ids = _merchant_user_ids(delivery)
    return {
        'delivery_id': str(delivery.id),
        'order_id': str(delivery.order_id),
        'client_user_id': str(order.client_id),
        'merchant_user_id': str(store.company.owner_id),
        'merchant_user_ids': json.dumps(merchant_ids),
        'rider_emp_id': str(rider.id) if rider else '',
        'rider_user_id': str(rider.user_id) if rider else '',
        'vehicle_type': str(rider.vehicle_type) if rider and rider.vehicle_type is not None else '',
        'store_id': str(store.id),
        'status': str(int(delivery.status)),
        'route_version': str(delivery.route_version),
        'tracking_key': delivery.tracking_key or '',
        'assigned_at_ms': str(dt_ms(delivery.assigned_at)),
        'picked_up_at_ms': str(dt_ms(delivery.picked_up_at)),
        'dest_lat': str(delivery.dest_point.y),
        'dest_lng': str(delivery.dest_point.x),
        'store_lat': str(delivery.origin_point.y),
        'store_lng': str(delivery.origin_point.x),
        'route_polyline6': delivery.route_polyline6 or '',
        'route_points': json.dumps(points),
        'route_cum_dist': json.dumps(delivery.route_cum_dist or []),
        'route_cum_time': json.dumps(delivery.route_cum_time or []),
        'route_distance_m': str(delivery.route_distance_m or 0.0),
        'route_duration_s': str(delivery.route_duration_s or 0.0),
        'eta_at_ms': str(dt_ms(delivery.eta_at)),
        'updated_at_ms': str(now_ms()),
    }


def sync_delivery_meta(delivery) -> Optional[dict]:
    """ Escribe `dlv:{id}:meta` en Redis (TTL 6 h; 30 min si la entrega terminó). """
    try:
        mapping = build_meta_mapping(delivery)
    except Exception as e:
        logger.error(f"Delivery #{delivery.id}: error armando meta: {e}")
        return None
    r = get_realtime_redis()
    if r is None:
        return mapping
    ttl = TERMINAL_META_TTL_S if int(delivery.status) in DELIVERY_TERMINAL_STATUSES else META_TTL_S
    try:
        pipe = r.pipeline()
        pipe.delete(key_meta(delivery.id))
        pipe.hset(key_meta(delivery.id), mapping=mapping)
        pipe.expire(key_meta(delivery.id), ttl)
        pipe.execute()
    except Exception as e:
        logger.warning(f"Delivery #{delivery.id}: no se pudo escribir meta en Redis: {e}")
    return mapping


def reset_live_anchor(delivery, mode: str = 'route', lat: Optional[float] = None, lng: Optional[float] = None) -> dict:
    """
    Reinicia el ancla en `dlv:{id}:live`: t_a = ahora, s_a = 0, k = 1.0, sigma_a = 10 m.
    Node continúa el filtro de Kalman a partir de este estado.
    """
    t = now_ms()
    if lat is None or lng is None:
        lat = float(delivery.origin_point.y)
        lng = float(delivery.origin_point.x)
    anchor = {
        'delivery_id': str(delivery.id),
        't_a': str(t),
        's_a': '0',
        'k': '1.0',
        'sigma_a': '10',
        'sigma_rate': '1.0',
        'v': '0',
        'p00': '100',
        'p01': '0',
        'p11': '4',
        'state_t_ms': str(t),
        'route_version': str(delivery.route_version),
        'mode': mode,
        'lat': str(lat),
        'lng': str(lng),
        'heading': '0',
        'speed_mps': '0',
        'eta_remaining_s': str(round(float(delivery.route_duration_s or 0.0), 1)),
        'off_route_count': '0',
        'arriving_sent': '0',
        'source': 'server',
    }
    r = get_realtime_redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.delete(key_live(delivery.id))
            pipe.hset(key_live(delivery.id), mapping=anchor)
            pipe.expire(key_live(delivery.id), LIVE_TTL_S)
            pipe.execute()
        except Exception as e:
            logger.warning(f"Delivery #{delivery.id}: no se pudo reiniciar el ancla: {e}")
    return anchor_payload_from_live(anchor)


def read_live_anchor(delivery_id) -> Optional[dict]:
    r = get_realtime_redis()
    if r is None:
        return None
    try:
        live = r.hgetall(key_live(delivery_id))
    except Exception:
        return None
    return anchor_payload_from_live(live) if live else None


def anchor_payload_from_live(live: dict) -> dict:
    """ Formato público del evento `delivery_anchor` a partir del HASH `dlv:{id}:live`. """
    def f(name, default=0.0):
        try:
            return float(live.get(name, default))
        except (TypeError, ValueError):
            return default
    return {
        'delivery_id': int(f('delivery_id', 0)) if live.get('delivery_id') else None,
        't_a': int(f('t_a', 0)),
        's_a': f('s_a'),
        'k': f('k', 1.0),
        'sigma_a': f('sigma_a', 10.0),
        'sigma_rate': f('sigma_rate', 1.0),
        'route_version': int(f('route_version', 1)),
        'mode': live.get('mode') or 'route',
        'lat': f('lat'),
        'lng': f('lng'),
        'heading': f('heading'),
        'speed_mps': f('speed_mps'),
        'eta_remaining_s': f('eta_remaining_s'),
        'source': live.get('source') or 'server',
    }


def register_rolling_ids(delivery) -> None:
    """ Registra `rolling_id -> delivery_id` en `dlv:roll:{window}` (ventana actual + 12 siguientes, 2 h). """
    if not delivery.tracking_key:
        return
    r = get_realtime_redis()
    if r is None:
        return
    current = ble_window()
    try:
        pipe = r.pipeline()
        for w in range(current, current + BLE_WINDOWS_AHEAD + 1):
            rid = ble_rolling_id(delivery.tracking_key, w).hex()
            pipe.hset(key_roll(w), rid, str(delivery.id))
            pipe.expireat(key_roll(w), (w + 3) * BLE_WINDOW_S)
        pipe.execute()
    except Exception as e:
        logger.warning(f"Delivery #{delivery.id}: no se pudieron registrar los rolling_id BLE: {e}")


def unregister_rolling_ids(delivery) -> None:
    if not delivery.tracking_key:
        return
    r = get_realtime_redis()
    if r is None:
        return
    start_ts = (delivery.accepted_at or delivery.created_at or timezone.now()).timestamp()
    first = ble_window(start_ts) - 1
    last = ble_window() + BLE_WINDOWS_AHEAD + 1
    try:
        pipe = r.pipeline()
        for w in range(first, min(last, first + 200) + 1):
            pipe.hdel(key_roll(w), ble_rolling_id(delivery.tracking_key, w).hex())
        pipe.execute()
    except Exception:
        pass


def cleanup_realtime_keys(delivery) -> None:
    """ Al terminar la entrega: borra live/trace y rolling_ids; la meta queda 30 min para clientes rezagados. """
    unregister_rolling_ids(delivery)
    r = get_realtime_redis()
    if r is None:
        return
    try:
        r.delete(key_live(delivery.id), key_trace(delivery.id))
        r.expire(key_meta(delivery.id), TERMINAL_META_TTL_S)
    except Exception:
        pass


# =========================================================================
# 3. AVISOS A NODE Y NOTIFICACIONES
# =========================================================================
def _post_node(path: str, payload: dict) -> None:
    """ POST a `INTERNAL_WEBSOCKETS_URL + internal/<path>`. Nunca lanza errores. """
    try:
        requests.post(
            f"{settings.INTERNAL_WEBSOCKETS_URL}internal/{path}",
            json=payload,
            headers={'X-Microservice-Token': settings.SECRET_KEY},
            timeout=2,
        )
    except Exception as e:
        logger.warning(f"Delivery: no se pudo avisar a Node ({path}): {e}")


def _post_node_on_commit(path: str, payload: dict) -> None:
    transaction.on_commit(lambda: _post_node(path, payload))


def build_status_payload(delivery, extra: Optional[dict] = None) -> dict:
    rider = delivery.rider
    payload = {
        'delivery_id': delivery.id,
        'order_id': delivery.order_id,
        'store_id': str(delivery.store_id),
        'status': int(delivery.status),
        'status_label': str(DeliveryStatus(int(delivery.status)).label),
        'eta_at_ms': dt_ms(delivery.eta_at) or None,
        'route_version': delivery.route_version,
        'client_user_id': str(delivery.order.client_id),
        'merchant_user_ids': _merchant_user_ids(delivery),
        'rider_user_id': str(rider.user_id) if rider else None,
        'rider_emp_id': rider.id if rider else None,
        'updated_at_ms': now_ms(),
    }
    if extra:
        payload.update(extra)
    return payload


def build_route_payload(delivery) -> dict:
    return {
        'delivery_id': delivery.id,
        'status': int(delivery.status),
        'route_version': delivery.route_version,
        'polyline6': delivery.route_polyline6 or '',
        'cum_dist': delivery.route_cum_dist or [],
        'cum_time': delivery.route_cum_time or [],
        'distance_m': delivery.route_distance_m,
        'duration_s': delivery.route_duration_s,
        'eta_at_ms': dt_ms(delivery.eta_at) or None,
    }


def _after_commit_status(delivery, extra: Optional[dict] = None, sync_meta: bool = True,
                         include_route: bool = False) -> None:
    """ Tras el commit: actualiza la meta en Redis y avisa a Node del nuevo estado (y la ruta, si aplica). """
    payload = build_status_payload(delivery, extra)
    route_payload = build_route_payload(delivery) if include_route else None
    delivery_ref = delivery

    def _run():
        if sync_meta:
            sync_delivery_meta(delivery_ref)
        _post_node('delivery-status', payload)
        if route_payload is not None:
            _post_node('delivery-route', route_payload)

    transaction.on_commit(_run)


def _notify_on_commit(user_id, title: str, body: str, event_type: str, category: int, section: int,
                      extra: Optional[dict] = None) -> None:
    if not user_id:
        return

    def _run():
        try:
            from .firebase_admin import NotificationManager
            NotificationManager.notify_workforce_event(
                user_id=user_id,
                title=title,
                body=body,
                event_type=event_type,
                category=category,
                section=section,
                extra_data=extra or {},
            )
        except Exception as e:
            logger.warning(f"Delivery: no se pudo notificar a {user_id}: {e}")

    transaction.on_commit(_run)


def _notify_merchants_on_commit(delivery, title: str, body: str, event_type: str, extra: Optional[dict] = None) -> None:
    for uid in _merchant_user_ids(delivery):
        _notify_on_commit(
            uid, title, body, event_type,
            NotificationCategory.DELIVERY_STATUS, NotificationSection.MERCHANT_ORDERS,
            dict({'delivery_id': delivery.id, 'order_id': delivery.order_id, 'is_merchant_receiver': True}, **(extra or {})),
        )


def _notify_client_on_commit(delivery, title: str, body: str, event_type: str, extra: Optional[dict] = None) -> None:
    _notify_on_commit(
        delivery.order.client_id, title, body, event_type,
        NotificationCategory.DELIVERY_STATUS, NotificationSection.ORDERS,
        dict({'delivery_id': delivery.id, 'order_id': delivery.order_id, 'is_merchant_receiver': False}, **(extra or {})),
    )


def _notify_rider_on_commit(rider, title: str, body: str, event_type: str, delivery, extra: Optional[dict] = None,
                            category: int = NotificationCategory.DELIVERY_STATUS) -> None:
    if rider is None:
        return
    _notify_on_commit(
        rider.user_id, title, body, event_type, category, NotificationSection.HOME,
        dict({'delivery_id': delivery.id, 'order_id': delivery.order_id, 'employee_id': rider.id}, **(extra or {})),
    )


# =========================================================================
# 4. PERMISOS Y BÚSQUEDAS
# =========================================================================
def employee_assigned_to_store(employee, store) -> bool:
    return Employee.objects.filter(pk=employee.pk, company_id=store.company_id).filter(
        Q(employeestoreassignment__store=store) | Q(permissions__allowed_stores=store)
    ).exists()


def user_can_manage_store_deliveries(user, store) -> bool:
    """ Dueño de la compañía o asistente ACTIVO asignado a la sucursal. """
    if not user or not getattr(user, 'is_authenticated', False) or store is None:
        return False
    if store.company.owner_id == user.id:
        return True
    return Employee.objects.filter(
        user=user, company_id=store.company_id, status=EmployeeStatus.ACTIVE, role=EmployeeRole.ASSISTANT,
    ).filter(
        Q(employeestoreassignment__store=store) | Q(permissions__allowed_stores=store)
    ).exists()


def get_rider_employee(employee_id) -> Employee:
    employee = Employee.objects.select_related('user', 'company').filter(pk=employee_id).first()
    if employee is None or employee.status != EmployeeStatus.ACTIVE or employee.role != EmployeeRole.DELIVERY:
        raise DeliveryError("Tu acceso como repartidor no está activo.", status_code=403, code='rider_not_active')
    return employee


def _delivery_qs():
    return DeliveryAssignment.objects.select_related(
        'order', 'order__client', 'store', 'store__company', 'rider', 'rider__user',
    )


def get_delivery(delivery_id) -> DeliveryAssignment:
    try:
        pk = int(delivery_id)
    except (TypeError, ValueError):
        raise DeliveryError("Identificador de entrega inválido.", code='invalid_delivery_id')
    delivery = _delivery_qs().filter(pk=pk).first()
    if delivery is None:
        raise DeliveryError("La entrega no existe.", status_code=404, code='delivery_not_found')
    return delivery


def _lock_delivery(delivery_id) -> DeliveryAssignment:
    """ Bloquea la fila de la entrega (debe llamarse dentro de transaction.atomic()). """
    delivery = _delivery_qs().select_for_update(of=('self',)).filter(pk=delivery_id).first()
    if delivery is None:
        raise DeliveryError("La entrega no existe.", status_code=404, code='delivery_not_found')
    return delivery


def _lock_order(order_id) -> Order:
    return Order.objects.select_for_update(of=('self',)).select_related('store__company').get(pk=order_id)


def _active_delivery_for_rider(employee) -> Optional[DeliveryAssignment]:
    return _delivery_qs().filter(rider=employee, status__in=DELIVERY_ACTIVE_STATUSES).order_by('-created_at').first()


def _require_rider_of(delivery, employee) -> None:
    if delivery.rider_id is None or delivery.rider_id != employee.id:
        raise DeliveryError("Esta entrega no está asignada a ti.", status_code=403, code='not_assigned_rider')


def resolve_viewer_role(user, delivery, ctx: str, emp_id=None) -> Optional[str]:
    """ 'rider' | 'client' | 'merchant' | None, según el usuario y el contexto de su token. """
    if ctx == 'worker':
        if emp_id is not None and delivery.rider_id is not None and str(delivery.rider_id) == str(emp_id) \
                and delivery.rider.user_id == user.id:
            return 'rider'
        # Asistentes del comercio operando con su token de trabajador ven la entrega como el comercio
        if user_can_manage_store_deliveries(user, delivery.store):
            return 'merchant'
        return None
    if delivery.order.client_id == user.id:
        return 'client'
    if user_can_manage_store_deliveries(user, delivery.store):
        return 'merchant'
    return None


def parse_store_uuid(store_id):
    """ Valida que `store_id` sea un UUID (CompanyStore.id); evita 500 por ValidationError de Django. """
    if store_id in (None, '', 'null'):
        return None
    try:
        return uuid.UUID(str(store_id).strip())
    except (TypeError, ValueError, AttributeError):
        raise DeliveryError("Identificador de sucursal inválido.", code='invalid_store_id')


# =========================================================================
# 5. TURNOS
# =========================================================================
def _active_shift(employee) -> Optional[RiderShift]:
    return (
        RiderShift.objects.select_related('store')
        .filter(employee=employee, is_active=True)
        .order_by('-started_at')
        .first()
    )


def _parse_battery(battery) -> Optional[int]:
    if battery is None or battery == '':
        return None
    try:
        value = int(float(battery))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, value))


def start_shift(employee, store_id, lat, lng, battery=None) -> dict:
    """ Abre (o reemplaza) el turno del repartidor en una sucursal asignada. """
    lat_f, lng_f = parse_lat_lng(lat, lng, required=True)
    battery_val = _parse_battery(battery)
    store_uuid = parse_store_uuid(store_id)
    store = CompanyStore.objects.select_related('company').filter(pk=store_uuid, company_id=employee.company_id).first() \
        if store_uuid else None
    if store is None:
        raise DeliveryError("La sucursal no existe o no pertenece a tu comercio.", status_code=404, code='store_not_found')
    if not store.is_active:
        raise DeliveryError("La sucursal está inactiva.", code='store_inactive')
    if not employee_assigned_to_store(employee, store):
        raise DeliveryError("No estás asignado a esta sucursal.", status_code=403, code='store_not_assigned')

    now = timezone.now()
    with transaction.atomic():
        # Serializa aperturas concurrentes de turno del mismo repartidor (evita dos turnos activos)
        Employee.objects.select_for_update().filter(pk=employee.pk).first()
        RiderShift.objects.filter(employee=employee, is_active=True).update(is_active=False, ended_at=now)
        shift = RiderShift.objects.create(
            employee=employee,
            store=store,
            last_point=make_point(lat_f, lng_f),
            last_heartbeat_at=now,
            battery_level=battery_val,
        )
        Employee.objects.filter(pk=employee.pk).update(last_seen_at=now)

    _rider_loc_set(employee.id, lat_f, lng_f, store.id, battery_val)
    if _active_delivery_for_rider(employee) is None:
        try_assign_pending_deliveries_for_store(store)
    return get_shift_status(employee)


def heartbeat_shift(employee, lat, lng, battery=None) -> dict:
    """ Latido de ubicación cada 60 s durante el turno (va a Redis, TTL 120 s). """
    lat_f, lng_f = parse_lat_lng(lat, lng, required=True)
    battery_val = _parse_battery(battery)
    shift = _active_shift(employee)
    if shift is None:
        raise DeliveryError("No tienes un turno abierto.", status_code=409, code='no_active_shift')
    now = timezone.now()
    update = {'last_point': make_point(lat_f, lng_f), 'last_heartbeat_at': now}
    if battery_val is not None:
        update['battery_level'] = battery_val
    RiderShift.objects.filter(pk=shift.pk).update(**update)
    Employee.objects.filter(pk=employee.pk).update(last_seen_at=now)
    _rider_loc_set(employee.id, lat_f, lng_f, shift.store_id, battery_val)

    active = _active_delivery_for_rider(employee)
    if active is None and DeliveryAssignment.objects.filter(
        store_id=shift.store_id, status=DeliveryStatus.PENDING_RIDER
    ).exists():
        try_assign_pending_deliveries_for_store(shift.store)
        active = _active_delivery_for_rider(employee)
    return {
        'shift_id': shift.id,
        'server_time_ms': now_ms(),
        'active_delivery_id': active.id if active else None,
        'active_delivery_status': int(active.status) if active else None,
    }


def end_shift(employee) -> dict:
    """ Cierra el turno. No se permite con una entrega en curso; una oferta pendiente se rechaza sola. """
    active = _active_delivery_for_rider(employee)
    if active is not None and int(active.status) in STATUS_FROM_ACCEPTED:
        raise DeliveryError(
            "No puedes cerrar el turno con una entrega en curso.", status_code=409, code='delivery_in_progress',
        )
    if active is not None and int(active.status) == DeliveryStatus.ASSIGNED:
        try:
            decline_delivery(employee, active.id, reason='shift_ended')
        except DeliveryError:
            pass
    now = timezone.now()
    closed = RiderShift.objects.filter(employee=employee, is_active=True).update(is_active=False, ended_at=now)
    _rider_loc_delete(employee.id)
    return {'closed_shifts': closed, 'shift': None, 'server_time_ms': now_ms()}


def get_shift_status(employee) -> dict:
    shift = _active_shift(employee)
    active = _active_delivery_for_rider(employee)
    return {
        'shift': shift.get_json() if shift else None,
        'active_delivery': active.get_json(viewer_role='rider') if active else None,
        'server_time_ms': now_ms(),
        'heartbeat_interval_s': 60,
    }


# =========================================================================
# 6. AUTO-ASIGNACIÓN
# =========================================================================
def _candidate_riders(delivery) -> List[dict]:
    """
    Candidatos: role=DELIVERY, status=ACTIVE, asignados a la sucursal, con turno abierto en ella,
    latido de menos de 120 s, sin entrega activa y que no hayan rechazado esta oferta.
    """
    store = delivery.store
    cutoff = timezone.now() - timedelta(seconds=HEARTBEAT_MAX_AGE_S)
    declined = set()
    for raw in delivery.declined_rider_ids or []:
        try:
            declined.add(int(raw))
        except (TypeError, ValueError):
            continue
    busy_ids = set(
        DeliveryAssignment.objects.filter(status__in=DELIVERY_ACTIVE_STATUSES, rider__isnull=False)
        .values_list('rider_id', flat=True)
    )
    assigned_ids = set(
        Employee.objects.filter(company_id=store.company_id)
        .filter(Q(employeestoreassignment__store=store) | Q(permissions__allowed_stores=store))
        .values_list('id', flat=True)
    )
    shifts = (
        RiderShift.objects.select_related('employee', 'employee__user')
        .filter(
            store=store,
            is_active=True,
            last_heartbeat_at__gte=cutoff,
            employee__status=EmployeeStatus.ACTIVE,
            employee__role=EmployeeRole.DELIVERY,
            employee__company_id=store.company_id,
        )
        .order_by('-last_heartbeat_at')
    )
    client_id = delivery.order.client_id
    seen = set()
    candidates = []
    for shift in shifts:
        emp = shift.employee
        if emp.id in seen or emp.id in busy_ids or emp.id in declined or emp.id not in assigned_ids:
            continue
        if emp.user_id == client_id or emp.user_id == store.company.owner_id:
            continue
        seen.add(emp.id)
        loc = _rider_loc_get(emp.id)
        if loc and loc.get('lat') is not None and (not loc.get('store_id') or str(loc.get('store_id')) == str(store.id)):
            lat, lng = float(loc['lat']), float(loc['lng'])
        elif shift.last_point is not None:
            lat, lng = float(shift.last_point.y), float(shift.last_point.x)
        else:
            continue
        candidates.append({'employee': emp, 'lat': lat, 'lng': lng, 'shift': shift})
    return candidates


def rank_candidates(candidates: List[dict], durations: List[Optional[float]], delivered_today: dict) -> List[dict]:
    """
    Ordena por tiempo real por calle hasta la sucursal. Entre los que quedan a menos de 60 s del mejor,
    gana el que hizo menos entregas hoy (reparto justo del trabajo). Sin ruta (None) van al final.
    """
    enriched = []
    for cand, dur in zip(candidates, durations):
        enriched.append(dict(cand, duration_s=(float(dur) if dur is not None else math.inf),
                             delivered_today=int(delivered_today.get(cand['employee'].id, 0))))
    if not enriched:
        return []
    enriched.sort(key=lambda c: c['duration_s'])
    best = enriched[0]['duration_s']
    if math.isinf(best):
        return sorted(enriched, key=lambda c: c['delivered_today'])
    tie_group = [c for c in enriched if c['duration_s'] - best < TIE_WINDOW_S]
    rest = [c for c in enriched if c['duration_s'] - best >= TIE_WINDOW_S]
    tie_group.sort(key=lambda c: (c['delivered_today'], c['duration_s']))
    return tie_group + rest


def _ordered_candidates(delivery) -> List[dict]:
    candidates = _candidate_riders(delivery)
    if not candidates:
        return []
    store_lat, store_lng = float(delivery.origin_point.y), float(delivery.origin_point.x)
    if len(candidates) > MAX_TABLE_CANDIDATES:
        candidates.sort(key=lambda c: haversine_m(c['lat'], c['lng'], store_lat, store_lng))
        candidates = candidates[:MAX_TABLE_CANDIDATES]
    try:
        durations = routing.table([(c['lat'], c['lng']) for c in candidates], (store_lat, store_lng), profile='car')
    except Exception as e:
        logger.warning(f"Delivery #{delivery.id}: /table falló, se usa distancia estimada: {e}")
        durations = [haversine_m(c['lat'], c['lng'], store_lat, store_lng) * 1.28 / 8.0 for c in candidates]
    today_start = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    delivered_today = dict(
        DeliveryAssignment.objects.filter(
            rider_id__in=[c['employee'].id for c in candidates],
            status=DeliveryStatus.DELIVERED,
            delivered_at__gte=today_start,
        ).values('rider_id').annotate(n=Count('id')).values_list('rider_id', 'n')
    )
    return rank_candidates(candidates, durations, delivered_today)


def _offer_payload(delivery, eta_to_store_s: Optional[float] = None) -> dict:
    origin = delivery.origin_point
    dest = delivery.dest_point
    return {
        'delivery_id': delivery.id,
        'order_id': delivery.order_id,
        'store_id': str(delivery.store_id),
        'store_name': delivery.store.name,
        'company_name': delivery.store.company.name,
        'rider_user_id': str(delivery.rider.user_id) if delivery.rider else None,
        'rider_emp_id': delivery.rider_id,
        'offer_expires_at_ms': dt_ms(delivery.offer_expires_at) or None,
        'is_auto_assigned': delivery.is_auto_assigned,
        'origin': {'lat': float(origin.y), 'lng': float(origin.x)},
        # Privacidad: antes de aceptar, el repartidor solo ve la zona (~1 km) del cliente
        'destination_zone': {'lat': round(float(dest.y), 2), 'lng': round(float(dest.x), 2), 'approx_radius_m': 1000},
        'estimated_distance_m': round(haversine_m(origin.y, origin.x, dest.y, dest.x) * 1.28),
        'eta_to_store_s': round(eta_to_store_s, 1) if eta_to_store_s is not None and not math.isinf(eta_to_store_s) else None,
    }


def _announce_offer_on_commit(delivery, eta_to_store_s: Optional[float] = None) -> None:
    payload = _offer_payload(delivery, eta_to_store_s)
    _notify_rider_on_commit(
        delivery.rider,
        "Nueva entrega disponible",
        f"{delivery.store.company.name} tiene un pedido para ti. Tienes {OFFER_TTL_S} s para aceptarlo.",
        'delivery_offer',
        delivery,
        extra={'offer_expires_at_ms': payload['offer_expires_at_ms']},
        category=NotificationCategory.DELIVERY_ASSIGNMENT,
    )
    delivery_ref = delivery

    def _run():
        sync_delivery_meta(delivery_ref)
        _post_node('delivery-offer', payload)

    transaction.on_commit(_run)
    _after_commit_status(delivery, sync_meta=False)


def _notify_no_riders(delivery) -> None:
    """ Avisa al comercio que no hay repartidores (con enfriamiento de 10 min por entrega). """
    r = get_realtime_redis()
    if r is not None:
        try:
            if not r.set(f"dlv:{delivery.id}:no_rider_notified", '1', nx=True, ex=NO_RIDER_NOTIFY_COOLDOWN_S):
                return
        except Exception:
            pass
    _notify_merchants_on_commit(
        delivery,
        "No hay repartidores disponibles",
        f"No hay repartidores disponibles en este momento para la orden N° {delivery.order_id}; "
        f"seguiremos buscando automáticamente.",
        'delivery_no_riders',
    )


def auto_assign_delivery(delivery_id) -> Optional[DeliveryAssignment]:
    """
    Ofrece la entrega al mejor candidato (OSRM /table + desempate justo). Si dos órdenes compiten por el
    mismo repartidor, la segunda choca con `one_active_delivery_per_rider` y pasa al siguiente.
    """
    delivery = _delivery_qs().filter(pk=delivery_id).first()
    if delivery is None or int(delivery.status) != DeliveryStatus.PENDING_RIDER:
        return delivery
    if delivery.order.status not in (OrderStatus.WAITING, OrderStatus.DELIVERY_SENT):
        return delivery

    ordered = _ordered_candidates(delivery)
    for cand in ordered:
        employee = cand['employee']
        try:
            with transaction.atomic():
                locked = _lock_delivery(delivery.id)
                if int(locked.status) != DeliveryStatus.PENDING_RIDER:
                    return locked
                if employee.id in {int(x) for x in (locked.declined_rider_ids or []) if str(x).isdigit()}:
                    continue
                now = timezone.now()
                locked.rider = employee
                locked.status = DeliveryStatus.ASSIGNED
                locked.assigned_at = now
                locked.offer_expires_at = now + timedelta(seconds=OFFER_TTL_S)
                locked.is_auto_assigned = True
                locked.assigned_by = None
                locked.save(update_fields=[
                    'rider', 'status', 'assigned_at', 'offer_expires_at', 'is_auto_assigned', 'assigned_by',
                ])
                _announce_offer_on_commit(locked, cand.get('duration_s'))
            return locked
        except IntegrityError:
            logger.info(f"Delivery #{delivery.id}: el repartidor {employee.id} ya tomó otra entrega; siguiente candidato.")
            continue

    with transaction.atomic():
        _notify_no_riders(delivery)
    return delivery


def safe_auto_assign(delivery_id) -> None:
    try:
        auto_assign_delivery(delivery_id)
    except Exception as e:
        logger.exception(f"Delivery #{delivery_id}: error en auto-asignación: {e}")


def try_assign_pending_deliveries_for_store(store) -> int:
    """ Reintenta asignar las entregas PENDING_RIDER de la sucursal (al liberarse o iniciar turno un repartidor). """
    store_id = store.id if hasattr(store, 'id') else store
    pending_ids = list(
        DeliveryAssignment.objects.filter(store_id=store_id, status=DeliveryStatus.PENDING_RIDER)
        .order_by('created_at').values_list('id', flat=True)[:20]
    )
    assigned = 0
    for pk in pending_ids:
        try:
            result = auto_assign_delivery(pk)
            if result is not None and int(result.status) == DeliveryStatus.ASSIGNED:
                assigned += 1
        except Exception as e:
            logger.exception(f"Delivery #{pk}: error reintentando asignación: {e}")
    return assigned


def _schedule_auto_assign(delivery_id) -> None:
    transaction.on_commit(lambda: safe_auto_assign(delivery_id))


def _schedule_store_retry(store_id) -> None:
    transaction.on_commit(lambda: _safe_store_retry(store_id))


def _safe_store_retry(store_id) -> None:
    try:
        try_assign_pending_deliveries_for_store(store_id)
    except Exception as e:
        logger.exception(f"Delivery: error reintentando asignaciones de la sucursal {store_id}: {e}")


def create_or_assign_delivery_for_order(order, auto_assign: bool = True) -> Optional[DeliveryAssignment]:
    """
    Crea la entrega de una orden con delivery (congelando origen y destino) y dispara la auto-asignación.
    Retorna None si la orden no es de delivery o le faltan ubicaciones.
    """
    try:
        if int(order.withdrawal_type) != WithdrawalType.DELIVERY:
            return None
    except (TypeError, ValueError):
        return None

    existing = _delivery_qs().filter(order_id=order.id).first()
    if existing is not None:
        return existing

    order = Order.objects.select_related('store__company', 'store__location', 'client_location').get(pk=order.pk)
    store_location = getattr(order.store, 'location', None)
    client_location = order.client_location
    if store_location is None or store_location.coordinates is None or client_location is None:
        logger.warning(f"Orden {order.id}: sin ubicación de tienda o de cliente; no se crea la entrega.")
        return None

    tracking_key = secrets.token_hex(32)
    pin = f"{secrets.randbelow(10000):04d}"
    address_parts = [p for p in [(client_location.name or '').strip(), (client_location.description or '').strip()] if p]
    try:
        with transaction.atomic():
            delivery = DeliveryAssignment.objects.create(
                order=order,
                store=order.store,
                status=DeliveryStatus.PENDING_RIDER,
                origin_point=make_point(store_location.coordinates.y, store_location.coordinates.x),
                dest_point=make_point(client_location.coordinates.y, client_location.coordinates.x),
                dest_address_snapshot=' — '.join(address_parts),
                tracking_key=tracking_key,
                handoff_pin=pin,
                handoff_pin_hash=hash_handoff_pin(tracking_key, pin),
            )
    except IntegrityError:
        return _delivery_qs().filter(order_id=order.id).first()

    delivery = get_delivery(delivery.id)
    sync_delivery_meta(delivery)
    if auto_assign:
        safe_auto_assign(delivery.id)
        delivery = get_delivery(delivery.id)
    return delivery


def _resolve_order_delivery_for_manager(actor_user, order_id) -> DeliveryAssignment:
    try:
        pk = int(str(order_id).strip().lstrip('#'))
    except (TypeError, ValueError):
        raise DeliveryError("Identificador de orden inválido.", code='invalid_order_id')
    order = Order.objects.select_related('store__company').filter(pk=pk).first()
    if order is None:
        raise DeliveryError("La orden no existe.", status_code=404, code='order_not_found')
    if not user_can_manage_store_deliveries(actor_user, order.store):
        raise DeliveryError("No tienes permisos sobre esta orden.", status_code=403, code='not_store_manager')
    if int(order.withdrawal_type) != WithdrawalType.DELIVERY:
        raise DeliveryError("Esta orden no es de delivery.", code='not_delivery_order')
    if order.status not in (OrderStatus.WAITING, OrderStatus.DELIVERY_SENT):
        raise DeliveryError("La orden ya no admite cambios de repartidor.", status_code=409, code='order_not_assignable')
    delivery = _delivery_qs().filter(order_id=order.id).first()
    if delivery is None:
        delivery = create_or_assign_delivery_for_order(order, auto_assign=False)
    if delivery is None:
        raise DeliveryError(
            "La orden no tiene ubicación de tienda o de cliente para crear la entrega.",
            status_code=409, code='missing_locations',
        )
    return delivery


def _set_rider_manually(actor_user, order_id, employee_id, allowed_statuses) -> DeliveryAssignment:
    delivery = _resolve_order_delivery_for_manager(actor_user, order_id)
    if employee_id in (None, '', 'auto'):
        # Si el comerciante toca "Auto-asignar al repartidor más cercano" sin enviar employee_id,
        # limpiamos la lista de rechazos previos y ejecutamos el motor de auto-asignación OSRM.
        with transaction.atomic():
            locked = _lock_delivery(delivery.id)
            if int(locked.status) not in allowed_statuses:
                raise DeliveryError(
                    "La entrega ya no admite este cambio de repartidor.", status_code=409, code='invalid_delivery_status',
                )
            previous_rider = locked.rider
            if previous_rider is not None:
                _release_to_pending(locked)
                _notify_rider_on_commit(
                    previous_rider, "Entrega reasignada",
                    f"La orden N° {locked.order_id} fue puesta en búsqueda automática.",
                    'delivery_unassigned', locked,
                )
            # Se limpian los rechazos previos, pero NO se vuelve a ofrecer al repartidor recién retirado
            locked.declined_rider_ids = [previous_rider.id] if previous_rider is not None else []
            locked.save(update_fields=['declined_rider_ids'])
            transaction.on_commit(lambda: sync_delivery_meta(locked))
            if previous_rider is not None:
                _post_node_on_commit('delivery-status', build_status_payload(locked, {
                    'previous_rider_user_id': str(previous_rider.user_id),
                    'reason': 'auto_reassign',
                }))
        auto_assign_delivery(delivery.id)
        return get_delivery(delivery.id)

    try:
        emp_pk = int(employee_id)
    except (TypeError, ValueError):
        raise DeliveryError("El campo 'employee_id' es obligatorio.", code='employee_required')
    employee = Employee.objects.select_related('user').filter(pk=emp_pk).first()
    store = delivery.store
    if employee is None or employee.company_id != store.company_id:
        raise DeliveryError("El repartidor no pertenece a tu comercio.", status_code=404, code='rider_not_found')
    if employee.status != EmployeeStatus.ACTIVE or employee.role != EmployeeRole.DELIVERY:
        raise DeliveryError("Ese trabajador no es un repartidor activo.", code='rider_not_active')
    if not employee_assigned_to_store(employee, store):
        raise DeliveryError("Ese repartidor no está asignado a esta sucursal.", code='rider_not_in_store')
    if employee.user_id == delivery.order.client_id:
        raise DeliveryError("El repartidor no puede entregar su propia compra.", code='rider_is_client')

    previous_rider = None
    try:
        with transaction.atomic():
            locked = _lock_delivery(delivery.id)
            if int(locked.status) not in allowed_statuses:
                raise DeliveryError(
                    "La entrega ya no admite este cambio de repartidor.", status_code=409, code='invalid_delivery_status',
                )
            if locked.rider_id == employee.id and int(locked.status) != DeliveryStatus.PENDING_RIDER:
                raise DeliveryError("Ese repartidor ya tiene esta entrega.", status_code=409, code='same_rider')
            previous_rider = locked.rider
            now = timezone.now()
            extra_fields = []
            if previous_rider is not None and previous_rider.id != employee.id:
                extra_fields = _rotate_tracking_secrets(locked)
            locked.rider = employee
            locked.status = DeliveryStatus.ASSIGNED
            locked.assigned_at = now
            locked.accepted_at = None
            locked.at_store_at = None
            locked.eta_at = None
            locked.offer_expires_at = now + timedelta(seconds=OFFER_TTL_S)
            locked.is_auto_assigned = False
            locked.assigned_by = actor_user
            locked.save(update_fields=[
                'rider', 'status', 'assigned_at', 'accepted_at', 'at_store_at', 'offer_expires_at',
                'is_auto_assigned', 'assigned_by', 'eta_at',
            ] + extra_fields)
            if previous_rider is not None and previous_rider.id != employee.id:
                _notify_rider_on_commit(
                    previous_rider, "Entrega reasignada",
                    f"La orden N° {locked.order_id} fue reasignada a otro repartidor.",
                    'delivery_reassigned', locked,
                )
            _announce_offer_on_commit(locked)
            if previous_rider is not None and previous_rider.id != employee.id:
                _post_node_on_commit('delivery-status', build_status_payload(locked, {
                    'previous_rider_user_id': str(previous_rider.user_id),
                }))
    except IntegrityError:
        raise DeliveryError("Ese repartidor ya tiene una entrega activa.", status_code=409, code='rider_busy')
    return get_delivery(delivery.id)


def manual_assign_delivery(actor_user, order_id, employee_id) -> DeliveryAssignment:
    """ El comercio elige manualmente al repartidor (solo si nadie la aceptó todavía). """
    return _set_rider_manually(
        actor_user, order_id, employee_id, (DeliveryStatus.PENDING_RIDER, DeliveryStatus.ASSIGNED),
    )


def reassign_delivery(actor_user, order_id, employee_id) -> DeliveryAssignment:
    """ Reasigna a otro repartidor mientras el paquete no haya salido de la tienda. """
    return _set_rider_manually(
        actor_user, order_id, employee_id,
        (DeliveryStatus.PENDING_RIDER, DeliveryStatus.ASSIGNED, DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE),
    )


def unassign_delivery(actor_user, order_id) -> DeliveryAssignment:
    """ Quita al repartidor (antes de la recogida) y vuelve a buscar otro automáticamente. """
    delivery = _resolve_order_delivery_for_manager(actor_user, order_id)
    with transaction.atomic():
        locked = _lock_delivery(delivery.id)
        if int(locked.status) == DeliveryStatus.PENDING_RIDER:
            # Sin repartidor: se reinicia la búsqueda automática limpiando rechazos previos
            locked.declined_rider_ids = []
            locked.save(update_fields=['declined_rider_ids'])
            transaction.on_commit(lambda: sync_delivery_meta(locked))
            _schedule_auto_assign(locked.id)
        else:
            if int(locked.status) not in (DeliveryStatus.ASSIGNED, DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE):
                raise DeliveryError("La entrega no tiene un repartidor que se pueda quitar.", status_code=409,
                                    code='invalid_delivery_status')
            previous_rider = locked.rider
            _release_to_pending(locked)
            _notify_rider_on_commit(
                previous_rider, "Entrega retirada",
                f"El comercio retiró la orden N° {locked.order_id} de tus entregas.",
                'delivery_unassigned', locked,
            )
            transaction.on_commit(lambda: sync_delivery_meta(locked))
            _post_node_on_commit('delivery-status', build_status_payload(locked, {
                'previous_rider_user_id': str(previous_rider.user_id) if previous_rider else None,
                'reason': 'unassigned',
            }))
            _schedule_auto_assign(locked.id)
    return get_delivery(delivery.id)


def _rotate_tracking_secrets(locked) -> list:
    """
    Al cambiar de repartidor se regenera `tracking_key` (BLE / PIN offline) para que el repartidor anterior
    no pueda seguir firmando posiciones ni entregas offline. El PIN del cliente NO cambia: solo se recalcula su hash.
    Retorna los campos a guardar. Debe llamarse dentro de la transacción.
    """
    if not locked.tracking_key:
        return []
    from types import SimpleNamespace
    snapshot = SimpleNamespace(
        id=locked.id, tracking_key=locked.tracking_key,
        accepted_at=locked.accepted_at, created_at=locked.created_at,
    )
    transaction.on_commit(lambda: unregister_rolling_ids(snapshot))
    locked.tracking_key = secrets.token_hex(32)
    fields = ['tracking_key']
    if locked.handoff_pin:
        locked.handoff_pin_hash = hash_handoff_pin(locked.tracking_key, locked.handoff_pin)
        fields.append('handoff_pin_hash')
    return fields


def _release_to_pending(locked) -> None:
    """ Devuelve la entrega a PENDING_RIDER excluyendo al repartidor actual (dentro de la transacción). """
    declined = [int(x) for x in (locked.declined_rider_ids or []) if str(x).isdigit()]
    if locked.rider_id and locked.rider_id not in declined:
        declined.append(locked.rider_id)
    secret_fields = _rotate_tracking_secrets(locked) if locked.rider_id else []
    locked.declined_rider_ids = declined
    locked.rider = None
    locked.status = DeliveryStatus.PENDING_RIDER
    locked.offer_expires_at = None
    locked.assigned_at = None
    locked.accepted_at = None
    locked.at_store_at = None
    locked.eta_at = None
    locked.save(update_fields=[
        'declined_rider_ids', 'rider', 'status', 'offer_expires_at', 'assigned_at', 'accepted_at', 'at_store_at',
        'eta_at',
    ] + secret_fields)


def expire_offer(delivery_id) -> bool:
    """ Si la oferta de 45 s venció sin respuesta, la pasa al siguiente candidato. """
    with transaction.atomic():
        locked = _delivery_qs().select_for_update(of=('self',)).filter(pk=delivery_id).first()
        if locked is None or int(locked.status) != DeliveryStatus.ASSIGNED:
            return False
        if not locked.offer_expires_at or locked.offer_expires_at > timezone.now():
            return False
        previous_rider = locked.rider
        _release_to_pending(locked)
        _notify_rider_on_commit(
            previous_rider, "Oferta vencida",
            f"La oferta de la orden N° {locked.order_id} venció y pasó a otro repartidor.",
            'delivery_offer_expired', locked,
        )
        transaction.on_commit(lambda: sync_delivery_meta(locked))
        _post_node_on_commit('delivery-status', build_status_payload(locked, {
            'previous_rider_user_id': str(previous_rider.user_id) if previous_rider else None,
            'reason': 'offer_expired',
        }))
    safe_auto_assign(delivery_id)
    return True


# =========================================================================
# 7. CICLO DE VIDA DEL REPARTIDOR
# =========================================================================
def _compute_route(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, vehicle_type) -> dict:
    profile = routing.profile_for_vehicle(vehicle_type)
    route = routing.route((origin_lat, origin_lng), (dest_lat, dest_lng), profile=profile)
    points = list(route.get('points') or [])
    cum_dist = list(route.get('cum_dist') or [])
    cum_time = list(route.get('cum_time') or [])
    if len(points) < 2 or len(cum_dist) != len(points) or len(cum_time) != len(points):
        points = [(origin_lat, origin_lng), (dest_lat, dest_lng)]
        cum_dist = [0.0, float(route.get('distance_m') or 0.0)]
        cum_time = [0.0, float(route.get('duration_s') or 0.0)]
        route['polyline6'] = routing.encode_polyline(points, precision=6)
    route['points'] = points
    route['cum_dist'] = cum_dist
    route['cum_time'] = cum_time
    return route


def _apply_route(delivery, route: dict) -> List[str]:
    points = route['points']
    delivery.route_polyline6 = route.get('polyline6') or ''
    delivery.route_geometry = LineString([(float(lng), float(lat)) for lat, lng in points], srid=4326)
    delivery.route_cum_dist = [round(float(x), 2) for x in route['cum_dist']]
    delivery.route_cum_time = [round(float(x), 2) for x in route['cum_time']]
    delivery.route_distance_m = float(route.get('distance_m') or 0.0)
    delivery.route_duration_s = float(route.get('duration_s') or 0.0)
    return ['route_polyline6', 'route_geometry', 'route_cum_dist', 'route_cum_time', 'route_distance_m', 'route_duration_s']


def accept_delivery(employee, delivery_id) -> DeliveryAssignment:
    """ El repartidor acepta la oferta: se calcula la ruta tienda -> cliente y se inicializa el ancla. """
    delivery = get_delivery(delivery_id)
    _require_rider_of(delivery, employee)
    if int(delivery.status) != DeliveryStatus.ASSIGNED:
        raise DeliveryError("Esta entrega no está esperando tu aceptación.", status_code=409, code='invalid_delivery_status')
    if delivery.offer_expires_at and delivery.offer_expires_at <= timezone.now():
        expire_offer(delivery.id)
        raise DeliveryError("La oferta venció.", status_code=410, code='offer_expired')

    # Ruta (red) fuera del bloqueo
    route = _compute_route(
        float(delivery.origin_point.y), float(delivery.origin_point.x),
        float(delivery.dest_point.y), float(delivery.dest_point.x),
        employee.vehicle_type,
    )
    approach_s = 0.0
    loc = _rider_loc_get(employee.id)
    if loc and loc.get('lat') is not None:
        try:
            approach = routing.table([(float(loc['lat']), float(loc['lng']))],
                                     (float(delivery.origin_point.y), float(delivery.origin_point.x)),
                                     profile=routing.profile_for_vehicle(employee.vehicle_type))
            approach_s = float(approach[0]) if approach and approach[0] is not None else 0.0
        except Exception:
            approach_s = 0.0

    with transaction.atomic():
        locked = _lock_delivery(delivery.id)
        _require_rider_of(locked, employee)
        if int(locked.status) != DeliveryStatus.ASSIGNED:
            raise DeliveryError("Esta entrega no está esperando tu aceptación.", status_code=409,
                                code='invalid_delivery_status')
        if locked.offer_expires_at and locked.offer_expires_at <= timezone.now():
            raise DeliveryError("La oferta venció.", status_code=410, code='offer_expired')
        now = timezone.now()
        fields = _apply_route(locked, route)
        locked.status = DeliveryStatus.ACCEPTED
        locked.accepted_at = now
        locked.offer_expires_at = None
        locked.eta_at = now + timedelta(seconds=approach_s + float(locked.route_duration_s or 0.0))
        locked.save(update_fields=fields + ['status', 'accepted_at', 'offer_expires_at', 'eta_at'])

        delivery_ref = locked

        def _run():
            sync_delivery_meta(delivery_ref)
            reset_live_anchor(delivery_ref, mode='free',
                              lat=float(loc['lat']) if loc and loc.get('lat') is not None else None,
                              lng=float(loc['lng']) if loc and loc.get('lng') is not None else None)
            register_rolling_ids(delivery_ref)

        transaction.on_commit(_run)
        _after_commit_status(locked, sync_meta=False, include_route=True)
        _notify_client_on_commit(
            locked, "Tu pedido tiene repartidor",
            f"Un repartidor de {locked.store.company.name} aceptó tu pedido y va a la tienda.",
            'delivery_accepted',
        )
        _notify_merchants_on_commit(
            locked, "Repartidor en camino a la tienda",
            f"La orden N° {locked.order_id} fue aceptada por un repartidor.",
            'delivery_accepted',
        )
    return get_delivery(delivery.id)


def decline_delivery(employee, delivery_id, reason: str = '') -> DeliveryAssignment:
    """ El repartidor rechaza la oferta: se excluye y se ofrece al siguiente candidato. """
    with transaction.atomic():
        locked = _lock_delivery(int(delivery_id))
        _require_rider_of(locked, employee)
        if int(locked.status) != DeliveryStatus.ASSIGNED:
            raise DeliveryError("Solo puedes rechazar una oferta pendiente.", status_code=409, code='invalid_delivery_status')
        rider_user_id = str(employee.user_id)
        _release_to_pending(locked)
        # Primero la meta (Redis) y luego el aviso a Node, para que Node no relea la meta vieja
        transaction.on_commit(lambda: sync_delivery_meta(locked))
        _post_node_on_commit('delivery-status', build_status_payload(locked, {
            'previous_rider_user_id': rider_user_id,
            'reason': (str(reason or '')[:60] or 'declined'),
        }))
        _schedule_auto_assign(locked.id)
    return get_delivery(locked.id)


def mark_arrived_store(employee, delivery_id, lat=None, lng=None, force: bool = False) -> DeliveryAssignment:
    """ Llegada a la tienda (geocerca de 100 m sobre `origin_point`, salvo `force=True`). """
    coords = parse_lat_lng(lat, lng, required=not force)
    with transaction.atomic():
        locked = _lock_delivery(int(delivery_id))
        _require_rider_of(locked, employee)
        if int(locked.status) != DeliveryStatus.ACCEPTED:
            raise DeliveryError("Debes aceptar la entrega antes de marcar la llegada.", status_code=409,
                                code='invalid_delivery_status')
        update_fields = ['status', 'at_store_at']
        if coords is not None:
            distance = haversine_m(coords[0], coords[1], locked.origin_point.y, locked.origin_point.x)
            if distance > STORE_GEOFENCE_M and not force:
                raise DeliveryError(
                    f"Aún estás a {int(distance)} m de la tienda. Acércate para marcar la llegada.",
                    code='outside_store_geofence',
                )
            locked.last_fix_point = make_point(coords[0], coords[1])
            locked.last_fix_at = timezone.now()
            locked.last_fix_source = FixSource.GNSS_SOCKET
            update_fields += ['last_fix_point', 'last_fix_at', 'last_fix_source']
        locked.status = DeliveryStatus.AT_STORE
        locked.at_store_at = timezone.now()
        locked.save(update_fields=update_fields)
        _after_commit_status(locked)
        _notify_merchants_on_commit(
            locked, "El repartidor llegó a la tienda",
            f"El repartidor de la orden N° {locked.order_id} está en la tienda esperando el paquete.",
            'delivery_at_store',
        )
    return get_delivery(locked.id)


def mark_picked_up(actor_user, delivery_id, employee=None) -> DeliveryAssignment:
    """
    Recogida del paquete (repartidor asignado o dueño/asistente de la tienda). La orden pasa a
    DELIVERY_SENT con `ship_order_service` y el ancla se reinicia al inicio de la ruta tienda -> cliente.
    """
    delivery = get_delivery(delivery_id)
    is_rider = employee is not None and delivery.rider_id == employee.id
    if not is_rider and not user_can_manage_store_deliveries(actor_user, delivery.store):
        raise DeliveryError("No tienes permisos sobre esta entrega.", status_code=403, code='forbidden')

    with transaction.atomic():
        # Orden de bloqueo consistente en todo el sistema: primero la orden, luego la entrega
        order = _lock_order(delivery.order_id)
        locked = _lock_delivery(delivery.id)
        if locked.rider_id is None:
            raise DeliveryError("La entrega todavía no tiene repartidor.", status_code=409, code='no_rider')
        if int(locked.status) not in (DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE):
            raise DeliveryError("La entrega no está lista para ser recogida.", status_code=409, code='invalid_delivery_status')
        if order.status == OrderStatus.REPORTED:
            raise DeliveryError(
                "Esta orden ha sido reportada y se encuentra en revisión por Soporte CartMaker.",
                status_code=409, code='order_reported',
            )
        if order.status == OrderStatus.WAITING:
            try:
                ship_order_service(
                    order, actor_user,
                    notify_body=f"El repartidor de {order.store.company.name} ya tiene tus productos y va en camino.",
                )
            except OrderServiceError as e:
                raise DeliveryError(e.message, status_code=e.status_code, code='order_not_shippable')
        elif order.status != OrderStatus.DELIVERY_SENT:
            raise DeliveryError("La orden ya no admite despacho.", status_code=409, code='order_not_shippable')

        now = timezone.now()
        update_fields = ['status', 'picked_up_at', 'eta_at']
        if not locked.route_polyline6:
            route = _compute_route(
                float(locked.origin_point.y), float(locked.origin_point.x),
                float(locked.dest_point.y), float(locked.dest_point.x),
                locked.rider.vehicle_type,
            )
            update_fields += _apply_route(locked, route)
        locked.status = DeliveryStatus.PICKED_UP
        locked.picked_up_at = now
        locked.eta_at = now + timedelta(seconds=float(locked.route_duration_s or 0.0))
        locked.save(update_fields=update_fields)

        delivery_ref = locked
        status_payload = build_status_payload(locked)
        route_payload = build_route_payload(locked)

        def _run():
            sync_delivery_meta(delivery_ref)
            anchor = reset_live_anchor(delivery_ref, mode='route')
            register_rolling_ids(delivery_ref)
            status_payload['anchor'] = anchor
            _post_node('delivery-route', route_payload)
            _post_node('delivery-status', status_payload)

        transaction.on_commit(_run)
    return get_delivery(delivery.id)


def mark_arriving(delivery_id) -> Optional[DeliveryAssignment]:
    """ PICKED_UP -> ARRIVING (el repartidor entró a menos de 150 m del cliente; lo detecta Node). """
    with transaction.atomic():
        locked = _delivery_qs().select_for_update(of=('self',)).filter(pk=delivery_id).first()
        if locked is None or int(locked.status) != DeliveryStatus.PICKED_UP:
            return locked
        locked.status = DeliveryStatus.ARRIVING
        locked.arriving_at = timezone.now()
        locked.save(update_fields=['status', 'arriving_at'])
        _after_commit_status(locked)
        _notify_client_on_commit(
            locked, "Tu repartidor está llegando",
            "Tu pedido está a menos de 150 m. Ten a mano tu PIN de entrega.",
            'delivery_arriving',
        )
    return locked


def complete_delivery_with_pin(employee, delivery_id, pin, lat=None, lng=None, fix_time=None,
                               t_ms=None, offline_signature=None) -> dict:
    """
    Entrega con PIN. El PIN completa la orden (COMPLETED vía `complete_order_service`).

    - Online: {pin, lat?, lng?, fix_time?}
    - Offline sincronizada: {pin, lat, lng, t_ms, offline_signature} con
      offline_signature = hex(HMAC_SHA256(bytes.fromhex(tracking_key), f"{id}:{pin}:{t_ms}:{lat:.6f}:{lng:.6f}")).
      Se exige además estar a <= 150 m de `dest_point` y un `t_ms` coherente.
    - Máximo 5 intentos de PIN; luego se bloquea (el comercio o soporte deben intervenir).
    """
    is_offline = bool(offline_signature)
    coords = parse_lat_lng(lat, lng, required=is_offline)
    pin_str = str(pin or '').strip()
    if not pin_str:
        raise DeliveryError("Debes ingresar el PIN que te dicta el cliente.", code='pin_required')

    delivery = get_delivery(delivery_id)
    _require_rider_of(delivery, employee)

    pending_error = None
    with transaction.atomic():
        order = _lock_order(delivery.order_id)
        locked = _lock_delivery(delivery.id)
        _require_rider_of(locked, employee)
        if int(locked.status) not in IN_TRANSIT_STATUSES:
            raise DeliveryError("La entrega no está en camino al cliente.", status_code=409, code='invalid_delivery_status')
        if int(locked.pin_attempts or 0) >= DELIVERY_MAX_PIN_ATTEMPTS:
            raise DeliveryError(
                "Demasiados intentos de PIN. Pide al comercio que confirme la entrega o contacta a soporte.",
                status_code=423, code='pin_locked',
            )

        fix_at = timezone.now()
        source = FixSource.GNSS_SOCKET
        if is_offline:
            try:
                t_ms_val = int(t_ms)
            except (TypeError, ValueError):
                raise DeliveryError("El campo 't_ms' es obligatorio para la entrega offline.", code='t_ms_required')
            assigned_ms = dt_ms(locked.assigned_at)
            picked_rel_ms = max(0, dt_ms(locked.picked_up_at) - assigned_ms) if locked.picked_up_at else 0
            abs_ms = assigned_ms + t_ms_val
            if t_ms_val <= 0 or abs_ms > now_ms() + 60000 or t_ms_val + 5000 < picked_rel_ms:
                raise DeliveryError("La hora de la entrega offline no es coherente.", code='offline_time_incoherent')
            distance = haversine_m(coords[0], coords[1], locked.dest_point.y, locked.dest_point.x)
            if distance > OFFLINE_DELIVERY_RADIUS_M:
                raise DeliveryError(
                    f"La entrega offline se registró a {int(distance)} m del destino (máximo {OFFLINE_DELIVERY_RADIUS_M} m).",
                    code='offline_too_far',
                )
            signature_ok = verify_offline_signature(
                locked.tracking_key, offline_signature, locked.id, pin_str, t_ms_val, coords[0], coords[1],
            )
            if not signature_ok:
                raise DeliveryError("La firma de la entrega offline es inválida.", status_code=403,
                                    code='invalid_offline_signature')
            fix_at = datetime.fromtimestamp(abs_ms / 1000.0, tz=timezone.get_current_timezone())
            source = FixSource.OFFLINE_BUFFER

        if not verify_handoff_pin(locked.tracking_key, locked.handoff_pin_hash, pin_str):
            locked.pin_attempts = int(locked.pin_attempts or 0) + 1
            locked.save(update_fields=['pin_attempts'])
            remaining = max(0, DELIVERY_MAX_PIN_ATTEMPTS - locked.pin_attempts)
            pending_error = DeliveryError(
                f"PIN incorrecto. Te quedan {remaining} intento(s)." if remaining else
                "PIN incorrecto. Se bloqueó la entrega con PIN; el comercio o soporte deben confirmarla.",
                status_code=400 if remaining else 423,
                code='invalid_pin' if remaining else 'pin_locked',
            )
        else:
            if order.status == OrderStatus.REPORTED:
                raise DeliveryError(
                    "Esta orden ha sido reportada y se encuentra en revisión por Soporte CartMaker.",
                    status_code=409, code='order_reported',
                )
            tokens_earned = 0.0
            if order.status != OrderStatus.COMPLETED:
                try:
                    result = complete_order_service(order, employee.user, actor_role='rider')
                    tokens_earned = result.get('tokens_earned', 0.0)
                except OrderServiceError as e:
                    raise DeliveryError(e.message, status_code=e.status_code, code='order_not_completable')

            locked.status = DeliveryStatus.DELIVERED
            locked.delivered_at = timezone.now()
            update_fields = ['status', 'delivered_at']
            if coords is not None:
                locked.last_fix_point = make_point(coords[0], coords[1])
                locked.last_fix_at = fix_at
                locked.last_fix_source = source
                update_fields += ['last_fix_point', 'last_fix_at', 'last_fix_source']
            locked.save(update_fields=update_fields)

            delivery_ref = locked
            store_id = locked.store_id
            status_payload = build_status_payload(locked, {'offline': is_offline})

            def _run():
                sync_delivery_meta(delivery_ref)
                _post_node('delivery-status', status_payload)
                _enqueue_trace_persist(delivery_ref.id)
                _safe_store_retry(store_id)

            transaction.on_commit(_run)

    if pending_error is not None:
        raise pending_error
    final = get_delivery(delivery.id)
    return {'delivery': final.get_json(viewer_role='rider'), 'order_status': int(OrderStatus.COMPLETED),
            'tokens_earned_by_client': tokens_earned, 'offline': is_offline}


def _enqueue_trace_persist(delivery_id) -> None:
    try:
        from ..tasks import persist_delivery_trace_task
        persist_delivery_trace_task.delay(delivery_id)
    except Exception as e:
        logger.warning(f"Delivery #{delivery_id}: broker no disponible, se persiste la traza en línea ({e}).")
        try:
            persist_delivery_trace(delivery_id)
        except Exception as inner:
            logger.error(f"Delivery #{delivery_id}: no se pudo persistir la traza: {inner}")


def fail_delivery(actor_user, delivery_id, reason: str, employee=None) -> DeliveryAssignment:
    """
    - Antes de la recogida (ACCEPTED / AT_STORE) por el repartidor: libera la entrega y se busca otro repartidor.
    - Después de la recogida (PICKED_UP / ARRIVING), por el repartidor o el comercio: pasa a FAILED
      (cliente ausente o incidencia) y la orden queda para gestión del comercio / soporte.
    """
    reason_clean = str(reason or '').strip()[:255]
    if not reason_clean:
        raise DeliveryError("Debes indicar el motivo.", code='reason_required')
    delivery = get_delivery(delivery_id)
    is_rider = employee is not None and delivery.rider_id == employee.id
    is_manager = user_can_manage_store_deliveries(actor_user, delivery.store) if not is_rider else False
    if not is_rider and not is_manager:
        raise DeliveryError("No tienes permisos sobre esta entrega.", status_code=403, code='forbidden')

    with transaction.atomic():
        locked = _lock_delivery(delivery.id)
        status_value = int(locked.status)
        if is_rider and status_value in (DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE):
            rider_user_id = str(locked.rider.user_id)
            locked.failure_reason = reason_clean
            locked.save(update_fields=['failure_reason'])
            _release_to_pending(locked)
            transaction.on_commit(lambda: sync_delivery_meta(locked))
            _post_node_on_commit('delivery-status', build_status_payload(locked, {
                'previous_rider_user_id': rider_user_id, 'reason': 'rider_released',
            }))
            _notify_merchants_on_commit(
                locked, "El repartidor liberó la entrega",
                f"Buscamos otro repartidor para la orden N° {locked.order_id}. Motivo: {reason_clean}",
                'delivery_released',
            )
            _schedule_auto_assign(locked.id)
        elif status_value in IN_TRANSIT_STATUSES:
            locked.status = DeliveryStatus.FAILED
            locked.failure_reason = reason_clean
            locked.cancelled_at = timezone.now()
            locked.save(update_fields=['status', 'failure_reason', 'cancelled_at'])
            delivery_ref = locked
            store_id = locked.store_id
            status_payload = build_status_payload(locked, {'reason': reason_clean})

            def _run():
                sync_delivery_meta(delivery_ref)
                _post_node('delivery-status', status_payload)
                _enqueue_trace_persist(delivery_ref.id)
                _safe_store_retry(store_id)

            transaction.on_commit(_run)
            _notify_client_on_commit(locked, "No se pudo completar la entrega",
                                     f"Motivo: {reason_clean}. El comercio se comunicará contigo.", 'delivery_failed')
            _notify_merchants_on_commit(locked, "Entrega fallida",
                                        f"La entrega de la orden N° {locked.order_id} falló. Motivo: {reason_clean}",
                                        'delivery_failed')
        else:
            raise DeliveryError("La entrega no está en un estado que permita reportar una falla.",
                                status_code=409, code='invalid_delivery_status')
    return get_delivery(delivery.id)


def cancel_delivery_for_order(order, reason: str = 'order_cancelled') -> Optional[DeliveryAssignment]:
    """
    Cancela la entrega de una orden (p. ej. el cliente canceló mientras estaba WAITING).
    Debe llamarse DENTRO de la transacción que cancela la orden (la orden ya está bloqueada).
    """
    locked = _delivery_qs().select_for_update(of=('self',)).filter(order_id=order.id).first()
    if locked is None or int(locked.status) in DELIVERY_TERMINAL_STATUSES:
        return locked
    rider = locked.rider
    locked.status = DeliveryStatus.CANCELLED
    locked.cancelled_at = timezone.now()
    locked.failure_reason = str(reason or '')[:255]
    locked.offer_expires_at = None
    locked.save(update_fields=['status', 'cancelled_at', 'failure_reason', 'offer_expires_at'])
    delivery_ref = locked
    store_id = locked.store_id
    status_payload = build_status_payload(locked, {'reason': reason})

    def _run():
        sync_delivery_meta(delivery_ref)
        _post_node('delivery-status', status_payload)
        cleanup_realtime_keys(delivery_ref)
        if rider is not None:
            _safe_store_retry(store_id)

    transaction.on_commit(_run)
    _notify_rider_on_commit(rider, "Entrega cancelada",
                            f"La orden N° {locked.order_id} fue cancelada. Ya no debes entregarla.",
                            'delivery_cancelled', locked)
    return locked


def finalize_delivery_for_closed_order(order, reason: str = 'order_completed') -> Optional[DeliveryAssignment]:
    """
    Cierra la entrega cuando la ORDEN se completa / resuelve por fuera del flujo del repartidor
    (el cliente o el comercio marcan "completada", o soporte la resuelve).
    - Si el paquete ya iba en camino (PICKED_UP / ARRIVING) -> DELIVERED.
    - Si aún no se había retirado -> CANCELLED.
    Libera al repartidor (restricción one_active_delivery_per_rider), limpia Redis y avisa a Node.
    Debe llamarse DENTRO de la transacción que bloqueó la orden.
    """
    locked = _delivery_qs().select_for_update(of=('self',)).filter(order_id=order.id).first()
    if locked is None or int(locked.status) in DELIVERY_TERMINAL_STATUSES:
        return locked
    rider = locked.rider
    now = timezone.now()
    if int(locked.status) in IN_TRANSIT_STATUSES:
        locked.status = DeliveryStatus.DELIVERED
        locked.delivered_at = now
        locked.failure_reason = str(reason or '')[:255]
        locked.save(update_fields=['status', 'delivered_at', 'failure_reason'])
    else:
        locked.status = DeliveryStatus.CANCELLED
        locked.cancelled_at = now
        locked.failure_reason = str(reason or '')[:255]
        locked.offer_expires_at = None
        locked.save(update_fields=['status', 'cancelled_at', 'failure_reason', 'offer_expires_at'])
    delivery_ref = locked
    store_id = locked.store_id
    is_delivered = int(locked.status) == DeliveryStatus.DELIVERED
    status_payload = build_status_payload(locked, {'reason': reason})

    def _run():
        sync_delivery_meta(delivery_ref)
        _post_node('delivery-status', status_payload)
        if is_delivered:
            _enqueue_trace_persist(delivery_ref.id)
        else:
            cleanup_realtime_keys(delivery_ref)
        if rider is not None:
            _safe_store_retry(store_id)

    transaction.on_commit(_run)
    if rider is not None:
        _notify_rider_on_commit(
            rider, "Entrega cerrada",
            f"La orden N° {locked.order_id} fue cerrada por el comercio o soporte.",
            'delivery_closed', locked,
        )
    return locked


def confirm_delivery_by_manager(actor_user, delivery_id) -> dict:
    """
    El comercio (dueño o asistente) confirma la entrega cuando el PIN quedó bloqueado o el cliente no puede
    dictarlo. Completa la orden igual que el PIN (DELIVERED + COMPLETED).
    """
    delivery = get_delivery(delivery_id)
    if not user_can_manage_store_deliveries(actor_user, delivery.store):
        raise DeliveryError("No tienes permisos sobre esta entrega.", status_code=403, code='forbidden')
    tokens_earned = 0.0
    with transaction.atomic():
        order = _lock_order(delivery.order_id)
        locked = _lock_delivery(delivery.id)
        if int(locked.status) not in IN_TRANSIT_STATUSES:
            raise DeliveryError("La entrega no está en camino al cliente.", status_code=409,
                                code='invalid_delivery_status')
        if order.status == OrderStatus.REPORTED:
            raise DeliveryError("Esta orden está en revisión por Soporte CartMaker.", status_code=409,
                                code='order_reported')
        if order.status != OrderStatus.COMPLETED:
            try:
                result = complete_order_service(order, actor_user, actor_role='merchant')
                tokens_earned = result.get('tokens_earned', 0.0)
            except OrderServiceError as e:
                raise DeliveryError(e.message, status_code=e.status_code, code='order_not_completable')
        locked.status = DeliveryStatus.DELIVERED
        locked.delivered_at = timezone.now()
        locked.failure_reason = 'confirmed_by_merchant'
        locked.save(update_fields=['status', 'delivered_at', 'failure_reason'])
        delivery_ref = locked
        store_id = locked.store_id
        status_payload = build_status_payload(locked, {'reason': 'confirmed_by_merchant'})

        def _run():
            sync_delivery_meta(delivery_ref)
            _post_node('delivery-status', status_payload)
            _enqueue_trace_persist(delivery_ref.id)
            _safe_store_retry(store_id)

        transaction.on_commit(_run)
        _notify_rider_on_commit(locked.rider, "Entrega confirmada",
                                f"El comercio confirmó la entrega de la orden N° {locked.order_id}.",
                                'delivery_confirmed', locked)
    final = get_delivery(delivery.id)
    return {'delivery': final.get_json(viewer_role='merchant'), 'order_status': int(OrderStatus.COMPLETED),
            'tokens_earned_by_client': tokens_earned}


def recalculate_delivery_route(delivery_id, from_lat=None, from_lng=None, force: bool = False,
                               employee=None) -> DeliveryAssignment:
    """
    Recalcula la ruta (route_version + 1) cuando el repartidor se desvía. En tránsito parte de su
    posición actual; antes de la recogida, desde la tienda. Enfriamiento de 15 s.
    """
    delivery = get_delivery(delivery_id)
    if employee is not None:
        _require_rider_of(delivery, employee)
    status_value = int(delivery.status)
    if status_value not in STATUS_FROM_ACCEPTED:
        raise DeliveryError("La entrega no admite recálculo de ruta.", status_code=409, code='invalid_delivery_status')

    r = get_realtime_redis()
    if r is not None and not force:
        try:
            if not r.set(f"dlv:{delivery.id}:reroute_lock", '1', nx=True, ex=REROUTE_COOLDOWN_S):
                raise DeliveryError("La ruta se recalculó hace muy poco.", status_code=429, code='reroute_cooldown')
        except DeliveryError:
            raise
        except Exception:
            pass

    if status_value in IN_TRANSIT_STATUSES:
        coords = parse_lat_lng(from_lat, from_lng, required=False)
        if coords is None:
            live = read_live_anchor(delivery.id)
            if live and live.get('lat'):
                coords = (live['lat'], live['lng'])
            elif delivery.last_fix_point is not None:
                coords = (float(delivery.last_fix_point.y), float(delivery.last_fix_point.x))
            else:
                coords = (float(delivery.origin_point.y), float(delivery.origin_point.x))
    else:
        coords = (float(delivery.origin_point.y), float(delivery.origin_point.x))

    route = _compute_route(coords[0], coords[1], float(delivery.dest_point.y), float(delivery.dest_point.x),
                           delivery.rider.vehicle_type if delivery.rider else None)
    with transaction.atomic():
        locked = _lock_delivery(delivery.id)
        if int(locked.status) not in STATUS_FROM_ACCEPTED:
            raise DeliveryError("La entrega no admite recálculo de ruta.", status_code=409, code='invalid_delivery_status')
        fields = _apply_route(locked, route)
        locked.route_version = int(locked.route_version or 1) + 1
        if int(locked.status) in IN_TRANSIT_STATUSES:
            locked.eta_at = timezone.now() + timedelta(seconds=float(locked.route_duration_s or 0.0))
        locked.save(update_fields=fields + ['route_version', 'eta_at'])
        delivery_ref = locked
        route_payload = build_route_payload(locked)
        in_transit = int(locked.status) in IN_TRANSIT_STATUSES

        def _run():
            sync_delivery_meta(delivery_ref)
            if in_transit:
                route_payload['anchor'] = reset_live_anchor(delivery_ref, mode='route', lat=coords[0], lng=coords[1])
            _post_node('delivery-route', route_payload)

        transaction.on_commit(_run)
    return get_delivery(delivery.id)


# =========================================================================
# 8. BUFFER OFFLINE, TRAZA Y BACKFILL
# =========================================================================
def decode_trace_body(body: bytes, content_type: str = '') -> List[tuple]:
    """
    Acepta JSON `{"points": [...]}`, msgpack crudo o msgpack+gzip (cuerpo binario).
    El contenido msgpack puede ser una lista de puntos o un dict `{"points": [...]}`.
    """
    if not body:
        raise DeliveryError("El cuerpo de la traza está vacío.", code='empty_trace')
    ct = (content_type or '').lower()
    data = None
    if 'json' in ct:
        try:
            data = json.loads(body.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            raise DeliveryError("JSON inválido.", code='invalid_trace')
    else:
        raw = bytes(body)
        if raw[:2] == b'\x1f\x8b':
            raw = _safe_gunzip(raw)
        try:
            import msgpack
            data = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        except Exception:
            try:
                data = json.loads(raw.decode('utf-8'))
            except Exception:
                raise DeliveryError("No se pudo decodificar la traza (msgpack/gzip/JSON).", code='invalid_trace')
    points = data.get('points') if isinstance(data, dict) else data
    if not isinstance(points, (list, tuple)):
        raise DeliveryError("La traza debe contener una lista 'points'.", code='invalid_trace')
    if len(points) > MAX_TRACE_POINTS:
        raise DeliveryError(f"Máximo {MAX_TRACE_POINTS} puntos por traza.", status_code=413, code='trace_too_large')
    normalized = [normalize_trace_point(p) for p in points]
    return [p for p in normalized if p is not None]


def read_stream_points(delivery_id) -> List[tuple]:
    """ Lee el stream `dlv:{id}:trace` que escribe Node (campos t, ts, lat, lng, v, hdg, acc, src). """
    r = get_realtime_redis()
    if r is None:
        return []
    try:
        entries = r.xrange(key_trace(delivery_id), '-', '+', count=MAX_TRACE_POINTS + 1000)
    except Exception:
        return []
    points = []
    for _entry_id, fields in entries or []:
        try:
            point = normalize_trace_point({
                't_ms': int(float(fields.get('t'))),
                'lat': float(fields.get('lat')),
                'lng': float(fields.get('lng')),
                'speed_mps': float(fields.get('v') or 0.0),
                'heading': float(fields.get('hdg') or 0.0),
                'accuracy_m': float(fields.get('acc') or 0.0),
                'source': int(float(fields.get('src') or 0)),
            }, default_source=FixSource.GNSS_SOCKET)
        except (TypeError, ValueError):
            point = None
        if point is not None:
            points.append(point)
    return points


def _downsample(points: List[tuple], max_points: int) -> List[tuple]:
    if len(points) <= max_points:
        return list(points)
    step = len(points) / float(max_points)
    sampled = [points[int(i * step)] for i in range(max_points - 1)]
    sampled.append(points[-1])
    return sampled


def _save_trace(delivery, points: List[tuple], run_match: bool = True) -> DeliveryTrace:
    matched = ''
    if run_match and len(points) >= 2:
        sample = _downsample(points, MAX_MATCH_POINTS)
        assigned_s = dt_ms(delivery.assigned_at) / 1000.0
        try:
            result = routing.match(
                [(p[1] / 1e7, p[2] / 1e7) for p in sample],
                timestamps=[int(assigned_s + p[0] / 1000.0) for p in sample] if assigned_s else None,
                profile=routing.profile_for_vehicle(delivery.rider.vehicle_type if delivery.rider else None),
            )
            matchings = result.get('matchings') or []
            if matchings:
                matched = max(matchings, key=lambda m: m.get('distance_m') or 0.0).get('polyline6') or ''
        except Exception as e:
            logger.info(f"Delivery #{delivery.id}: map matching no disponible: {e}")
    trace, _created = DeliveryTrace.objects.get_or_create(delivery=delivery)
    trace.compressed_points = pack_trace_points(points)
    trace.point_count = len(points)
    trace.max_gap_s = trace_max_gap_s(points)
    if matched:
        trace.matched_polyline6 = matched
    trace.save(update_fields=['compressed_points', 'point_count', 'max_gap_s', 'matched_polyline6'])
    return trace


def upload_delivery_trace(employee, delivery_id, body: bytes, content_type: str = '') -> dict:
    """
    Subida del buffer offline del repartidor. Une y deduplica por `t_ms` con el stream de Redis y la traza
    guardada, actualiza `DeliveryTrace` y emite `delivery_trace_backfill` (respetando la privacidad del cliente).
    """
    delivery = get_delivery(delivery_id)
    _require_rider_of(delivery, employee)
    status_value = int(delivery.status)
    if status_value in (DeliveryStatus.PENDING_RIDER, DeliveryStatus.ASSIGNED, DeliveryStatus.CANCELLED):
        raise DeliveryError("La entrega no admite traza en este estado.", status_code=409, code='invalid_delivery_status')
    if delivery.delivered_at and delivery.delivered_at < timezone.now() - timedelta(hours=6):
        raise DeliveryError("La entrega terminó hace demasiado tiempo para subir la traza.", status_code=410,
                            code='trace_window_closed')

    uploaded = decode_trace_body(body, content_type)
    existing = []
    trace = DeliveryTrace.objects.filter(delivery=delivery).first()
    if trace is not None and trace.compressed_points:
        try:
            existing = unpack_trace_points(trace.compressed_points)
        except Exception:
            existing = []
    merged = merge_trace_points(read_stream_points(delivery.id), existing, uploaded)
    if len(merged) > MAX_TRACE_POINTS:
        merged = _downsample(merged, MAX_TRACE_POINTS)
    saved = _save_trace(delivery, merged, run_match=True)

    # Último fix conocido (si el buffer trae algo más nuevo que lo guardado)
    if uploaded and delivery.assigned_at:
        newest = max(uploaded, key=lambda p: p[0])
        newest_at = delivery.assigned_at + timedelta(milliseconds=newest[0])
        if newest_at <= timezone.now() + timedelta(seconds=60) and (delivery.last_fix_at is None or newest_at > delivery.last_fix_at):
            DeliveryAssignment.objects.filter(pk=delivery.pk).filter(
                Q(last_fix_at__isnull=True) | Q(last_fix_at__lt=newest_at)
            ).update(
                last_fix_point=make_point(newest[1] / 1e7, newest[2] / 1e7),
                last_fix_speed_mps=newest[3] / 100.0,
                last_fix_heading=newest[4] / 100.0,
                last_fix_accuracy_m=newest[5] / 10.0,
                last_fix_at=newest_at,
                last_fix_source=FixSource.OFFLINE_BUFFER,
            )

    # Backfill: el comercio y el repartidor ven todo; el cliente solo desde la recogida (privacidad)
    picked_rel_ms = None
    if delivery.picked_up_at and delivery.assigned_at:
        picked_rel_ms = max(0, dt_ms(delivery.picked_up_at) - dt_ms(delivery.assigned_at))
    uploaded_sorted = sorted({p[0]: p for p in uploaded}.values(), key=lambda p: p[0])
    sample = _downsample(uploaded_sorted, MAX_BACKFILL_POINTS)

    def as_json(p):
        return {'t_ms': p[0], 'lat': p[1] / 1e7, 'lng': p[2] / 1e7, 'speed_mps': p[3] / 100.0,
                'heading': p[4] / 100.0, 'source': p[6]}

    points_all = [as_json(p) for p in sample]
    points_client = []
    if picked_rel_ms is not None and status_value in (
        DeliveryStatus.PICKED_UP, DeliveryStatus.ARRIVING, DeliveryStatus.DELIVERED,
    ):
        points_client = [as_json(p) for p in sample if p[0] >= picked_rel_ms]
    if points_all:
        _post_node('delivery-trace-backfill', {
            'delivery_id': delivery.id,
            'status': status_value,
            'assigned_at_ms': dt_ms(delivery.assigned_at),
            'points_all': points_all,
            'points_client': points_client,
        })
    return {
        'received_points': len(uploaded),
        'stored_points': saved.point_count,
        'max_gap_s': saved.max_gap_s,
        'matched': bool(saved.matched_polyline6),
    }


def persist_delivery_trace(delivery_id) -> dict:
    """ Mueve el stream `dlv:{id}:trace` a `DeliveryTrace` y limpia las claves temporales (entregas terminadas). """
    delivery = _delivery_qs().filter(pk=delivery_id).first()
    if delivery is None:
        return {'persisted': False}
    stream_points = read_stream_points(delivery.id)
    existing = []
    trace = DeliveryTrace.objects.filter(delivery=delivery).first()
    if trace is not None and trace.compressed_points:
        try:
            existing = unpack_trace_points(trace.compressed_points)
        except Exception:
            existing = []
    merged = merge_trace_points(existing, stream_points)
    if merged:
        _save_trace(delivery, _downsample(merged, MAX_TRACE_POINTS), run_match=True)
    if int(delivery.status) in DELIVERY_TERMINAL_STATUSES:
        cleanup_realtime_keys(delivery)
    return {'persisted': bool(merged), 'points': len(merged)}


def cleanup_expired_traces() -> dict:
    """ Habeas Data: borra trazas vencidas (30 días) y la última posición de entregas viejas. """
    now = timezone.now()
    deleted, _ = DeliveryTrace.objects.filter(expires_at__lt=now).delete()
    cleared = DeliveryAssignment.objects.filter(
        status__in=DELIVERY_TERMINAL_STATUSES,
        created_at__lt=now - timedelta(days=30),
        last_fix_point__isnull=False,
    ).update(last_fix_point=None, last_fix_speed_mps=None, last_fix_heading=None, last_fix_accuracy_m=None)
    stale_shifts = RiderShift.objects.filter(
        is_active=True, last_heartbeat_at__lt=now - timedelta(hours=12),
    ).update(is_active=False, ended_at=now)
    return {'deleted_traces': deleted, 'cleared_fixes': cleared, 'closed_stale_shifts': stale_shifts}


# =========================================================================
# 9. RETRANSMISIÓN BLE (FASE 4)
# =========================================================================
def _decode_relay_packet(item: dict) -> Optional[bytes]:
    import base64
    raw = item.get('packet') or item.get('payload')
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    try:
        if len(raw) == BLE_PACKET_LEN * 2 and all(c in '0123456789abcdefABCDEF' for c in raw):
            data = bytes.fromhex(raw)
        else:
            padded = raw + '=' * (-len(raw) % 4)
            data = base64.urlsafe_b64decode(padded.replace('+', '-').replace('/', '_'))
    except (ValueError, TypeError):
        return None
    return data if len(data) == BLE_PACKET_LEN else None


def _resolve_rolling_id(rolling_id_hex: str, windows: List[int]):
    """ Busca la entrega por rolling_id en Redis (ventanas dadas) y, si no, entre las entregas activas de la BD. """
    r = get_realtime_redis()
    if r is not None:
        for w in windows:
            try:
                found = r.hget(key_roll(w), rolling_id_hex)
            except Exception:
                found = None
            if found:
                return int(found), w
    candidates = DeliveryAssignment.objects.filter(status__in=STATUS_FROM_ACCEPTED).exclude(tracking_key='') \
        .values_list('id', 'tracking_key')[:500]
    for pk, tracking_key in candidates:
        for w in windows:
            try:
                if ble_rolling_id(tracking_key, w).hex() == rolling_id_hex:
                    return int(pk), w
            except ValueError:
                continue
    return None, None


def _reconstruct_ble_time_ms(assigned_at_ms: int, t_rel_s: int, observed_s: float) -> int:
    """ t_rel_s viene módulo 65536: se elige el ciclo más cercano a la hora observada. """
    base_s = assigned_at_ms / 1000.0
    cycles = round((observed_s - base_s - t_rel_s) / 65536.0)
    return int((base_s + t_rel_s + max(0, cycles) * 65536) * 1000)


def process_ble_relay_batch(relayer_user, items) -> dict:
    """
    Procesa un lote de anuncios BLE retransmitidos por teléfonos cercanos. No se guarda la ubicación
    del retransmisor. Por cada paquete válido se actualiza `last_fix_*` (BLE_RELAY) y se inyecta el fix en Node.
    """
    if not isinstance(items, list):
        raise DeliveryError("El campo 'items' debe ser una lista.", code='invalid_items')
    stats = {'accepted': 0, 'duplicates': 0, 'rejected': 0}
    now_s = time.time()
    for item in items[:BLE_MAX_BATCH]:
        if not isinstance(item, dict):
            stats['rejected'] += 1
            continue
        packet = _decode_relay_packet(item)
        if packet is None:
            stats['rejected'] += 1
            continue
        observed_s = now_s
        try:
            if item.get('observed_at') is not None:
                obs = float(item.get('observed_at'))
                obs = obs / 1000.0 if obs > 1e11 else obs
                if now_s - BLE_MAX_AGE_S <= obs <= now_s + 60:
                    observed_s = obs
        except (TypeError, ValueError):
            pass
        w_obs = ble_window(observed_s)
        delivery_id, window = _resolve_rolling_id(packet[0:4].hex(), [w_obs, w_obs - 1])
        if delivery_id is None:
            stats['rejected'] += 1
            continue
        delivery = DeliveryAssignment.objects.filter(pk=delivery_id, status__in=STATUS_FROM_ACCEPTED) \
            .only('id', 'tracking_key', 'assigned_at', 'last_fix_at', 'status').first()
        if delivery is None or not delivery.assigned_at:
            stats['rejected'] += 1
            continue
        try:
            fix = parse_ble_packet(delivery.tracking_key, packet, expected_window=window)
        except (BlePacketError, ValueError):
            stats['rejected'] += 1
            continue

        r = get_realtime_redis()
        if r is not None:
            try:
                if not r.set(f"dlv:{delivery.id}:ble:{window}:{fix['seq']}", '1', nx=True, ex=2 * BLE_WINDOW_S):
                    stats['duplicates'] += 1
                    continue
            except Exception:
                pass

        assigned_ms = dt_ms(delivery.assigned_at)
        ts_ms = _reconstruct_ble_time_ms(assigned_ms, fix['t_rel_s'], observed_s)
        if ts_ms > (now_s + 60) * 1000 or ts_ms < (now_s - BLE_MAX_AGE_S) * 1000:
            stats['rejected'] += 1
            continue
        fix_at = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.get_current_timezone())
        DeliveryAssignment.objects.filter(pk=delivery.pk).filter(
            Q(last_fix_at__isnull=True) | Q(last_fix_at__lt=fix_at)
        ).update(
            last_fix_point=make_point(fix['lat'], fix['lng']),
            last_fix_speed_mps=fix['speed_mps'],
            last_fix_heading=fix['heading'],
            last_fix_accuracy_m=25.0,
            last_fix_at=fix_at,
            last_fix_source=FixSource.BLE_RELAY,
        )
        _post_node('delivery-fix', {
            'delivery_id': delivery.id,
            't_ms': max(0, ts_ms - assigned_ms),
            'ts_ms': ts_ms,
            'lat': fix['lat'],
            'lng': fix['lng'],
            'speed_mps': fix['speed_mps'],
            'heading': fix['heading'],
            'accuracy_m': 25.0,
            'seq': fix['seq'],
            'source': 'ble_relay',
        })
        stats['accepted'] += 1
    stats['received'] = min(len(items), BLE_MAX_BATCH)
    return stats


# =========================================================================
# 10. CONSULTAS PARA LAS VISTAS Y PARA NODE
# =========================================================================
def build_bootstrap(user, delivery_id, ctx: str, emp_id=None) -> dict:
    """
    Todo lo que la app necesita para pintar el seguimiento: entrega (con privacidad por rol), ruta y
    perfil de tiempos, ancla actual, hora del servidor y — SOLO al repartidor — `tracking_key`.
    """
    delivery = get_delivery(delivery_id)
    role = resolve_viewer_role(user, delivery, ctx, emp_id)
    if role is None:
        raise DeliveryError("No participas en esta entrega.", status_code=403, code='not_participant')
    status_value = int(delivery.status)
    data = {
        'role': role,
        'delivery': delivery.get_json(viewer_role=role),
        'server_time_ms': now_ms(),
        'socket': {
            'join_event': 'join_delivery',
            'room': f"delivery_{delivery.id}",
        },
        'protocol': {
            'pace_k_min': 0.25,
            'pace_k_max': 2.5,
            'arriving_radius_m': ARRIVING_RADIUS_M,
            'off_route_threshold_m': 40,
        },
    }
    show_route = (
        (role == 'client' and status_value in IN_TRANSIT_STATUSES)
        or (role == 'merchant' and status_value in STATUS_FROM_ACCEPTED + (DeliveryStatus.DELIVERED,))
        or (role == 'rider' and status_value in STATUS_FROM_ACCEPTED + (DeliveryStatus.DELIVERED,))
    )
    if show_route and delivery.route_polyline6:
        data['route'] = {
            'version': delivery.route_version,
            'polyline6': delivery.route_polyline6,
            'cum_dist': delivery.route_cum_dist or [],
            'cum_time': delivery.route_cum_time or [],
            'distance_m': delivery.route_distance_m,
            'duration_s': delivery.route_duration_s,
        }
    show_anchor = (
        (role == 'client' and status_value in IN_TRANSIT_STATUSES)
        or (role in ('merchant', 'rider') and status_value in STATUS_FROM_ACCEPTED)
    )
    data['anchor'] = read_live_anchor(delivery.id) if show_anchor else None
    # La clave de rastreo (BLE / PIN offline) solo se entrega cuando el repartidor ya aceptó la entrega
    if role == 'rider' and status_value in STATUS_FROM_ACCEPTED:
        data['rider_secrets'] = {
            'tracking_key': delivery.tracking_key,
            'assigned_at_ms': dt_ms(delivery.assigned_at),
            'ble_service_uuid16': getattr(settings, 'DELIVERY_BLE_SERVICE_UUID16', 'CA7E'),
            'ble_window_s': BLE_WINDOW_S,
        }
    return data


def list_rider_assignments(employee, status_filter: str = 'active') -> List[DeliveryAssignment]:
    qs = _delivery_qs().filter(rider=employee)
    status_filter = (status_filter or 'active').strip().lower()
    if status_filter == 'active':
        qs = qs.filter(status__in=DELIVERY_ACTIVE_STATUSES)
    elif status_filter == 'completed':
        qs = qs.filter(status__in=DELIVERY_TERMINAL_STATUSES)
    return list(qs.order_by('-created_at')[:50])


def list_available_riders(actor_user, store_id) -> dict:
    """ Repartidores de la sucursal con turno, estado en línea, batería y carga actual (para el comercio). """
    store_uuid = parse_store_uuid(store_id)
    store = CompanyStore.objects.select_related('company', 'location').filter(pk=store_uuid).first() if store_uuid else None
    if store is None:
        raise DeliveryError("La sucursal no existe.", status_code=404, code='store_not_found')
    if not user_can_manage_store_deliveries(actor_user, store):
        raise DeliveryError("No tienes permisos sobre esta sucursal.", status_code=403, code='not_store_manager')
    riders = (
        Employee.objects.select_related('user')
        .filter(company_id=store.company_id, role=EmployeeRole.DELIVERY, status=EmployeeStatus.ACTIVE)
        .filter(Q(employeestoreassignment__store=store) | Q(permissions__allowed_stores=store))
        .distinct()
    )
    rider_ids = [r.id for r in riders]
    shifts = {
        s.employee_id: s for s in RiderShift.objects.filter(employee_id__in=rider_ids, store=store, is_active=True)
    }
    active = {
        d.rider_id: d for d in DeliveryAssignment.objects.filter(rider_id__in=rider_ids, status__in=DELIVERY_ACTIVE_STATUSES)
    }
    today_start = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    delivered_today = dict(
        DeliveryAssignment.objects.filter(rider_id__in=rider_ids, status=DeliveryStatus.DELIVERED,
                                          delivered_at__gte=today_start)
        .values('rider_id').annotate(n=Count('id')).values_list('rider_id', 'n')
    )
    cutoff = timezone.now() - timedelta(seconds=HEARTBEAT_MAX_AGE_S)
    data = []
    for rider in riders:
        shift = shifts.get(rider.id)
        current = active.get(rider.id)
        loc = _rider_loc_get(rider.id)
        distance_to_store = None
        if loc and loc.get('lat') is not None:
            distance_to_store = round(haversine_m(float(loc['lat']), float(loc['lng']),
                                                  float(store.location.coordinates.y),
                                                  float(store.location.coordinates.x))) \
                if hasattr(store, 'location') and store.location else None
        on_shift = shift is not None
        heartbeat_fresh = bool(shift and shift.last_heartbeat_at and shift.last_heartbeat_at >= cutoff)
        data.append({
            'employee_id': rider.id,
            'display_name': (rider.display_alias or f"{rider.user.first_name} {rider.user.last_name}").strip(),
            'profile_picture': rider.user.get_profile_picture_url() if rider.user.profile_picture else '',
            'vehicle_type': int(rider.vehicle_type) if rider.vehicle_type is not None else None,
            'on_shift': on_shift,
            'online': heartbeat_fresh or _rider_is_online(rider.id),
            'available': on_shift and heartbeat_fresh and current is None,
            'battery_level': (
                (loc or {}).get('battery') if (loc and loc.get('battery') is not None)
                else (shift.battery_level if shift else None)
            ),
            'last_heartbeat_at': timezone.localtime(shift.last_heartbeat_at).isoformat()
            if shift and shift.last_heartbeat_at else None,
            'distance_to_store_m': distance_to_store,
            'active_delivery': {
                'delivery_id': current.id, 'order_id': current.order_id, 'status': int(current.status),
            } if current else None,
            'delivered_today': int(delivered_today.get(rider.id, 0)),
        })
    data.sort(key=lambda d: (
        not d['available'], not d['online'],
        d['distance_to_store_m'] if d['distance_to_store_m'] is not None else 10 ** 9,
    ))
    pending = DeliveryAssignment.objects.filter(store=store, status=DeliveryStatus.PENDING_RIDER).count()
    return {'store_id': str(store.id), 'pending_deliveries': pending, 'riders': data}


def get_delivery_meta_for_node(delivery_id) -> dict:
    """ Reconstruye `dlv:{id}:meta` desde la BD (Node la pide si expiró en Redis). """
    delivery = get_delivery(delivery_id)
    mapping = sync_delivery_meta(delivery) or build_meta_mapping(delivery)
    return mapping


def handle_node_event(payload: dict) -> dict:
    """
    Eventos que Node envía a Django:
    - {event: 'arriving', delivery_id}: el repartidor entró a menos de 150 m del cliente.
    - {event: 'reroute', delivery_id, lat, lng}: el repartidor se desvió (2 fixes > 40 m de la ruta).
    """
    event = str((payload or {}).get('event') or '').strip().lower()
    try:
        delivery_id = int((payload or {}).get('delivery_id'))
    except (TypeError, ValueError):
        raise DeliveryError("Identificador de entrega inválido.", code='invalid_delivery_id')
    if event == 'arriving':
        delivery = mark_arriving(delivery_id)
        return {'ok': True, 'status': int(delivery.status) if delivery else None}
    if event == 'reroute':
        delivery = recalculate_delivery_route(delivery_id, payload.get('lat'), payload.get('lng'))
        return {'ok': True, 'route_version': delivery.route_version}
    raise DeliveryError("Evento desconocido.", code='unknown_event')


def user_can_manage_company(user_id, company_id) -> bool:
    """ Dueño de la compañía o asistente ACTIVO de ella (lo consulta Node para `join_company_riders`). """
    try:
        company_uuid = uuid.UUID(str(company_id))
        user_uuid = uuid.UUID(str(user_id))
    except (TypeError, ValueError, AttributeError):
        return False
    from ..models import Company
    if Company.objects.filter(pk=company_uuid, owner_id=user_uuid).exists():
        return True
    return Employee.objects.filter(
        user_id=user_uuid, company_id=company_uuid, status=EmployeeStatus.ACTIVE, role=EmployeeRole.ASSISTANT,
    ).exists()


def release_active_deliveries_of_rider(emp_id, reason: str = 'rider_revoked') -> int:
    """
    Al suspender / revocar / cambiar de rol / renunciar un repartidor: devuelve a búsqueda automática sus
    entregas que aún NO retiró (ASSIGNED, ACCEPTED, AT_STORE). Las que ya van en camino se mantienen
    (el paquete está físicamente con él) y se avisa al comercio.
    """
    released = 0
    ids = list(
        DeliveryAssignment.objects.filter(rider_id=emp_id, status__in=DELIVERY_ACTIVE_STATUSES).values_list('id', flat=True)
    )
    for pk in ids:
        try:
            with transaction.atomic():
                locked = _lock_delivery(pk)
                if locked.rider_id != emp_id:
                    continue
                if int(locked.status) in (DeliveryStatus.ASSIGNED, DeliveryStatus.ACCEPTED, DeliveryStatus.AT_STORE):
                    previous_rider = locked.rider
                    _release_to_pending(locked)
                    transaction.on_commit(lambda d=locked: sync_delivery_meta(d))
                    _post_node_on_commit('delivery-status', build_status_payload(locked, {
                        'previous_rider_user_id': str(previous_rider.user_id) if previous_rider else None,
                        'reason': reason,
                    }))
                    _schedule_auto_assign(locked.id)
                    released += 1
                else:
                    _notify_merchants_on_commit(
                        locked,
                        "Repartidor sin acceso",
                        f"El repartidor de la orden N° {locked.order_id} perdió su acceso mientras llevaba el pedido.",
                        'delivery_rider_revoked',
                    )
        except DeliveryError:
            continue
        except Exception as e:
            logger.exception(f"Delivery #{pk}: error liberando entrega del repartidor {emp_id}: {e}")
    return released


def ensure_missing_delivery_assignments(limit: int = 50) -> int:
    """
    Red de seguridad: crea la entrega de órdenes DELIVERY en espera que no la tengan
    (p. ej. si falló la creación justo después del checkout).
    """
    created = 0
    orders = (
        Order.objects.filter(
            withdrawal_type=WithdrawalType.DELIVERY,
            status=OrderStatus.WAITING,
            delivery_assignment__isnull=True,
            client_location__isnull=False,
            creation__gte=timezone.now() - timedelta(hours=24),
        ).order_by('creation')[:limit]
    )
    for order in orders:
        try:
            if create_or_assign_delivery_for_order(order) is not None:
                created += 1
        except Exception as e:
            logger.exception(f"Orden {order.id}: error creando la entrega faltante: {e}")
    return created


def expire_and_retry_offers() -> dict:
    """ Tarea periódica (30 s): ofertas vencidas -> siguiente candidato; PENDING_RIDER -> reintento. """
    now = timezone.now()
    expired_ids = list(
        DeliveryAssignment.objects.filter(status=DeliveryStatus.ASSIGNED, offer_expires_at__lt=now)
        .values_list('id', flat=True)[:200]
    )
    expired = 0
    for pk in expired_ids:
        try:
            if expire_offer(pk):
                expired += 1
        except Exception as e:
            logger.exception(f"Delivery #{pk}: error expirando oferta: {e}")
    pending_ids = list(
        DeliveryAssignment.objects.filter(
            status=DeliveryStatus.PENDING_RIDER,
            created_at__gte=now - timedelta(hours=24),
            order__status__in=[OrderStatus.WAITING, OrderStatus.DELIVERY_SENT],
        ).order_by('created_at').values_list('id', flat=True)[:100]
    )
    assigned = 0
    for pk in pending_ids:
        try:
            result = auto_assign_delivery(pk)
            if result is not None and int(result.status) == DeliveryStatus.ASSIGNED:
                assigned += 1
        except Exception as e:
            logger.exception(f"Delivery #{pk}: error reintentando asignación: {e}")
    missing_created = 0
    try:
        missing_created = ensure_missing_delivery_assignments()
    except Exception as e:
        logger.exception(f"Delivery: error creando entregas faltantes: {e}")
    return {
        'expired_offers': expired, 'pending_checked': len(pending_ids), 'newly_assigned': assigned,
        'missing_assignments_created': missing_created,
    }
