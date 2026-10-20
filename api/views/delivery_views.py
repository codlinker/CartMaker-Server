"""
Vistas HTTP del sistema de Delivery en Tiempo Real (Fases 2, 3 y 4).

Toda la lógica de negocio, criptografía, rutas y sincronización con Redis/Node vive en
`api/core/delivery.py`; estas vistas solo traducen HTTP y aplican permisos y límites de tasa.
"""
import secrets
from rest_framework.parsers import BaseParser, JSONParser
from .base import *
from ..core.delivery import (
    DeliveryError,
    accept_delivery,
    build_bootstrap,
    complete_delivery_with_pin,
    decline_delivery,
    end_shift,
    fail_delivery,
    get_delivery_meta_for_node,
    get_rider_employee,
    get_shift_status,
    handle_node_event,
    heartbeat_shift,
    list_available_riders,
    list_rider_assignments,
    mark_arrived_store,
    mark_picked_up,
    process_ble_relay_batch,
    recalculate_delivery_route,
    resolve_viewer_role,
    start_shift,
    upload_delivery_trace,
)
from ..core.workforce import CTX_WORKER, EMP_ID_CLAIM
from ..permissions import IsDeliveryWorker, get_request_ctx, get_token_claim


def _delivery_error_response(err: DeliveryError) -> Response:
    payload = {'error': err.message}
    if err.code:
        payload['code'] = err.code
    return Response(payload, status=err.status_code)


def _truthy(raw) -> bool:
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'si', 'sí')


def _rider_from_request(request):
    emp_id = get_token_claim(request, EMP_ID_CLAIM, None)
    return get_rider_employee(emp_id)


def _optional_rider_from_request(request):
    if get_request_ctx(request) != CTX_WORKER:
        return None
    emp_id = get_token_claim(request, EMP_ID_CLAIM, None)
    if emp_id is None:
        return None
    try:
        return get_rider_employee(emp_id)
    except DeliveryError:
        return None


class RawBytesParser(BaseParser):
    """ Permite cuerpos binarios (`application/octet-stream`, `application/x-msgpack`, `application/gzip`). """
    media_type = '*/*'

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read()


####################################################
############# TURNOS DEL REPARTIDOR ################
####################################################

class DeliveryShiftStartAPI(APIView):
    """
    POST /api/v1/delivery/shift/start/
    Body: {store_id, lat, lng, battery?}
    Abre el turno del repartidor en la sucursal indicada y dispara la auto-asignación de pedidos pendientes.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request):
        try:
            employee = _rider_from_request(request)
            data = start_shift(
                employee,
                store_id=request.data.get('store_id'),
                lat=request.data.get('lat'),
                lng=request.data.get('lng'),
                battery=request.data.get('battery'),
            )
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'message': "Turno iniciado.", **data}, status=status.HTTP_200_OK)


class DeliveryShiftHeartbeatAPI(APIView):
    """
    POST /api/v1/delivery/shift/heartbeat/
    Body: {lat, lng, battery?}
    Latido de ubicación cada 60 s mientras el turno está abierto.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request):
        try:
            employee = _rider_from_request(request)
            data = heartbeat_shift(
                employee,
                lat=request.data.get('lat'),
                lng=request.data.get('lng'),
                battery=request.data.get('battery'),
            )
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response(data, status=status.HTTP_200_OK)


class DeliveryShiftEndAPI(APIView):
    """
    POST /api/v1/delivery/shift/end/
    Cierra el turno activo del repartidor y detiene la recolección de ubicación.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request):
        try:
            employee = _rider_from_request(request)
            data = end_shift(employee)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'message': "Turno cerrado.", **data}, status=status.HTTP_200_OK)


class DeliveryShiftStatusAPI(APIView):
    """
    GET /api/v1/delivery/shift/status/
    Devuelve el turno abierto (si existe) y la entrega activa del repartidor.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        try:
            employee = _rider_from_request(request)
            data = get_shift_status(employee)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response(data, status=status.HTTP_200_OK)


####################################################
########### DISPONIBILIDAD (COMERCIANTE) ###########
####################################################

