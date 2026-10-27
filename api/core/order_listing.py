"""
Listados baratos de órdenes (`GET orders/` y `GET orders/merchant_orders/`).

Cada 45 s la app consulta estos endpoints como respaldo del socket, así que el costo de una consulta "sin cambios"
tiene que ser mínimo. Este módulo añade, sin romper el formato actual (`{'data': [...]}`):

1. **ETag / 304** — el ETag se calcula con UNA consulta agregada (`COUNT` + `MAX(updated_at)`) ANTES de armar el JSON.
   Si el cliente manda `If-None-Match` con el mismo valor, se responde `304 Not Modified` sin serializar nada.
   (El ETag incluye además un "bucket" de 5 min para acotar cualquier dato periférico que no toque `Order.updated_at`,
   como el nombre/logo del comercio.)
2. **Consulta incremental** — `?updated_after=<ISO8601>` devuelve solo las órdenes con `updated_at` mayor.
   La respuesta incluye `server_time` (ISO8601 UTC, capturado ANTES de consultar) para usarlo en la siguiente llamada.
   Recomendación al cliente: restar ~2 s al `server_time` guardado para tolerar relojes/commits en vuelo.
3. **Paginación opcional** — solo si llegan `page` y/o `page_size` (máx. 100). Sin esos parámetros la respuesta es
   la lista completa de siempre. Con paginación se añaden `results` (= `data`), `count`, `page`, `page_size`,
   `total_pages`, `has_next`, `next` (URL absoluta o `null`), `next_page`, `previous` y `previous_page`.
"""
import hashlib
import math
import re
import time
from datetime import datetime, timezone as dt_timezone
from typing import Optional
from urllib.parse import urlencode

from django.db.models import Count, Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response

