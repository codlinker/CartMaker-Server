import json
import math
import re
import base64
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import sync_to_async
from django.contrib.gis.measure import D

from ..models import SubCategory, AtlasThread, AtlasMessage, InventoryItem, ProductViewLog, CompanyStore, TokenWallet
from .product_search_engine import ProductSearchEngine
from .catalog_taxonomy import render_catalog_for_prompt
from .ve_geo import describe_zone

# =========================================================================
# 🛠️ ESQUEMAS DE HERRAMIENTAS (TOOLS) - ATLAS 2.0 (OPENAI / OPENROUTER)
# =========================================================================

def _get_tools_schema() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "buscar_productos_inventario",
                "description": (
                    "Motor principal de búsqueda de productos, tiendas, ofertas y categorías en CartMaker Venezuela. "
                    "Soporta búsqueda por texto, categoría, comercio/centro comercial, atributos dinámicos (tallas, peso, capacidad), "
                    "tiendas abiertas ahora (delivery/retiro inmediato), ofertas relámpago y descuentos por tokens. "
                    "🚨 REGLA: Si el usuario pide algo general ('productos con delivery inmediato', 'qué hay abierto ahorita', "
                    "'ofertas hoy', 'dónde gasto mis tokens'), deja `query` vacío ('') y activa los filtros booleanos correspondientes. "
                    "Si expresa una necesidad ('tengo calor', 'tengo hambre'), invoca esta herramienta EN PARALELO con 2 a 4 productos concretos."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "1 o 2 sustantivos del producto en singular (ej. 'hamburguesa', 'caucho', 'harina'). "
                                "Déjalo vacío '' si el usuario solo pide explorar tiendas abiertas, delivery inmediato, ofertas o una categoría completa."
                            ),
                        },
                        "categoria": {
                            "type": "string",
                            "description": "Filtro opcional por categoría o subcategoría del catálogo (ej. 'Alimentos y Bebidas', 'Calzado', 'Farmacia', 'Celulares')."
                        },
                        "comercio_o_centro_comercial": {
                            "type": "string",
                            "description": "Filtro opcional por nombre de tienda, marca comercial o centro comercial (ej. 'Sambil', 'DonAmigo')."
                        },
                        "atributo_o_variante": {
                            "type": "string",
                            "description": "Filtro opcional por talla, presentación, peso, marca o especificación (ej. 'talla 42', '500g', '256gb', 'sin gluten')."
                        },
                        "unidad_venta": {
                            "type": "string",
                            "enum": ["unit", "kg", "g", "lb", "l", "ml", "pack", "box", "portion", "combo", "pair", "set"],
                            "description": "Filtro opcional por unidad de venta ('kg', 'g', 'unit', 'portion', 'combo', 'pair')."
                        },
                        "precio_min_usd": {
                            "type": "number",
                            "description": "Precio mínimo en USD si el usuario lo especificó."
                        },
                        "precio_max_usd": {
                            "type": "number",
                            "description": "Precio máximo o tope en USD si el usuario dijo 'menos de $X' o 'máximo $X'."
                        },
                        "solo_abiertos_ahora": {
                            "type": "boolean",
                            "description": "true si el usuario pide delivery inmediato, comprar ahorita mismo, urgencia o locales abiertos."
                        },
                        "solo_ofertas": {
                            "type": "boolean",
                            "description": "true si el usuario busca promociones, descuentos o rebajas activas."
                        },
                        "solo_con_descuento_tokens": {
                            "type": "boolean",
                            "description": "true si el usuario pregunta dónde usar sus tokens o qué productos tienen descuento por puntos/tokens."
                        },
                        "solo_en_centro_comercial": {
                            "type": "boolean",
                            "description": "true si el usuario quiere tiendas ubicadas dentro de un centro comercial (mall)."
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["best", "cheap", "nearby", "quality"],
                            "description": "'cheap' (más económico), 'nearby' (más cercano/rápido), 'quality' (mejor reputación/Platinum), 'best' (balance óptimo)."
                        },
                        "max_distancia": {
                            "type": "number",
                            "description": "Radio inicial en metros. Default 15000.0 (15 km)."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "armar_lista_o_receta",
                "description": (
                    "ÚSALA OBLIGATORIAMENTE cuando el usuario quiera cocinar un plato ('quiero hacer pabellón', 'hacer hallacas', 'una parrilla'), "
                    "hacer mercado con varios productos, armar un combo para una ocasión (cumpleaños, reunión, desayuno familiar) "
                    "o comprar varios artículos dentro de un presupuesto ('tengo $20 para resolver el almuerzo'). "
                    "El motor consolida la compra en la menor cantidad de tiendas, traza la ruta geográfica y prepara el carrito en 1 toque."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "titulo_plan": {
                            "type": "string",
                            "description": "Título atractivo del combo, receta o lista (ej. 'Ruta para Pabellón Criollo', 'Combo Parrilla Fin de Semana')."
                        },
                        "items": {
                            "type": "array",
                            "description": "Lista de ingredientes o productos específicos a conseguir.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Nombre genérico del producto en singular (ej. 'carne mechada', 'caraota', 'arroz', 'plátano')."},
                                    "cantidad": {"type": "string", "description": "Cantidad sugerida o pedida (ej. '500g', '1 kg', '2 unidades')."}
                                },
                                "required": ["query"]
                            }
                        },
                        "presupuesto_max_usd": {
                            "type": "number",
                            "description": "Presupuesto máximo total en USD si el usuario indicó un límite de dinero."
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["best", "cheap", "nearby"],
                            "description": "Prioridad del armado: 'cheap' (máximo ahorro), 'nearby' (menor recorrido), 'best' (equilibrio)."
                        },
                        "max_distancia": {
                            "type": "number",
                            "description": "Radio de búsqueda en metros. Default 15000.0."
                        }
                    },
                    "required": ["items"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "sugerir_productos_relacionados",
                "description": "Obtiene complementos basados en telemetría de compras cruzadas para un artículo específico (UUID).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "UUID del InventoryItem de referencia."
                        }
                    },
                    "required": ["item_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "explorar_feed_personalizado",
                "description": (
                    "Descubre productos destacados cerca del usuario según su perfil de gustos, ofertas del día o tiendas abiertas. "
                    "Úsala cuando el usuario pida 'sorpréndeme', 'qué me recomiendas hoy' o 'qué hay de bueno por aquí'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "enfoque": {
                            "type": "string",
                            "enum": ["parati", "ofertas", "abiertos_cerca", "mis_tokens"],
                            "description": "Enfoque del descubrimiento."
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "responder_conversacion",
                "description": (
                    "Úsala ÚNICAMENTE para saludos puros ('hola'), agradecimientos ('gracias') o dudas sobre cómo usar la app "
                    "que NO involucren buscar productos, tiendas, ofertas, precios ni ubicaciones."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []}
            }
        },
    ]