class DeliveryAvailableRidersAPI(APIView):
    """
    GET /api/v1/delivery/riders/available/?store_id=<uuid>
    Lista los repartidores asignados a la sucursal con su estado en línea, turno, distancia a la tienda y carga actual.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        store_id = request.query_params.get('store_id')
        try:
            data = list_available_riders(request.user, store_id)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'data': data}, status=status.HTTP_200_OK)


####################################################
########## CICLO DE VIDA DE LA ENTREGA #############
####################################################

class DeliveryMyAssignmentsAPI(APIView):
    """
    GET /api/v1/delivery/my-assignments/?status=active|completed|all
    Lista las entregas asignadas al repartidor en sesión.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request):
        try:
            employee = _rider_from_request(request)
            items = list_rider_assignments(employee, status_filter=request.query_params.get('status') or 'active')
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'data': [d.get_json(viewer_role='rider') for d in items]}, status=status.HTTP_200_OK)


class DeliveryAcceptAPI(APIView):
    """
    POST /api/v1/delivery/<id>/accept/
    El repartidor acepta la oferta (45 s). Calcula la ruta OSRM y revela la dirección exacta del cliente.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _rider_from_request(request)
            delivery = accept_delivery(employee, delivery_id)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({
            'message': "Entrega aceptada. Dirígete a la sucursal para retirar el pedido.",
            'data': delivery.get_json(viewer_role='rider'),
        }, status=status.HTTP_200_OK)


class DeliveryDeclineAPI(APIView):
    """
    POST /api/v1/delivery/<id>/decline/
    Body opcional: {reason}
    Rechaza la oferta y pasa automáticamente al siguiente repartidor disponible.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _rider_from_request(request)
            delivery = decline_delivery(employee, delivery_id, reason=request.data.get('reason') or '')
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({
            'message': "Oferta rechazada.",
            'delivery_id': delivery.id,
            'status': int(delivery.status),
        }, status=status.HTTP_200_OK)


class DeliveryArrivedStoreAPI(APIView):
    """
    POST /api/v1/delivery/<id>/arrived_store/
    Body: {lat, lng, force?: bool}
    Marca que el repartidor llegó a la tienda (valida geocerca de 100 m salvo `force=true`).
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _rider_from_request(request)
            delivery = mark_arrived_store(
                employee,
                delivery_id,
                lat=request.data.get('lat'),
                lng=request.data.get('lng'),
                force=_truthy(request.data.get('force')),
            )
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({
            'message': "Llegada a la tienda registrada.",
            'data': delivery.get_json(viewer_role='rider'),
        }, status=status.HTTP_200_OK)


class DeliveryPickedUpAPI(APIView):
    """
    POST /api/v1/delivery/<id>/picked_up/
    Puede llamarlo el repartidor asignado o el comerciante/asistente de la tienda.
    Pasa la entrega a PICKED_UP, la orden a DELIVERY_SENT y habilita el mapa en vivo para el cliente.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _optional_rider_from_request(request)
            delivery = mark_picked_up(request.user, delivery_id, employee=employee)
        except DeliveryError as e:
            return _delivery_error_response(e)
        role = 'rider' if (employee and delivery.rider_id == employee.id) else 'merchant'
        return Response({
            'message': "Paquete retirado. Entrega en camino al cliente.",
            'data': delivery.get_json(viewer_role=role),
        }, status=status.HTTP_200_OK)


class DeliveryCompleteWithPinAPI(APIView):
    """
    POST /api/v1/delivery/<id>/deliver/
    Body online:  {pin, lat?, lng?, fix_time?}
    Body offline: {pin, lat, lng, t_ms, offline_signature}
    Verifica el PIN de 4 dígitos del cliente y pasa automáticamente la orden a COMPLETED.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _rider_from_request(request)
            result = complete_delivery_with_pin(
                employee,
                delivery_id,
                pin=request.data.get('pin'),
                lat=request.data.get('lat'),
                lng=request.data.get('lng'),
                fix_time=request.data.get('fix_time'),
                t_ms=request.data.get('t_ms'),
                offline_signature=request.data.get('offline_signature'),
            )
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({
            'message': "¡Entrega completada exitosamente!",
            **result,
        }, status=status.HTTP_200_OK)


class DeliveryFailAPI(APIView):
    """
    POST /api/v1/delivery/<id>/fail/
    Body: {reason}
    Reporta una incidencia o libera la entrega si aún no fue retirada de la tienda.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _optional_rider_from_request(request)
            delivery = fail_delivery(request.user, delivery_id, reason=request.data.get('reason'), employee=employee)
        except DeliveryError as e:
            return _delivery_error_response(e)
        role = 'rider' if (employee and delivery.rider_id == employee.id) else 'merchant'
        return Response({
            'message': "Estado de entrega actualizado.",
            'data': delivery.get_json(viewer_role=role),
        }, status=status.HTTP_200_OK)