ETAG_TIME_BUCKET_SECONDS = 300
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def parse_updated_after(raw) -> Optional[datetime]:
    """Interpreta `updated_after` (ISO8601 con o sin zona, `Z`, o epoch en segundos/milisegundos). Lanza ValueError."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.lstrip('-').replace('.', '', 1).isdigit():
        value = float(text)
        if value > 1e11:  # milisegundos
            value /= 1000.0
        return datetime.fromtimestamp(value, tz=dt_timezone.utc)
    # En una query string el "+" de "+00:00" llega como espacio: lo restauramos.
    space_offset = re.match(r'^(.*T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?) (\d{2}:\d{2})$', text)
    normalized = f"{space_offset.group(1)}+{space_offset.group(2)}" if space_offset else text
    if normalized.endswith('Z') or normalized.endswith('z'):
        normalized = normalized[:-1] + '+00:00'
    parsed = parse_datetime(normalized)
    if parsed is None:
        raise ValueError('updated_after debe ser una fecha ISO8601 válida (ej. 2026-10-27T01:00:00Z).')
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _etag_matches(header_value: str, etag: str) -> bool:
    if not header_value:
        return False
    target = etag.strip().removeprefix('W/')
    for token in header_value.split(','):
        token = token.strip()
        if token == '*':
            return True
        if token.removeprefix('W/') == target:
            return True
    return False


class OrderListing:
    """Orquesta ETag/304, `updated_after` y paginación sobre un queryset de `Order` ya filtrado por permisos."""

    def __init__(self, request, base_qs, scope: str, order_by=('-creation', '-id')):
        self.request = request
        self.base_qs = base_qs
        self.scope = scope
        self.order_by = order_by
        self.server_time = timezone.now()
        self.updated_after = None
        self.page = None
        self.page_size = None
        self.total_count = None
        self._etag = None

    # ------------------------------------------------------------------
    def _parse_params(self) -> Optional[Response]:
        params = self.request.query_params
        try:
            self.updated_after = parse_updated_after(params.get('updated_after'))
        except ValueError as exc:
            return Response({'error': str(exc), 'detail': str(exc), 'code': 'invalid_updated_after'},
                            status=status.HTTP_400_BAD_REQUEST)

        raw_page = params.get('page')
        raw_size = params.get('page_size')
        if raw_page is not None or raw_size is not None:
            try:
                self.page = max(1, int(raw_page)) if raw_page not in (None, '') else 1
                size = int(raw_size) if raw_size not in (None, '') else DEFAULT_PAGE_SIZE
                self.page_size = min(MAX_PAGE_SIZE, max(1, size))
            except (TypeError, ValueError):
                return Response({'error': 'page y page_size deben ser enteros.', 'code': 'invalid_pagination'},
                                status=status.HTTP_400_BAD_REQUEST)
        return None

    def _compute_etag(self) -> str:
        aggregate = self.base_qs.aggregate(total=Count('id'), last_update=Max('updated_at'))
        last_update = aggregate['last_update']
        raw = '|'.join([
            'orders-v1',
            self.scope,
            str(getattr(self.request.user, 'id', '')),
            self.request.META.get('QUERY_STRING', ''),
            str(aggregate['total'] or 0),
            last_update.isoformat() if last_update else '-',
            str(int(time.time() // ETAG_TIME_BUCKET_SECONDS)),
        ])
        digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()
        self.total_count = aggregate['total'] or 0
        return f'"{digest}"'

    def begin(self) -> Optional[Response]:
        """Valida parámetros y evalúa el ETag. Devuelve una `Response` (400 / 304) o `None` para continuar."""
        error = self._parse_params()
        if error is not None:
            return error
        self._etag = self._compute_etag()
        if _etag_matches(self.request.META.get('HTTP_IF_NONE_MATCH', ''), self._etag):
            response = Response(status=status.HTTP_304_NOT_MODIFIED)
            self._apply_cache_headers(response)
            return response
        return None

    def _apply_cache_headers(self, response: Response) -> Response:
        if self._etag:
            response['ETag'] = self._etag
        response['Cache-Control'] = 'private, no-cache'
        response['Vary'] = 'Authorization'
        return response

    # ------------------------------------------------------------------
    def get_orders(self):
        """Queryset ya filtrado por `updated_after`, ordenado y (si aplica) recortado a la página pedida."""
        qs = self.base_qs
        if self.updated_after is not None:
            qs = qs.filter(updated_at__gt=self.updated_after)
        qs = qs.order_by(*self.order_by)
        if self.page is not None:
            if self.updated_after is not None:
                self.total_count = qs.count()
            offset = (self.page - 1) * self.page_size
            return qs[offset: offset + self.page_size]
        return qs

    def _page_url(self, page_number: int) -> str:
        query = self.request.query_params.copy()
        query['page'] = str(page_number)
        if 'page_size' not in query:
            query['page_size'] = str(self.page_size)
        return f"{self.request.build_absolute_uri(self.request.path)}?{urlencode(list(query.items()))}"

    def build_response(self, items: list) -> Response:
        payload = {
            'data': items,
            'server_time': self.server_time.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z'),
        }
        if self.updated_after is not None:
            payload['incremental'] = True
            payload['updated_after'] = self.updated_after.astimezone(dt_timezone.utc).isoformat().replace('+00:00', 'Z')
        if self.page is not None:
            total = int(self.total_count or 0)
            total_pages = max(1, math.ceil(total / self.page_size)) if total else 1
            has_next = self.page < total_pages
            has_prev = self.page > 1
            payload.update({
                'results': items,
                'count': total,
                'page': self.page,
                'page_size': self.page_size,
                'total_pages': total_pages,
                'has_next': has_next,
                'next': self._page_url(self.page + 1) if has_next else None,
                'next_page': self.page + 1 if has_next else None,
                'previous': self._page_url(self.page - 1) if has_prev else None,
                'previous_page': self.page - 1 if has_prev else None,
            })
        return self._apply_cache_headers(Response(payload, status=status.HTTP_200_OK))