class AtlasManager:
    ORIGIN_USER = 1
    ORIGIN_AI = 2

    def __init__(self, user_lat: float = 0.0, user_lng: float = 0.0, user_locations: list = None, user: Any = None, seed: str = 'default'):
        if not hasattr(settings, 'OPENROUTER_API_KEY') or not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY no está configurada en settings.py")

        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": getattr(settings, 'DOMAIN', "http://localhost:8000"),
                "X-Title": "CartMaker App"
            }
        )

        self.model_name = getattr(settings, 'ATLAS_MODEL', 'google/gemini-2.5-flash')
        self.user_lat = float(user_lat or 0.0)
        self.user_lng = float(user_lng or 0.0)
        self.user_locations = user_locations or []
        self.user = user
        self.seed = seed

        catalog_text = render_catalog_for_prompt()

        # System Prompt optimizado para respuestas ejecutivas ultrarrápidas y bajo consumo de tokens
        self.chat_system_instruction = f"""
# ROL E IDENTIDAD CORE (ATLAS 2.0)
Eres 'Atlas', el motor de inteligencia comercial y espacial de CartMaker en Venezuela.
El frontend de CartMaker renderiza automáticamente un escenario visual interactivo (mapa en vivo, rutas 3D, tarjetas con precios, variantes, videos de 30s y botones de compra en 1 toque) a partir de los datos que retornan tus herramientas.
Por eso, tu respuesta de texto debe ser una SÍNTESIS EJECUTIVA ÁGIL (2 a 4 oraciones máximo): directa, inteligente y conversacional, sin repetir en listas largas lo que el usuario ya ve en las tarjetas interactivas.

# TONO Y REGLAS DE ORO
- Español venezolano natural, moderno, educado y resolutivo ("te cuadré", "de una", "chévere", "fino").
- PROHIBIDO llamar al usuario: mi pana, convive, mano, compa, hermano o bro.
- VERACIDAD ABSOLUTA: jamás inventes productos, tiendas, precios, ofertas, tokens ni horarios. Solo menciona datos presentes en el retorno de la herramienta de ESTE turno.
- PROHIBIDO mencionar distancias numéricas (metros, m, kilómetros, km). Ubica siempre a los comercios por su nombre de sector, urbanización, ciudad o Centro Comercial (con su piso si aparece).

# DEDUCCIÓN INTELIGENTE EN UN SOLO TURNO (CERO PREGUNTAS INNECESARIAS)
Catálogo oficial (Categorías y Subcategorías):
{catalog_text}

1. Si el usuario pide "productos con delivery inmediato cerca", "qué está abierto ahorita", "ofertas cerca" o "dónde uso mis tokens":
   -> Llama a `buscar_productos_inventario` con `query=""` y activa `solo_abiertos_ahora=true`, `solo_ofertas=true` o `solo_con_descuento_tokens=true` según corresponda. NUNCA pongas la palabra 'delivery' o 'abierto' dentro de `query`.
2. Si el usuario expresa una necesidad o problema ("tengo calor", "tengo hambre", "se fue la luz", "me duele la cabeza", "regalo para mi mamá"):
   -> Deduce de inmediato 2 a 4 productos concretos y llama a `buscar_productos_inventario` EN PARALELO en el mismo turno.
3. Si el usuario quiere cocinar un plato ("pabellón", "empanadas", "parrilla"), hacer mercado, cubrir un evento o ajustar varios productos a un presupuesto ("tengo $20"):
   -> Llama a `armar_lista_o_receta` con los ingredientes/artículos y `presupuesto_max_usd` si aplica.
4. Si la herramienta indica `transicion_zona` (no había stock en su zona actual pero sí se consiguió en una de sus ubicaciones guardadas o en otra zona cercana):
   -> Menciona con naturalidad que en su zona actual no había stock pero ya le moviste el radar hacia la zona donde sí hay disponibilidad.
5. Si el producto tiene descuento desbloqueable con los tokens del usuario (`token_deal`) o video reel (`reel:sí`), destácalo en una frase corta porque eso le ahorra dinero real o le permite ver el producto en video.
""".strip()

    # =========================================================================
    # EJECUCIÓN DE HERRAMIENTAS Y AUTO-RESOLUCIÓN MULTI-ZONA
    # =========================================================================

    def _execute_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        raw_query = (args.get('query') or '').strip()
        max_dist = float(args.get('max_distancia') or 15000.0)
        mode = args.get('mode') or 'best'

        filter_kwargs = {
            'category_query': args.get('categoria'),
            'company_or_store_query': args.get('comercio_o_centro_comercial'),
            'attribute_or_variant_query': args.get('atributo_o_variante'),
            'selling_unit': args.get('unidad_venta'),
            'min_price': args.get('precio_min_usd'),
            'max_price': args.get('precio_max_usd'),
            'only_open_now': bool(args.get('solo_abiertos_ahora', False)),
            'only_offers': bool(args.get('solo_ofertas', False)),
            'only_token_discounts': bool(args.get('solo_con_descuento_tokens', False)),
            'mall_only': bool(args.get('solo_en_centro_comercial', False)),
        }

        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)
        origin_zone_name = describe_zone(self.user_lat, self.user_lng)

        # Si no hay query ni filtros específicos, activamos modo descubrimiento inteligente (abiertos/cercanos)
        has_any_filter = any(v for v in filter_kwargs.values() if v is not False and v is not None and v != '')
        if not raw_query and not has_any_filter:
            filter_kwargs['only_open_now'] = True
            if mode == 'best':
                mode = 'nearby'

        explicit_small_radius = 'max_distancia' in args and max_dist < 15000.0
        if explicit_small_radius:
            candidates = engine.search_purchase_candidates(
                query=raw_query,
                max_distance_meters=max_dist,
                limit=6,
                location_label="Tu ubicación actual",
                mode=mode,
                **filter_kwargs,
            )
            search_outcome = {'results': candidates, 'expanded': False, 'origin_zone': origin_zone_name}
        else:
            search_outcome = engine.search_purchase_expanding(
                query=raw_query,
                base_radius_meters=max_dist,
                limit=6,
                location_label="Tu ubicación actual",
                mode=mode,
                **filter_kwargs,
            )

        if search_outcome['results']:
            response = {
                "type": "results",
                "data": search_outcome['results'],
                "places": dict(engine.purchase_places),
                "applied_filters": {k: v for k, v in filter_kwargs.items() if v},
            }
            if search_outcome.get('expanded'):
                first_item = search_outcome['results'][0]
                dest_coords = first_item.get('store_coordinates') or {}
                response["expansion"] = {
                    "origin_zone": search_outcome.get('origin_zone') or origin_zone_name,
                    "found_zone": search_outcome.get('found_zone'),
                    "nearest_distance_meters": search_outcome.get('nearest_distance_meters'),
                    "searched_radius_meters": search_outcome.get('searched_radius_meters'),
                    "base_radius_meters": max_dist,
                    "zones_by_item": search_outcome.get('zones_by_item', {}),
                }
                response["zone_transition"] = {
                    "occurred": True,
                    "transition_type": "EXPANDED_GEOGRAPHIC_RING",
                    "origin_zone": {
                        "lat": self.user_lat,
                        "lng": self.user_lng,
                        "label": "Tu ubicación actual",
                        "zone_name": search_outcome.get('origin_zone') or origin_zone_name,
                    },
                    "destination_zone": {
                        "lat": dest_coords.get('lat'),
                        "lng": dest_coords.get('lng'),
                        "label": search_outcome.get('found_zone') or "Zona cercana",
                        "zone_name": search_outcome.get('found_zone'),
                        "distance_from_origin_meters": search_outcome.get('nearest_distance_meters'),
                    },
                    "camera_flight_suggested": True,
                }
            return response

        # 2. AUTO-RESOLUCIÓN EN UBICACIONES GUARDADAS DEL USUARIO (Sin pedir confirmación [Sí/No])
        fallback_results = []
        fallback_places = {}
        matched_saved_loc = None

        for loc in self.user_locations:
            try:
                loc_lat = float(loc.get('latitude', 0.0))
                loc_lng = float(loc.get('longitude', 0.0))
            except (ValueError, TypeError):
                continue
            loc_name = loc.get('name', 'Ubicación guardada')

            if abs(loc_lat - self.user_lat) < 0.001 and abs(loc_lng - self.user_lng) < 0.001:
                continue

            eng_fb = ProductSearchEngine(lat=loc_lat, lng=loc_lng, user=self.user, seed=self.seed)
            fb_candidates = eng_fb.search_purchase_candidates(
                query=raw_query,
                max_distance_meters=max_dist,
                limit=4,
                location_label=loc_name,
                mode=mode,
                **filter_kwargs,
            )
            if fb_candidates:
                if matched_saved_loc is None:
                    matched_saved_loc = {
                        "lat": loc_lat,
                        "lng": loc_lng,
                        "label": loc_name,
                        "zone_name": describe_zone(loc_lat, loc_lng),
                    }
                fallback_results.extend(fb_candidates)
                fallback_places.update(eng_fb.purchase_places)
                if len(fallback_results) >= 6:
                    break

        if fallback_results:
            return {
                "type": "results",
                "data": fallback_results,
                "places": fallback_places,
                "applied_filters": {k: v for k, v in filter_kwargs.items() if v},
                "zone_transition": {
                    "occurred": True,
                    "transition_type": "SAVED_USER_LOCATION",
                    "origin_zone": {
                        "lat": self.user_lat,
                        "lng": self.user_lng,
                        "label": "Tu ubicación actual",
                        "zone_name": origin_zone_name,
                    },
                    "destination_zone": matched_saved_loc,
                    "camera_flight_suggested": True,
                },
            }

        # 3. Telemetría de Demanda Insatisfecha
        search_label = raw_query or filter_kwargs.get('category_query') or ''
        if search_label:
            try:
                from django.core.cache import cache
                redis_conn = cache.client.get_client()
                redis_conn.rpush("telemetry:unmet_demand", json.dumps({
                    'client_id': str(self.user.id) if self.user and self.user.is_authenticated else None,
                    'search_term': search_label,
                    'lat': self.user_lat,
                    'lng': self.user_lng,
                    'timestamp': timezone.now().isoformat()
                }))
            except Exception as e:
                print(f"[ATLAS TELEMETRY ERROR]: {e}")

        return {
            "type": "not_found",
            "query": search_label,
            "origin_zone": origin_zone_name,
            "message": f"Cero existencias para '{search_label or 'esa búsqueda'}' en {origin_zone_name} ni en tus ubicaciones guardadas."
        }

    @staticmethod
    def _format_place_label(place: Optional[Dict[str, Any]]) -> str:
        """Texto compacto de ubicación en nombres de zona/ciudad/centro comercial; nunca cifras de distancia."""
        if not place:
            return ""
        parts = []
        if place.get('zone'):
            parts.append(f"Zona:{place['zone']}")
        if place.get('address'):
            parts.append(f"Dir:{place['address'][:45]}")
        if place.get('proximity'):
            parts.append(f"Cercanía:{place['proximity']}")
        mall_label = AtlasManager._format_mall_label(place)
        if mall_label:
            parts.append(f"En:{mall_label}")
        return (" | " + " | ".join(parts)) if parts else ""

    @staticmethod
    def _format_mall_label(place: Optional[Dict[str, Any]]) -> Optional[str]:
        """'Centro Comercial Sambil Chacao, piso 2' o None si la tienda no está en un centro comercial."""
        if not place or not place.get('mall_name'):
            return None
        label = f"Centro Comercial {place['mall_name']}"
        if place.get('mall_floor') is not None:
            label += f", piso {place['mall_floor']}"
        return label

    def _execute_shopping_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        needs = args.get('items', [])
        mode = args.get('mode', 'best')
        max_dist = float(args.get('max_distancia', 15000.0))
        budget_usd = args.get('presupuesto_max_usd')
        bundle_title = (args.get('titulo_plan') or 'Plan de Compra Inteligente').strip()

        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)
        plan = engine.resolve_shopping_list(
            needs=needs,
            max_distance_meters=max_dist,
            location_label="Tu ubicación actual",
            mode=mode,
            budget_usd=budget_usd,
        )
        plan['bundle_title'] = bundle_title
        plan['places'] = dict(engine.purchase_places)
        return plan

    def _execute_recommendations(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        item_id = args.get('item_id')
        if not item_id:
            return []

        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)
        time_horizon = timezone.now() - timedelta(days=14)
        buyers = ProductViewLog.objects.filter(
            inventory_item_id=item_id, start_time__gte=time_horizon
        ).filter(Q(added_to_cart=True) | Q(bought=True)).values_list('client_id', flat=True).distinct()

        recommended_ids = list(
            ProductViewLog.objects.filter(
                client_id__in=list(buyers), start_time__gte=time_horizon
            ).filter(Q(added_to_cart=True) | Q(bought=True)).exclude(
                inventory_item_id=item_id
            ).values('inventory_item_id').annotate(
                co_occurrence=Count('id')
            ).order_by('-co_occurrence').values_list('inventory_item_id', flat=True)[:4]
        )

        qs = engine._get_base_active_queryset()
        qs = engine._annotate_proximity_flag(qs)
        qs = engine._annotate_merchant_rating(qs)
        qs = qs.select_related(
            'product', 'product__category', 'product__category__parent_category',
            'product__company', 'store', 'store__location', 'store__location__mall', 'store__company'
        )

        items = []
        if recommended_ids:
            items = list(qs.filter(id__in=recommended_ids)[:4])

        if not items:
            try:
                base_item = InventoryItem.objects.select_related('product').get(id=item_id)
                items = list(
                    qs.filter(product__category_id=base_item.product.category_id)
                    .exclude(id=item_id)
                    .order_by('-cached_popularity_score')[:4]
                )
            except Exception:
                items = []

        light_records = [engine._build_purchase_light_record(it, []) for it in items]
        scored = engine._score_purchase_payloads(light_records, mode='best')
        return engine._batch_enrich_finalists(scored, location_label="Tu ubicación actual", query="")

    def _execute_personalized_feed(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        enfoque = (args.get('enfoque') or 'parati').strip().lower()
        engine = ProductSearchEngine(lat=self.user_lat, lng=self.user_lng, user=self.user, seed=self.seed)

        if enfoque == 'ofertas':
            return engine.search_purchase_candidates(
                query="", max_distance_meters=15000.0, limit=6, only_offers=True, mode='cheap'
            )
        if enfoque == 'abiertos_cerca':
            return engine.search_purchase_candidates(
                query="", max_distance_meters=10000.0, limit=6, only_open_now=True, mode='nearby'
            )
        if enfoque == 'mis_tokens':
            return engine.search_purchase_candidates(
                query="", max_distance_meters=15000.0, limit=6, only_user_redeemable_tokens=True, mode='best'
            )

        favorite_category_ids = []
        if self.user and self.user.is_authenticated:
            time_horizon = timezone.now() - timedelta(days=30)
            recent_views = ProductViewLog.objects.filter(
                client=self.user,
                start_time__gte=time_horizon
            ).values('inventory_item__product__category_id').annotate(
                interactions=Count('id')
            ).order_by('-interactions')[:3]
            favorite_category_ids = [
                item['inventory_item__product__category_id']
                for item in recent_views
                if item['inventory_item__product__category_id']
            ]
            if not favorite_category_ids:
                pref_parent_ids = self.user.get_preferred_category_ids()
                if pref_parent_ids:
                    favorite_category_ids = list(
                        SubCategory.objects.filter(parent_category_id__in=pref_parent_ids).values_list('id', flat=True)
                    )

        qs = engine._get_base_active_queryset()
        qs = engine._annotate_proximity_flag(qs)
        qs = engine._annotate_merchant_rating(qs)
        qs = qs.select_related(
            'product', 'product__category', 'product__category__parent_category',
            'product__company', 'store', 'store__location', 'store__location__mall', 'store__company'
        ).filter(store__location__coordinates__distance_lte=(engine.user_location, D(m=15000.0)))

        picked_items = []
        if favorite_category_ids:
            picked_items = list(qs.filter(product__category_id__in=favorite_category_ids).order_by('-cached_popularity_score')[:5])
            if len(picked_items) < 5:
                exclude_ids = [p.id for p in picked_items]
                picked_items.extend(list(qs.exclude(id__in=exclude_ids).order_by('-cached_popularity_score')[:5 - len(picked_items)]))
        else:
            picked_items = list(qs.order_by('-cached_popularity_score')[:5])

        light_records = [engine._build_purchase_light_record(it, []) for it in picked_items]
        scored = engine._score_purchase_payloads(light_records, mode='best')
        return engine._batch_enrich_finalists(scored, location_label="Tu ubicación actual", query="")

    # =========================================================================
    # 🎬 MOTOR DE ORQUESTACIÓN DE EXPERIENCIA Y ANIMACIONES (ATLAS 2.0)
    # =========================================================================

    def _build_atlas_experience(
        self,
        user_text: str,
        injected_products: List[Dict[str, Any]],
        smart_bundle: Optional[Dict[str, Any]],
        zone_transition: Optional[Dict[str, Any]],
        tools_used: List[str],
        applied_filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Construye determinísticamente en Python (0 tokens de LLM) el paquete completo
        de telemetría espacial, rutas, comparativas, reels de video, tokens y directivas
        cinemáticas para que el frontend de Flutter pueda ejecutar animaciones y experiencias
        dinámicas de otro nivel.
        """
        origin_zone = describe_zone(self.user_lat, self.user_lng)
        now_local = timezone.localtime(timezone.now())

        # 1. Consolidar `stores_map` (tiendas únicas participantes, ordenadas por distancia/relevancia)
        stores_by_id: Dict[str, Dict[str, Any]] = {}
        video_reels: List[Dict[str, Any]] = []
        seen_video_ids = set()
        total_unlockable_savings_usd = 0.0
        total_tokens_earnable = 0
        stores_with_user_tokens = []

        for item in injected_products:
            st_id = str(item.get('store_id') or '')
            if not st_id:
                continue
            coords = item.get('store_coordinates') or {}
            loc_details = item.get('store_location_details') or {}
            tok_opp = item.get('token_opportunity') or {}
            eff_price = float(item.get('effective_price') or 0.0)

            total_tokens_earnable += int(item.get('tokens_earned_on_purchase') or 0)
            if tok_opp.get('best_tier_affordable'):
                total_unlockable_savings_usd = round(
                    total_unlockable_savings_usd + float(tok_opp['best_tier_affordable'].get('savings_usd') or 0.0),
                    2,
                )

            vid = item.get('associated_video_story')
            if isinstance(vid, dict) and vid.get('video_id') and vid['video_id'] not in seen_video_ids:
                seen_video_ids.add(vid['video_id'])
                video_reels.append({
                    **vid,
                    'product_item_id': str(item.get('id')),
                    'product_name': (item.get('product') or {}).get('name'),
                    'effective_price': eff_price,
                    'store_id': st_id,
                    'store_name': item.get('store_name'),
                })

            slot = stores_by_id.get(st_id)
            if not slot:
                user_bal = int(item.get('user_wallet_balance') or 0)
                slot = {
                    'store_id': st_id,
                    'store_name': item.get('store_name'),
                    'company_id': str(item.get('company_id') or (item.get('product') or {}).get('company_id') or ''),
                    'company_name': item.get('company_name'),
                    'company_image': item.get('company_image'),
                    'store_img_url': loc_details.get('store_img_url'),
                    'lat': coords.get('lat'),
                    'lng': coords.get('lng'),
                    'distance_meters': item.get('distance_meters'),
                    'bearing_degrees': item.get('bearing_degrees'),
                    'cardinal_direction': item.get('cardinal_direction'),
                    'estimated_travel': item.get('estimated_travel'),
                    'zone': loc_details.get('zone'),
                    'address': loc_details.get('address'),
                    'reference_details': loc_details.get('reference_details'),
                    'proximity_label': loc_details.get('proximity_label'),
                    'is_mall': bool(loc_details.get('is_mall')),
                    'mall_id': loc_details.get('mall_id'),
                    'mall_name': loc_details.get('mall_name'),
                    'mall_floor': loc_details.get('mall_floor'),
                    'store_type': loc_details.get('store_type'),
                    'store_type_label': loc_details.get('store_type_label'),
                    'is_open_now': bool(item.get('is_open_now')),
                    'work_hours': item.get('work_hours'),
                    'work_days': item.get('work_days'),
                    'is_platinum': bool(item.get('is_platinum')),
                    'merchant_avg_rating': float(item.get('merchant_avg_rating') or 0.0),
                    'merchant_rating_count': int(item.get('merchant_rating_count') or 0),
                    'contact_methods': item.get('contact_methods') or {},
                    'user_wallet_balance': user_bal,
                    'gamification_enabled': bool(tok_opp.get('gamification_enabled')),
                    'tokens_per_dollar': int(tok_opp.get('tokens_per_dollar') or 0),
                    'matched_items_count': 0,
                    'matched_item_ids': [],
                    'matched_items_preview': [],
                    'subtotal_in_store_usd': 0.0,
                }
                stores_by_id[st_id] = slot
                if user_bal > 0:
                    stores_with_user_tokens.append({
                        'store_id': st_id,
                        'store_name': slot['store_name'],
                        'company_name': slot['company_name'],
                        'user_tokens': user_bal,
                    })

            slot['matched_items_count'] += 1
            slot['matched_item_ids'].append(str(item.get('id')))
            slot['subtotal_in_store_usd'] = round(slot['subtotal_in_store_usd'] + eff_price, 2)
            if len(slot['matched_items_preview']) < 4:
                prod_data = item.get('product') or {}
                slot['matched_items_preview'].append({
                    'item_id': str(item.get('id')),
                    'name': prod_data.get('name'),
                    'price_usd': eff_price,
                    'unit_label': prod_data.get('unit_label', 'und'),
                    'image': (prod_data.get('images') or [None])[0],
                    'atlas_badges': item.get('atlas_badges') or [],
                })

        stores_map = sorted(
            stores_by_id.values(),
            key=lambda s: (
                -int(s['matched_items_count']),
                float(s['distance_meters'] if s['distance_meters'] is not None else 999999.0),
            ),
        )
        for idx, st in enumerate(stores_map, start=1):
            st['rank_index'] = idx

        # 2. Comparativa Instantánea (`comparison_highlights`)
        comparison_highlights = None
        if injected_products:
            prices = [float(p.get('effective_price') or 0.0) for p in injected_products if p.get('effective_price') is not None]
            avg_price = round(sum(prices) / len(prices), 2) if prices else 0.0
            min_price = min(prices) if prices else 0.0
            max_price = max(prices) if prices else 0.0

            cheapest_item = min(injected_products, key=lambda p: float(p.get('effective_price') or 999999.0))
            open_items = [p for p in injected_products if p.get('is_open_now') and p.get('distance_meters') is not None]
            nearest_open_item = (
                min(open_items, key=lambda p: float(p.get('distance_meters') or 999999.0))
                if open_items else None
            )
            token_ready_items = [
                p for p in injected_products
                if (p.get('token_opportunity') or {}).get('best_tier_affordable')
            ]
            best_token_item = (
                max(
                    token_ready_items,
                    key=lambda p: float((p.get('token_opportunity') or {}).get('best_tier_affordable', {}).get('savings_usd') or 0.0),
                )
                if token_ready_items else None
            )
            best_rated_item = max(
                injected_products,
                key=lambda p: max(float(p.get('avg_rating') or 0.0), float(p.get('merchant_avg_rating') or 0.0)),
            )

            savings_vs_avg_pct = (
                round(((avg_price - float(cheapest_item.get('effective_price') or 0)) / avg_price) * 100, 1)
                if avg_price > 0 else 0.0
            )

            comparison_highlights = {
                'price_spread': {
                    'min_usd': round(min_price, 2),
                    'max_usd': round(max_price, 2),
                    'avg_usd': avg_price,
                    'candidates_count': len(injected_products),
                    'stores_count': len(stores_map),
                },
                'cheapest_option': {
                    'item_id': str(cheapest_item.get('id')),
                    'name': (cheapest_item.get('product') or {}).get('name'),
                    'effective_price': float(cheapest_item.get('effective_price') or 0.0),
                    'unit_label': (cheapest_item.get('product') or {}).get('unit_label', 'und'),
                    'store_id': str(cheapest_item.get('store_id')),
                    'store_name': cheapest_item.get('store_name'),
                    'company_name': cheapest_item.get('company_name'),
                    'distance_meters': cheapest_item.get('distance_meters'),
                    'is_open_now': bool(cheapest_item.get('is_open_now')),
                    'savings_vs_average_pct': max(0.0, savings_vs_avg_pct),
                },
                'nearest_open_option': {
                    'item_id': str(nearest_open_item.get('id')),
                    'name': (nearest_open_item.get('product') or {}).get('name'),
                    'effective_price': float(nearest_open_item.get('effective_price') or 0.0),
                    'store_id': str(nearest_open_item.get('store_id')),
                    'store_name': nearest_open_item.get('store_name'),
                    'company_name': nearest_open_item.get('company_name'),
                    'distance_meters': nearest_open_item.get('distance_meters'),
                    'estimated_travel': nearest_open_item.get('estimated_travel'),
                    'store_coordinates': nearest_open_item.get('store_coordinates'),
                } if nearest_open_item else None,
                'best_token_deal': {
                    'item_id': str(best_token_item.get('id')),
                    'name': (best_token_item.get('product') or {}).get('name'),
                    'store_id': str(best_token_item.get('store_id')),
                    'store_name': best_token_item.get('store_name'),
                    'user_wallet_balance': best_token_item.get('user_wallet_balance'),
                    'tier': (best_token_item.get('token_opportunity') or {}).get('best_tier_affordable'),
                } if best_token_item else None,
                'best_rated_option': {
                    'item_id': str(best_rated_item.get('id')),
                    'name': (best_rated_item.get('product') or {}).get('name'),
                    'store_id': str(best_rated_item.get('store_id')),
                    'store_name': best_rated_item.get('store_name'),
                    'rating': max(float(best_rated_item.get('avg_rating') or 0.0), float(best_rated_item.get('merchant_avg_rating') or 0.0)),
                    'is_platinum': bool(best_rated_item.get('is_platinum')),
                },
            }

        # 3. Selección determinista de `ui_mode` y `cinematic_directive` (Animaciones para Flutter)
        if "responder_conversacion" in tools_used and not injected_products:
            ui_mode = "CONVERSATIONAL"
            animation_type = "IDLE_PULSE"
        elif not injected_products:
            ui_mode = "ZERO_RESULTS_RADAR"
            animation_type = "RADAR_EXPAND_EMPTY"
        elif smart_bundle and smart_bundle.get('items_plan'):
            ui_mode = "SMART_BUNDLE_PLANNER"
            animation_type = "BUNDLE_STACK_ASSEMBLE" if len(smart_bundle.get('route_stops', [])) <= 1 else "ROUTE_PATH_DRAW"
        elif zone_transition and zone_transition.get('occurred'):
            ui_mode = "PRODUCT_RADAR"
            animation_type = "MAP_FLIGHT_TELEPORT"
        elif applied_filters.get('only_offers') or applied_filters.get('only_token_discounts') or total_unlockable_savings_usd > 0:
            ui_mode = "DEAL_AND_TOKEN_HUNTER"
            animation_type = "TOKEN_COIN_BURST" if total_unlockable_savings_usd > 0 else "DEAL_SPOTLIGHT_GLOW"
        elif applied_filters.get('only_open_now') and not (applied_filters.get('query')):
            ui_mode = "STORE_EXPLORER"
            animation_type = "RADAR_PULSE_AND_PIN_DROP"
        elif len(stores_map) >= 2 and comparison_highlights and (
            comparison_highlights['price_spread']['max_usd'] - comparison_highlights['price_spread']['min_usd'] >= 1.0
        ):
            ui_mode = "PRICE_VERSUS"
            animation_type = "VERSUS_SPLIT_CARD"
        else:
            ui_mode = "PRODUCT_RADAR"
            animation_type = "RADAR_PULSE_AND_PIN_DROP"

        # 4. Construcción de `camera_keyframes` y `route_polyline_points` para animaciones de mapa 3D
        valid_coords = [
            (float(s['lat']), float(s['lng']))
            for s in stores_map
            if s.get('lat') is not None and s.get('lng') is not None
        ]
        if valid_coords:
            all_lats = [c[0] for c in valid_coords] + ([self.user_lat] if self.user_lat else [])
            all_lngs = [c[1] for c in valid_coords] + ([self.user_lng] if self.user_lng else [])
            bounding_box = {
                'min_lat': round(min(all_lats), 6),
                'max_lat': round(max(all_lats), 6),
                'min_lng': round(min(all_lngs), 6),
                'max_lng': round(max(all_lngs), 6),
                'center_lat': round(sum(all_lats) / len(all_lats), 6),
                'center_lng': round(sum(all_lngs) / len(all_lngs), 6),
            }
        else:
            bounding_box = None

        primary_store = stores_map[0] if stores_map else None
        primary_item = injected_products[0] if injected_products else None

        camera_keyframes = [
            {
                'step': 1,
                'action': 'START_AT_USER_ORIGIN',
                'lat': self.user_lat,
                'lng': self.user_lng,
                'zoom': 14.5,
                'pitch': 0.0,
                'bearing': 0.0,
                'duration_ms': 600,
                'label': 'Tu ubicación actual',
            }
        ]
        route_polyline_points = [
            {
                'lat': self.user_lat,
                'lng': self.user_lng,
                'label': 'Tu ubicación',
                'stop_type': 'USER_ORIGIN',
                'stop_number': 0,
            }
        ]

        if zone_transition and zone_transition.get('occurred'):
            dest_z = zone_transition.get('destination_zone') or {}
            if dest_z.get('lat') is not None and dest_z.get('lng') is not None:
                camera_keyframes.append({
                    'step': len(camera_keyframes) + 1,
                    'action': 'TELEPORT_TO_DESTINATION_ZONE',
                    'lat': dest_z['lat'],
                    'lng': dest_z['lng'],
                    'zoom': 14.0,
                    'pitch': 35.0,
                    'bearing': 0.0,
                    'duration_ms': 1400,
                    'label': dest_z.get('label') or 'Zona encontrada',
                })

        stops_source = (smart_bundle.get('route_stops') if smart_bundle else None) or stores_map[:3]
        for idx, st in enumerate(stops_source, start=1):
            st_lat = st.get('lat') if 'lat' in st else (st.get('store_coordinates') or {}).get('lat')
            st_lng = st.get('lng') if 'lng' in st else (st.get('store_coordinates') or {}).get('lng')
            if st_lat is None or st_lng is None:
                continue
            camera_keyframes.append({
                'step': len(camera_keyframes) + 1,
                'action': 'FOCUS_STORE_PIN' if idx == 1 else 'FLY_TO_NEXT_STOP',
                'store_id': str(st.get('store_id')),
                'lat': st_lat,
                'lng': st_lng,
                'zoom': 16.5 if idx == 1 else 15.8,
                'pitch': 50.0,
                'bearing': float(st.get('bearing_degrees') or 0.0),
                'duration_ms': 1100,
                'label': f"{st.get('store_name')} ({st.get('company_name')})",
            })
            route_polyline_points.append({
                'lat': st_lat,
                'lng': st_lng,
                'store_id': str(st.get('store_id')),
                'label': st.get('store_name'),
                'company_name': st.get('company_name'),
                'stop_type': 'STORE_STOP',
                'stop_number': idx,
            })

        # 5. Mood & Theme dinámico según hora e intención
        if total_unlockable_savings_usd > 0 or applied_filters.get('only_offers'):
            mood_theme = "SAVINGS_GOLD"
        elif applied_filters.get('only_open_now'):
            mood_theme = "URGENT_OPEN_NOW"
        elif smart_bundle:
            mood_theme = "BUNDLE_CHEF"
        elif now_local.hour >= 20 or now_local.hour < 6:
            mood_theme = "NIGHT_OWL"
        else:
            archetype = ((primary_item or {}).get('product') or {}).get('category_archetype', 'general')
            mood_theme = "FRESH_MARKET" if archetype in ('fresh_produce', 'prepared_food', 'packaged_grocery') else "STANDARD"

        cinematic_directive = {
            'animation_type': animation_type,
            'auto_play': bool(injected_products),
            'mood_theme': mood_theme,
            'primary_focus_store_id': str(primary_store['store_id']) if primary_store else None,
            'primary_focus_item_id': str(primary_item['id']) if primary_item else None,
            'origin_coordinates': {
                'lat': self.user_lat,
                'lng': self.user_lng,
                'zone': origin_zone,
            },
            'target_bounding_box': bounding_box,
            'camera_keyframes': camera_keyframes,
            'route_polyline_points': route_polyline_points,
        }

        # 6. Generación de `quick_actions` (Chips interactivos de 1 toque para cero esfuerzo del usuario)
        quick_actions = []
        if primary_store and primary_store.get('lat') is not None:
            quick_actions.append({
                'id': f"route_{primary_store['store_id']}",
                'type': 'ANIMATE_MAP_ROUTE',
                'label': f"📍 Ir a {primary_store['store_name']}",
                'icon': 'map_pin',
                'payload': {
                    'store_id': primary_store['store_id'],
                    'store_name': primary_store['store_name'],
                    'company_name': primary_store['company_name'],
                    'lat': primary_store['lat'],
                    'lng': primary_store['lng'],
                    'bearing_degrees': primary_store.get('bearing_degrees'),
                    'estimated_travel': primary_store.get('estimated_travel'),
                    'is_mall': primary_store.get('is_mall'),
                    'mall_name': primary_store.get('mall_name'),
                    'mall_floor': primary_store.get('mall_floor'),
                },
            })

        if smart_bundle and smart_bundle.get('one_tap_cart_batches'):
            quick_actions.append({
                'id': 'one_tap_bundle',
                'type': 'ONE_TAP_ADD_BUNDLE',
                'label': f"🛒 Armar carrito (${smart_bundle.get('estimated_total_usd', 0):.2f})",
                'icon': 'shopping_Bag',
                'payload': {
                    'bundle_title': smart_bundle.get('bundle_title'),
                    'estimated_total_usd': smart_bundle.get('estimated_total_usd'),
                    'batches': smart_bundle.get('one_tap_cart_batches'),
                },
            })

        if video_reels:
            first_reel = video_reels[0]
            quick_actions.append({
                'id': f"reel_{first_reel['video_id']}",
                'type': 'PLAY_VIDEO_REEL',
                'label': f"🎬 Ver video en vivo ({int(round(first_reel.get('duration_seconds') or 15))}s)",
                'icon': 'play_circle',
                'payload': first_reel,
            })

        if comparison_highlights and comparison_highlights.get('best_token_deal'):
            td = comparison_highlights['best_token_deal']
            tier = td.get('tier') or {}
            quick_actions.append({
                'id': f"token_{td['item_id']}",
                'type': 'APPLY_TOKEN_DISCOUNT',
                'label': f"🪙 Canjear {tier.get('tokens')} tokens (-{int(tier.get('percentage', 0))}%)",
                'icon': 'coin',
                'payload': td,
            })

        if len(injected_products) > 1:
            if not applied_filters.get('only_open_now'):
                quick_actions.append({
                    'id': 'filter_open_now',
                    'type': 'SEND_ATLAS_PROMPT',
                    'label': '🟢 Solo abiertos ahorita',
                    'icon': 'clock',
                    'payload': {'prompt': 'Muéstrame de esos cuáles están abiertos ahorita mismo'},
                })
            quick_actions.append({
                'id': 'sort_cheapest',
                'type': 'SEND_ATLAS_PROMPT',
                'label': '💸 El más económico',
                'icon': 'tag',
                'payload': {'prompt': '¿Cuál de estas opciones me sale más económica?'},
            })

        return {
            'version': '2.0',
            'ui_mode': ui_mode,
            'cinematic_directive': cinematic_directive,
            'stores_map': stores_map,
            'comparison_highlights': comparison_highlights,
            'smart_bundle': {
                'bundle_title': smart_bundle.get('bundle_title'),
                'primary_store': smart_bundle.get('primary_store'),
                'items_plan': smart_bundle.get('items_plan'),
                'route_stops': smart_bundle.get('route_stops'),
                'one_tap_cart_batches': smart_bundle.get('one_tap_cart_batches'),
                'missing_queries': smart_bundle.get('missing_queries'),
                'estimated_total_usd': smart_bundle.get('estimated_total_usd'),
                'estimated_total_with_tokens_usd': smart_bundle.get('estimated_total_with_tokens_usd'),
                'total_token_savings_usd': smart_bundle.get('total_token_savings_usd'),
                'budget_usd': smart_bundle.get('budget_usd'),
                'within_budget': smart_bundle.get('within_budget'),
                'budget_remaining_usd': smart_bundle.get('budget_remaining_usd'),
            } if smart_bundle else None,
            'video_reels': video_reels,
            'token_opportunities': {
                'total_unlockable_savings_usd': total_unlockable_savings_usd,
                'total_tokens_earnable_in_turn': total_tokens_earnable,
                'stores_with_user_balance': stores_with_user_tokens,
            },
            'zone_transition': zone_transition,
            'quick_actions': quick_actions,
        }

    # =========================================================================
    # CHAT LOOP ASÍNCRONO (BAJO CONSUMO DE TOKENS + ALTA RIQUEZA DE DATOS)
    # =========================================================================

    @sync_to_async
    def _get_thread_history(self, thread_id: int) -> List[Dict[str, Any]]:
        messages = AtlasMessage.objects.filter(conversation_id=thread_id).order_by('-creation')[:6]
        messages = list(messages)[::-1]

        history = [{"role": "system", "content": self.chat_system_instruction}]

        ubicaciones_str = "\n".join([
            f"- {loc.get('name', 'Ubicación')}: {describe_zone(float(loc.get('latitude', 0.0)), float(loc.get('longitude', 0.0)))}"
            for loc in self.user_locations
            if loc.get('latitude') is not None and loc.get('longitude') is not None
        ]) if self.user_locations else "- Solo ubicación actual en vivo."

        now_local = timezone.localtime(timezone.now())
        dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        if now_local.hour < 11:
            momento = 'mañana (desayuno)'
        elif now_local.hour < 15:
            momento = 'mediodía (almuerzo)'
        elif now_local.hour < 19:
            momento = 'tarde (merienda)'
        else:
            momento = 'noche (cena)'

        history.append({
            "role": "system",
            "content": (
                f"CONTEXTO USUARIO: Zona actual={describe_zone(self.user_lat, self.user_lng)}. "
                f"Ubicaciones guardadas:\n{ubicaciones_str}\n"
                f"Hora local: {dias[now_local.weekday()]} {now_local.strftime('%I:%M %p')} ({momento})."
            )
        })

        for msg in messages:
            role = 'user' if msg.origin == self.ORIGIN_USER else 'assistant'
            content = msg.text[:900] if len(msg.text) > 900 else msg.text
            history.append({"role": role, "content": content})

        return history

    @sync_to_async
    def _save_message(self, thread_id: int, origin: int, text: str, product_ids: List[str] = None, action_command: dict = None) -> AtlasMessage:
        return AtlasMessage.objects.create(
            conversation_id=thread_id,
            origin=origin,
            text=text,
            product_ids=product_ids or [],
            action_command=action_command
        )

    @staticmethod
    def _data_tools_schema() -> List[Dict[str, Any]]:
        """Herramientas que consultan datos reales (todas menos la conversacional)."""
        return [t for t in _get_tools_schema() if t["function"]["name"] != "responder_conversacion"]

    _COMMERCE_CLAIM_PATTERN = re.compile(
        r"(\$\s?\d)|(\b\d+(?:[.,]\d+)?\s?(?:km|kil[oó]metros?|metros)\b)|(\b\d+\s?m\b)|(platinum)|(abiert[oa]\s+(?:ahora|ahorita))",
        re.IGNORECASE,
    )

    _UNIT = r"(?:km|kil[oó]metros?|metros|mts|m)"
    _TAIL = r"(?:\s+de\s+(?:tu\s+ubicaci[oó]n(?:\s+actual)?|ti|tu\s+zona|aqu[ií]|distancia))?"
    _DISTANCE_PHRASE_PATTERN = re.compile(
        "|".join([
            r"\s*\(\s*(?:a\s+|unos\s+)?\d+(?:[.,]\d+)?\s?" + _UNIT + r"\s*\)",
            r"\s+a\s+(?:unos\s+|unas\s+)?\d+(?:[.,]\d+)?\s?" + _UNIT + r"\b" + _TAIL,
            r"\s+(?:unos\s+|unas\s+)?\d+(?:[.,]\d+)?\s?(?:km|kil[oó]metros?)\b" + _TAIL,
        ]),
        re.IGNORECASE,
    )
    _KM_WORD_PATTERN = re.compile(r"\bkm\b|kil[oó]metros?", re.IGNORECASE)

    def _mentions_distance_units(self, text: Optional[str]) -> bool:
        return bool(text and (self._DISTANCE_PHRASE_PATTERN.search(text) or self._KM_WORD_PATTERN.search(text)))

    def _scrub_distance_phrases(self, text: str) -> str:
        """Elimina determinísticamente en 0ms (sin gastar tokens extra de LLM) cualquier frase de distancia numérica."""
        if not text:
            return ""
        cleaned = self._DISTANCE_PHRASE_PATTERN.sub("", text)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        return re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    def _claims_commerce_data(self, text: Optional[str]) -> bool:
        """True si el texto afirma precios, distancias, Platinum o estado abierto."""
        return bool(text and self._COMMERCE_CLAIM_PATTERN.search(text))

    async def _create_completion(self, history: list, thread_id: int, tools: list, tool_choice: str, temperature: float):
        """Llama al LLM; si el proveedor rechaza tool_choice='required', degrada a 'auto'."""
        kwargs = dict(
            model=self.model_name,
            messages=history,
            tools=tools,
            temperature=temperature,
            extra_body={"session_id": f"cartmaker-atlas-thread-{thread_id}"},
        )
        try:
            return await self.client.chat.completions.create(tool_choice=tool_choice, **kwargs)
        except Exception as e:
            if tool_choice == "required":
                print(f"[ATLAS] tool_choice='required' no soportado, usando 'auto': {e}")
                return await self.client.chat.completions.create(tool_choice="auto", **kwargs)
            raise

    @classmethod
    def _format_compact_candidate_for_llm(cls, it: Dict[str, Any], place: Optional[Dict[str, Any]]) -> str:
        """
        Serialización ultra-compacta para Gemini (~25 tokens por producto en lugar de ~130).
        Conserva todos los hechos que Gemini necesita mencionar mientras ahorra ~70% de tokens de entrada.
        """
        prod = it.get('product') or {}
        triad = it.get('triad') or {}
        p_name = prod.get('name', 'Artículo')
        unit_lbl = prod.get('unit_label', 'und')
        p_price = triad.get('price_usd', it.get('effective_price'))
        p_open = "ABIERTO" if triad.get('open_now') else "CERRADO"
        p_plat = " [Platinum]" if triad.get('platinum') else ""
        p_off = f" [-{triad.get('offer_pct')}%]" if triad.get('offer_pct') else ""

        tok_opp = it.get('token_opportunity') or {}
        best_tok = tok_opp.get('best_tier_affordable')
        tok_str = (
            f" | TokenDeal: usuario tiene {it.get('user_wallet_balance')}T -> -{int(best_tok['percentage'])}% (${best_tok['final_price_usd']})"
            if best_tok else (f" | Gana {it.get('tokens_earned_on_purchase')}T" if it.get('tokens_earned_on_purchase') else "")
        )
        reel_str = " | Reel30s:sí" if it.get('associated_video_story') else ""
        var_str = f" | Variante:{it['matched_variant'].get('name')}" if it.get('matched_variant') else ""

        m_rating = triad.get('merchant_rating', 0.0)
        m_count = triad.get('merchant_reviews_count', 0)
        rep_str = f"{m_rating}★({m_count})" if m_count > 0 else "Nuevo"

        return (
            f"• {p_name} (${p_price}/{unit_lbl}{p_off}{var_str}) en '{it.get('store_name')}' "
            f"({it.get('company_name')}{p_plat}) | {p_open} | Rep:{rep_str}{tok_str}{reel_str}"
            f"{cls._format_place_label(place)}"
        )

    async def send_chat_message_async(self, thread_id: int, user_text: str, image_base64: str = None) -> Dict[str, Any]:
        try:
            history = await self._get_thread_history(thread_id)
            await self._save_message(thread_id, self.ORIGIN_USER, user_text, [])

            if image_base64:
                forced_instruction = (
                    "\n\n[INSTRUCCIÓN VISUAL: Analiza la imagen adjunta. "
                    "Si muestra una lista de compras, receta, factura o varios artículos distintos, ejecuta `armar_lista_o_receta`. "
                    "Si muestra un producto específico (o repuesto, prenda, medicamento, comida), ejecuta `buscar_productos_inventario` "
                    "con su nombre y atributos visibles]."
                )
                history.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text + forced_instruction},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                })
            else:
                history.append({"role": "user", "content": user_text})

            response = await self._create_completion(
                history, thread_id, _get_tools_schema(), tool_choice="required", temperature=0.2
            )

            choice = response.choices[0]
            injected_products: List[Dict[str, Any]] = []
            smart_bundle_result: Optional[Dict[str, Any]] = None
            zone_transition_result: Optional[Dict[str, Any]] = None
            applied_filters_accum: Dict[str, Any] = {}
            tools_used: List[str] = []
            data_tool_used = False

            for _attempt in range(2):
                while choice.message.tool_calls:
                    tool_calls = choice.message.tool_calls
                    history.append(choice.message)

                    for tool_call in tool_calls:
                        fn_name = tool_call.function.name
                        tools_used.append(fn_name)
                        try:
                            fn_args = json.loads(tool_call.function.arguments or "{}")
                        except ValueError:
                            fn_args = {}
                        tool_payload = {}
                        if fn_name != "responder_conversacion":
                            data_tool_used = True

                        # 1. Búsqueda Inteligente / Por Filtros Estructurados
                        if fn_name == "buscar_productos_inventario":
                            db_res = await sync_to_async(self._execute_search)(fn_args)
                            if db_res.get("applied_filters"):
                                applied_filters_accum.update(db_res["applied_filters"])
                            if fn_args.get("query"):
                                applied_filters_accum["query"] = fn_args.get("query")

                            if db_res.get("type") == "results":
                                items = db_res["data"]
                                existing_ids = {str(p.get('id')) for p in injected_products}
                                for item in items:
                                    if str(item.get('id')) not in existing_ids:
                                        injected_products.append(item)
                                        existing_ids.add(str(item.get('id')))

                                places = db_res.get("places", {})
                                formatted_data = [
                                    self._format_compact_candidate_for_llm(it, places.get(str(it.get('id'))))
                                    for it in items
                                ]
                                tool_payload = {"status": "ok", "resultados": formatted_data}

                                z_trans = db_res.get("zone_transition")
                                if z_trans and z_trans.get("occurred"):
                                    zone_transition_result = z_trans
                                    orig_lbl = (z_trans.get("origin_zone") or {}).get("zone_name")
                                    dest_lbl = (z_trans.get("destination_zone") or {}).get("label")
                                    tool_payload["transicion_zona"] = (
                                        f"Sin stock en {orig_lbl}; encontrado automáticamente en '{dest_lbl}'. "
                                        "Coméntalo en 1 frase natural sin usar cifras de distancia."
                                    )
                            else:
                                tool_payload = {"status": "empty", "msg": db_res.get("message")}

                        # 2. Armar Receta, Combo o Lista de Compras
                        elif fn_name == "armar_lista_o_receta":
                            plan = await sync_to_async(self._execute_shopping_list)(fn_args)
                            smart_bundle_result = plan

                            for item in plan.get('injected', []):
                                if str(item.get('id')) not in {str(p.get('id')) for p in injected_products}:
                                    injected_products.append(item)

                            store_info = plan.get('primary_store')
                            plan_places = plan.get('places', {})
                            primary_store_id = str(store_info.get('store_id')) if store_info else None
                            primary_place = {}
                            if primary_store_id:
                                for found in plan.get('found', []):
                                    if str(found.get('store_id')) == primary_store_id:
                                        primary_place = plan_places.get(str(found.get('id'))) or {}
                                        break

                            tool_payload = {
                                "status": "ok",
                                "plan": {
                                    "titulo": plan.get("bundle_title"),
                                    "tienda_principal": store_info.get('store_name') if store_info else "Varias tiendas",
                                    "zona_tienda_principal": primary_place.get('zone'),
                                    "centro_comercial": self._format_mall_label(primary_place),
                                    "cubiertos_en_principal": f"{store_info.get('items_in_store', 0)}/{store_info.get('needs_total', 0)}" if store_info else "0",
                                    "paradas_totales": len(plan.get('route_stops', [])),
                                    "completados_en_otra_parada": [
                                        f"{x.get('item_name')} en {x.get('store_name')}"
                                        for x in plan.get('filled_elsewhere', [])
                                    ],
                                    "sin_stock": plan.get('missing_queries', []),
                                    "total_usd": plan.get('estimated_total_usd', 0.0),
                                    "total_con_tokens_usd": plan.get('estimated_total_with_tokens_usd', 0.0),
                                    "dentro_presupuesto": plan.get('within_budget', True),
                                }
                            }

                        # 3. Feed Personalizado / Descubrimiento
                        elif fn_name == "explorar_feed_personalizado":
                            db_products = await sync_to_async(self._execute_personalized_feed)(fn_args)
                            for p in db_products:
                                if str(p.get('id')) not in {str(x.get('id')) for x in injected_products}:
                                    injected_products.append(p)
                            tool_payload = {
                                "status": "ok" if db_products else "empty",
                                "resultados": [
                                    self._format_compact_candidate_for_llm(p, p.get('store_location_details'))
                                    for p in db_products
                                ]
                            }

                        # 3.5 Conversación pura
                        elif fn_name == "responder_conversacion":
                            tool_payload = {
                                "status": "ok",
                                "nota": "Saluda o responde brevemente sin inventar productos ni tiendas.",
                            }

                        # 4. Sugerencias Cruzadas
                        elif fn_name == "sugerir_productos_relacionados":
                            db_recs = await sync_to_async(self._execute_recommendations)(fn_args)
                            for p in db_recs:
                                if str(p.get('id')) not in {str(x.get('id')) for x in injected_products}:
                                    injected_products.append(p)
                            tool_payload = {
                                "status": "ok" if db_recs else "empty",
                                "resultados": [
                                    self._format_compact_candidate_for_llm(p, p.get('store_location_details'))
                                    for p in db_recs
                                ]
                            }

                        print(f"[ATLAS 2.0 TOOL] {fn_name}({fn_args}) -> {tool_payload.get('status')} | items={len(injected_products)}")
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": json.dumps(tool_payload, ensure_ascii=False)
                        })

                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=history,
                        tools=_get_tools_schema(),
                        temperature=0.35,
                        extra_body={"session_id": f"cartmaker-atlas-thread-{thread_id}"}
                    )
                    choice = response.choices[0]

                if (
                    data_tool_used
                    or _attempt == 1
                    or not self._claims_commerce_data(choice.message.content)
                ):
                    break

                # Guardia anti-alucinación
                history.append({
                    "role": "system",
                    "content": (
                        "CORRECCIÓN: mencionaste datos comerciales sin invocar herramientas en este turno. "
                        "Ejecuta la herramienta correspondiente ahora."
                    ),
                })
                response = await self._create_completion(
                    history, thread_id, self._data_tools_schema(), tool_choice="required", temperature=0.2
                )
                choice = response.choices[0]

            ai_final_text = self._scrub_distance_phrases(choice.message.content or "")
            if not data_tool_used and self._claims_commerce_data(ai_final_text):
                ai_final_text = (
                    "Ahorita no pude consultar el inventario en vivo. "
                    "¿Me confirmas qué producto buscas para rastrearlo de una?"
                )

            # Construir el paquete de orquestación espacial y de UI (`atlas_experience`)
            atlas_experience = self._build_atlas_experience(
                user_text=user_text,
                injected_products=injected_products,
                smart_bundle=smart_bundle_result,
                zone_transition=zone_transition_result,
                tools_used=tools_used,
                applied_filters=applied_filters_accum,
            )

            # `action_command` preserva compatibilidad y transporta `atlas_experience` para persistencia en BD
            action_command = {
                "action": atlas_experience["ui_mode"],
                "ui_mode": atlas_experience["ui_mode"],
                "cinematic_directive": atlas_experience["cinematic_directive"],
                "quick_actions": atlas_experience["quick_actions"],
                "atlas_experience": atlas_experience,
            }

            p_ids = [str(p['id']) for p in injected_products if 'id' in p]
            saved_msg = await self._save_message(thread_id, self.ORIGIN_AI, ai_final_text, p_ids, action_command)

            # Telemetría solo con cuenta autenticada
            if injected_products and self.user and self.user.is_authenticated:
                now = timezone.now()
                logs = [
                    ProductViewLog(
                        inventory_item_id=p['id'],
                        client_id=self.user.id,
                        start_time=now,
                        origin_source='atlas',
                        search_prompt=user_text[:150],
                        atlas_message_id=saved_msg.id
                    )
                    for p in injected_products if 'id' in p
                ]
                await sync_to_async(ProductViewLog.objects.bulk_create)(logs, ignore_conflicts=True)

            return {
                "success": True,
                "response": ai_final_text,
                "message_id": saved_msg.id,
                "injected_products": injected_products,
                "action_command": action_command,
                "atlas_experience": atlas_experience,
                "zero_results_refund_eligible": bool(data_tool_used and not injected_products),
            }

        except Exception as e:
            print(f"❌ [ATLAS CRITICAL ERROR]: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": "Atlas está optimizando sus rutas de inventario. Intenta de nuevo en unos segundos."}

    # =========================================================================
    # RECONOCIMIENTO VISUAL Y EXCEL (VISIÓN Y DATOS)
    # =========================================================================

    @sync_to_async
    def _get_available_subcategories(self) -> List[Dict[str, Any]]:
        from api.core.category_schemas import get_subcategory_schema

        items = []
        for s in SubCategory.objects.select_related('parent_category').all():
            schema = get_subcategory_schema(
                subcategory_name=s.name,
                parent_category_name=s.parent_category.name,
            )
            items.append({
                "id": s.id,
                "name": f"{s.parent_category.name} - {s.name}",
                "subcategory_name": s.name,
                "parent_category_id": s.parent_category_id,
                "parent_category_name": s.parent_category.name,
                "default_unit": schema.get("default_selling_unit", "unit"),
                "allowed_units": schema.get("allowed_selling_unit_codes", ["unit"]),
                "attribute_keys": [f["key"] for f in schema.get("fields", []) if isinstance(f, dict) and f.get("key")],
                "supports_variants": bool(schema.get("supports_variants", True)),
                "supports_modifier_groups": bool(schema.get("supports_modifier_groups", False)),
            })
        return items

    def _parse_gemini_json_response(
        self,
        text_response: str,
        subcats_map: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        from api.core.category_schemas import (
            get_subcategory_schema,
            validate_and_normalize_product_dynamic_data,
        )

        if not text_response:
            return {"products": [], "error": "Respuesta vacía."}
        try:
            clean = text_response.strip()
            if clean.startswith('```json'):
                clean = clean[7:]
            if clean.startswith('```'):
                clean = clean[3:]
            if clean.endswith('```'):
                clean = clean[:-3]
            res = json.loads(clean.strip(), strict=False)
            if "products" in res and isinstance(res["products"], list):
                fallback_sub = next(iter(subcats_map.values()), None) if subcats_map else None
                for prod in res["products"]:
                    if not isinstance(prod, dict):
                        continue
                    if "description" in prod and isinstance(prod["description"], str):
                        prod["description"] = re.sub(r'(?<!\n)\n(?!\n)', '\n\n', prod["description"]).strip()

                    sub_id = prod.get("subcategory_id") or prod.get("category_id") or prod.get("category")
                    sub_info = None
                    if subcats_map and sub_id is not None:
                        try:
                            sub_info = subcats_map.get(int(sub_id))
                        except (ValueError, TypeError):
                            sub_info = None
                    if sub_info is None and fallback_sub is not None:
                        sub_info = fallback_sub

                    resolved_sub_id = sub_info["id"] if sub_info else sub_id
                    sub_name = sub_info["subcategory_name"] if sub_info else None
                    cat_id = sub_info["parent_category_id"] if sub_info else None
                    cat_name = sub_info["parent_category_name"] if sub_info else None

                    try:
                        base_price_val = max(0.0, float(prod.get("price", 0.0) or 0.0))
                    except (ValueError, TypeError):
                        base_price_val = 0.0
                    prod["price"] = round(base_price_val, 2)

                    dyn = validate_and_normalize_product_dynamic_data(
                        prod,
                        subcategory_name=sub_name,
                        category_name=cat_name,
                        base_price=base_price_val,
                    )
                    prod["subcategory_id"] = resolved_sub_id
                    prod["category_id"] = resolved_sub_id
                    prod["subcategory_name"] = sub_name or ""
                    prod["parent_category_id"] = cat_id
                    prod["parent_category_name"] = cat_name or ""
                    prod["selling_unit"] = dyn["selling_unit"]
                    prod["unit_label"] = dyn["unit_label"]
                    prod["allow_fractional_quantity"] = dyn["allow_fractional_quantity"]
                    prod["min_order_quantity"] = dyn["min_order_quantity"]
                    prod["unit_step"] = dyn["unit_step"]
                    prod["attributes"] = dyn["attributes"]
                    prod["variants"] = dyn["variants"]
                    prod["modifier_groups"] = dyn["modifier_groups"]
                    prod["product_schema"] = get_subcategory_schema(
                        subcategory_name=sub_name,
                        parent_category_name=cat_name,
                    )
            return res
        except json.JSONDecodeError:
            return {"products": [], "error": "Atlas no pudo interpretar el formato de los datos."}

    @staticmethod
    def _build_vision_catalog_prompt(subcats_for_llm: List[Dict[str, Any]], multi_mode: bool = False) -> str:
        mode_instruction = (
            "Analiza la imagen comercial (estante, vitrina, menú, factura o foto con varios artículos) "
            "y detecta TODOS los productos distintos visibles."
            if multi_mode
            else "Analiza la imagen comercial y extrae el producto o los productos visibles con el máximo nivel de detalle."
        )
        return (
            f"{mode_instruction}\n"
            "Para cada producto detectado:\n"
            "1. Elige el `subcategory_id` exacto del catálogo oficial.\n"
            "2. Elige `selling_unit` dentro de las `allowed_units` de esa subcategoría "
            "(ej. 'kg' o 'g' para frutas/verduras/carnes/charcutería por peso; 'pair' para calzado; "
            "'portion' o 'combo' para comida preparada; 'unit' o 'pack' para empaquetados).\n"
            "3. Completa `attributes` usando las claves de `attribute_keys` de esa subcategoría que puedas "
            "deducir visualmente del empaque, etiqueta o producto (ej. marca, contenido_neto, modelo, condicion, "
            "genero, tipo_prenda, tela_material, tipo_fresco, estado_conservacion, etc.).\n"
            "4. Si en la foto se aprecian tallas, colores, capacidades o presentaciones con precios distintos, "
            "inclúyelas en `variants` como `[{\"name\": \"...\", \"options\": {...}, \"price\": 0.0, \"stock\": null}]`.\n"
            "5. Si es comida preparada, snacks, charcutería o frescos donde aplican opciones de preparación/corte/maduración "
            "o contornos/extras visibles, puedes sugerirlos en `modifier_groups`.\n"
            "6. Si el precio es visible en la imagen, colócalo en `price` (número); de lo contrario usa `0.0`.\n\n"
            "Responde ÚNICAMENTE con JSON válido bajo este formato exacto:\n"
            "{\n"
            "  \"products\": [\n"
            "    {\n"
            "      \"name\": \"Nombre claro y comercial del producto\",\n"
            "      \"description\": \"Descripción comercial atractiva y detallada\",\n"
            "      \"price\": 0.0,\n"
            "      \"subcategory_id\": 1,\n"
            "      \"selling_unit\": \"unit\",\n"
            "      \"attributes\": {},\n"
            "      \"variants\": [],\n"
            "      \"modifier_groups\": []\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Catálogo oficial de subcategorías y sus campos: {json.dumps(subcats_for_llm, ensure_ascii=False)}"
        )

    async def analyze_image_for_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        subcats = await self._get_available_subcategories()
        subcats_for_llm = [
            {
                "id": s["id"],
                "name": s["name"],
                "default_unit": s["default_unit"],
                "allowed_units": s["allowed_units"],
                "attribute_keys": s["attribute_keys"],
            }
            for s in subcats
        ]
        subcats_map = {s["id"]: s for s in subcats}
        prompt = self._build_vision_catalog_prompt(subcats_for_llm, multi_mode=False)
        b64 = base64.b64encode(image_data).decode('utf-8')
        res = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}]}],
            temperature=0.25
        )
        return self._parse_gemini_json_response(res.choices[0].message.content, subcats_map=subcats_map)

    async def analyze_image_for_multiple_products_async(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        subcats = await self._get_available_subcategories()
        subcats_for_llm = [
            {
                "id": s["id"],
                "name": s["name"],
                "default_unit": s["default_unit"],
                "allowed_units": s["allowed_units"],
                "attribute_keys": s["attribute_keys"],
            }
            for s in subcats
        ]
        subcats_map = {s["id"]: s for s in subcats}
        prompt = self._build_vision_catalog_prompt(subcats_for_llm, multi_mode=True)
        b64 = base64.b64encode(image_data).decode('utf-8')
        res = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}]}],
            temperature=0.25
        )
        return self._parse_gemini_json_response(res.choices[0].message.content, subcats_map=subcats_map)

    async def analyze_processed_json_products_async(self, raw_products_json: List[Dict[str, Any]]) -> Dict[str, Any]:
        subcats = await self._get_available_subcategories()
        subcats_for_llm = [
            {
                "id": s["id"],
                "name": s["name"],
                "default_unit": s["default_unit"],
                "allowed_units": s["allowed_units"],
                "attribute_keys": s["attribute_keys"],
            }
            for s in subcats
        ]
        subcats_map = {s["id"]: s for s in subcats}
        prompt = (
            "Mapea estas filas de inventario (Excel/CSV) al catálogo oficial de CartMaker.\n"
            "Para cada producto:\n"
            "1. Asígnale su `subcategory_id` exacto del catálogo oficial.\n"
            "2. Elige `selling_unit` dentro de las `allowed_units` de esa subcategoría.\n"
            "3. Extrae en `attributes` cualquier dato técnico o comercial usando las claves de `attribute_keys` "
            "de esa subcategoría (ej. marca, contenido_neto, modelo, condicion, talla, color, etc.).\n"
            "4. Si la fila describe variantes (tallas/colores/pesos), inclúyelas en `variants`.\n"
            "Responde ÚNICAMENTE con JSON válido:\n"
            "{\"products\": [{\"name\": \"...\", \"description\": \"...\", \"price\": 0.0, \"subcategory_id\": 1, "
            "\"selling_unit\": \"unit\", \"attributes\": {}, \"variants\": [], \"modifier_groups\": []}]}\n"
            f"Catálogo oficial: {json.dumps(subcats_for_llm, ensure_ascii=False)}"
        )
        res = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(raw_products_json, ensure_ascii=False)}],
            temperature=0.2
        )
        return self._parse_gemini_json_response(res.choices[0].message.content, subcats_map=subcats_map)