class DeliveryRerouteAPI(APIView):
    """
    POST /api/v1/delivery/<id>/reroute/
    Body: {lat?, lng?, force?: bool}
    Recalcula la ruta OSRM desde la posición actual del repartidor e incrementa `route_version`.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _rider_from_request(request)
            delivery = recalculate_delivery_route(
                delivery_id,
                from_lat=request.data.get('lat'),
                from_lng=request.data.get('lng'),
                force=_truthy(request.data.get('force')),
                employee=employee,
            )
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({
            'message': "Ruta recalculada.",
            'data': delivery.get_json(viewer_role='rider'),
        }, status=status.HTTP_200_OK)


####################################################
###### TIEMPO REAL, BUFFER OFFLINE Y BLE RELAY #####
####################################################

class DeliveryBootstrapAPI(APIView):
    """
    GET /api/v1/delivery/<id>/bootstrap/
    Devuelve la entrega (filtrada por privacidad según el rol), la ruta `polyline6` con `cum_dist` y `cum_time`,
    el ancla actual del filtro de Kalman, la hora del servidor y — solo para el repartidor — `rider_secrets`.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get(self, request, delivery_id: int):
        ctx = get_request_ctx(request)
        emp_id = get_token_claim(request, EMP_ID_CLAIM, None)
        try:
            data = build_bootstrap(request.user, delivery_id, ctx=ctx, emp_id=emp_id)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'data': data}, status=status.HTTP_200_OK)


class DeliveryTraceUploadAPI(APIView):
    """
    POST /api/v1/delivery/<id>/trace/
    Acepta cuerpo binario (`msgpack+gzip` o `msgpack`) o JSON `{"points": [...]}`.
    Une y deduplica con el stream en vivo de Redis, persiste `DeliveryTrace` y emite `delivery_trace_backfill`.
    """
    permission_classes = [IsAuthenticated, IsDeliveryWorker]
    parser_classes = [JSONParser, RawBytesParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_rider'

    def post(self, request, delivery_id: int):
        try:
            employee = _rider_from_request(request)
            content_type = request.content_type or ''
            if isinstance(request.data, (bytes, bytearray)):
                raw_body = bytes(request.data)
            elif isinstance(request.data, (dict, list)):
                raw_body = json.dumps(request.data).encode('utf-8')
                content_type = 'application/json'
            else:
                raw_body = bytes(request.body or b'')
            result = upload_delivery_trace(employee, delivery_id, raw_body, content_type=content_type)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'message': "Traza sincronizada.", **result}, status=status.HTTP_200_OK)


class DeliveryBleRelayAPI(APIView):
    """
    POST /api/v1/delivery/relay/
    Body: {"items": [{"packet": "<hex o base64 de 24 B>", "rssi"?: -72, "observed_at"?: 1729390000}]}
    Cualquier usuario autenticado puede retransmitir anuncios BLE cercanos. No se guarda la ubicación del retransmisor.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'delivery_relay'

    def post(self, request):
        items = request.data.get('items')
        if items is None:
            items = request.data.get('packets')
        try:
            stats = process_ble_relay_batch(request.user, items)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'message': "Lote BLE procesado.", **stats}, status=status.HTTP_200_OK)


####################################################
###### ENDPOINTS INTERNOS (NODE_CHAT_SERVER) #######
####################################################

def _has_valid_microservice_token(request) -> bool:
    token = request.headers.get('X-Microservice-Token') or ''
    secret = getattr(settings, 'SECRET_KEY', '') or ''
    return bool(token and secret and secrets.compare_digest(str(token), str(secret)))


class DeliveryInternalMetaAPI(APIView):
    """
    GET /api/v1/delivery/internal/meta/<id>/
    Uso exclusivo de `node_chat_server` cuando `dlv:{id}:meta` expiró en Redis.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, delivery_id: int):
        if not _has_valid_microservice_token(request):
            return Response({'error': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            meta = get_delivery_meta_for_node(delivery_id)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response({'data': meta}, status=status.HTTP_200_OK)


class DeliveryInternalNodeEventAPI(APIView):
    """
    POST /api/v1/delivery/internal/node-event/
    Body: {event: 'arriving'|'reroute', delivery_id, lat?, lng?}
    Uso exclusivo de `node_chat_server`.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not _has_valid_microservice_token(request):
            return Response({'error': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            result = handle_node_event(request.data)
        except DeliveryError as e:
            return _delivery_error_response(e)
        return Response(result, status=status.HTTP_200_OK)
