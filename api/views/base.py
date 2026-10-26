"""Shared imports and helper utilities for the modular api.views package."""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import logging
import math
import re
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404

logger = logging.getLogger(__name__)
from dateutil.relativedelta import relativedelta
from rest_framework import parsers
from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from ..serializers import *
from ..models import *
from rest_framework.permissions import *
from ..core import atlas, firebase_admin
import mimetypes
from rest_framework.pagination import CursorPagination
from ..core.product_search_engine import ProductSearchEngine
from rest_framework import generics, status
from rest_framework.throttling import ScopedRateThrottle
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
import openpyxl
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
import random
import secrets
from django.contrib.auth.hashers import check_password
from ..cos import storage_manager
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from datetime import datetime, timedelta
import requests
from django.db import transaction
from ..core import *
from django.core.cache import cache
from django.utils import timezone
from ..tasks import *
from django.contrib.gis.geos import Polygon, Point
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from ..utils import parse_flexible_date, validate_venezuelan_rif_modulo11
from asgiref.sync import sync_to_async, async_to_sync
from rest_framework.pagination import PageNumberPagination
from django.db.models.functions import Coalesce, Round
from django.db.models import (
    Avg, Count, Sum, Q, F, Case, When, Value, Exists, ExpressionWrapper,
    Subquery, OuterRef, Prefetch, UUIDField, IntegerField, FloatField, BooleanField, CharField,
)
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
import operator
from functools import reduce
from django.utils.dateparse import parse_datetime
from django.db.models.functions import Cast


def _get_cached_bcv_rate(default: float = 0.0, raise_on_failure: bool = False) -> float:
    """
    Obtiene la tasa oficial del BCV desde caché en Redis (TTL 1h) o desde dolarapi.com con timeout estricto.
    """
    cache_key = "cartmaker:global:bcv_rate"
    fallback_key = "cartmaker:global:bcv_rate_fallback"
    cached_rate = cache.get(cache_key)
    if cached_rate is not None:
        return float(cached_rate)

    try:
        response = requests.get('https://ve.dolarapi.com/v1/estado', timeout=4)
        response.raise_for_status()
        data = response.json()
        api_available = data.get('estado') == 'Disponible' if data.get('estado') else False
        if api_available:
            response = requests.get('https://ve.dolarapi.com/v1/dolares/oficial', timeout=4)
            response.raise_for_status()
            data = response.json()
            rate = float(data.get('promedio', default) or default)
            if rate > 0:
                cache.set(cache_key, rate, timeout=3600)
                cache.set(fallback_key, rate, timeout=86400 * 7)
                return rate
    except Exception as e:
        print(f"Error obteniendo el precio del dolar bcv: {e}")
        fallback_rate = cache.get(fallback_key)
        if fallback_rate is not None:
            return float(fallback_rate)
        if raise_on_failure:
            raise

    fallback_rate = cache.get(fallback_key)
    if fallback_rate is not None:
        return float(fallback_rate)
    return float(default)


def _extract_and_validate_category_ids(data: dict):
    """
    Extrae y sanea la lista de IDs de categorías enviadas en el body
    ('category_ids' o 'preferred_category_ids' o 'categories').
    Retorna (is_valid: bool, clean_ids: list[int], error_msg: str | None).
    """
    raw_ids = None
    if isinstance(data, dict):
        for key in ('category_ids', 'preferred_category_ids', 'categories'):
            if key in data:
                raw_ids = data.get(key)
                break

    if raw_ids is None or not isinstance(raw_ids, (list, tuple)):
        return False, [], "Se requiere el campo 'category_ids' como una lista de IDs enteros."

    clean_ids = []
    seen = set()
    for item in raw_ids:
        try:
            cid = int(item)
            if cid > 0 and cid not in seen:
                seen.add(cid)
                clean_ids.append(cid)
        except (TypeError, ValueError):
            return False, [], f"ID de categoría inválido: {item!r}."

    return True, clean_ids, None

