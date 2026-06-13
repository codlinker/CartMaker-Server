from datetime import datetime, timedelta
import hashlib
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F, Q, Exists, FloatField, ExpressionWrapper, Avg, OuterRef
from django.db.models.expressions import Window
from django.db.models.functions import RowNumber, Coalesce
from django.db.models import Case, When, Value, Count, BooleanField
from django.contrib.gis.measure import D
from django.core.cache import cache
from api.models import InventoryItem, MerchantSubscription, ProductLike, ProductViewLog, CompanyStore

class ProductSearchEngine:
    """
    Motor Híbrido de CartMaker para la busqueda de productos.
    Combina geolocalización, prevención de monopolios, popularidad global 
    y filtrado basado en contenido (afinidad del usuario) en tiempo real.
    """

    # =========================================================================
    # CAPA DE CACHÉ DIVIDIDO (STRUCTURAL VS VOLATILE)
    # =========================================================================

    def _get_volatile_cache_key(self, item_id: str) -> str:
        """Genera la llave única en Redis para el estado en tiempo real de un lote."""
        return f"cartmaker:volatile:item:{item_id}"

    def _get_items_volatile_state(self, item_ids: list) -> dict:
        """
        Recupera el estado volátil de múltiples ítems en un solo viaje a Redis (MGET).
        Si hay un cache miss en algún ítem, se resolverá individualmente más adelante.
        """
        keys_map = {self._get_volatile_cache_key(uid): uid for uid in item_ids}
        # django-redis ejecuta un MGET nativo bajo el capó con get_many
        cached_states = cache.get_many(keys_map.keys())
        
        # Saneamos el resultado indexando directamente por el ID del ítem
        volatile_data = {}
        for key, state in cached_states.items():
            item_id = keys_map[key]
            volatile_data[item_id] = state
            
        return volatile_data

    def _stitch_and_filter_results(self, structural_results: list) -> list:
        """
        Fusiona el esqueleto estructural con el estado volátil en tiempo real de Redis.
        Filtra y descarta inmediatamente cualquier producto que se haya quedado sin stock
        o haya sido pausado en los últimos milisegundos.
        """
        if not structural_results:
            return []

        item_ids = [item["id"] for item in structural_results]
        volatile_states = self._get_items_volatile_state(item_ids)
        
        final_feed = []
        
        for item_data in structural_results:
            item_id = item_data["id"]
            state = volatile_states.get(item_id)
            
            # --- FALLBACK DE SEGURIDAD (CACHE MISS DEL ESTADO VOLÁTIL) ---
            # Si por alguna razón el estado volátil expiró en Redis, usamos los datos
            # estructurales de la BD como fuente de verdad temporal y repoblamos RAM.
            if not state:
                state = {
                    "stock": int(item_data.get("stock", 0)),
                    "paused": bool(item_data.get("paused", False)),
                    "custom_price": item_data.get("custom_price")
                }
                # Guardamos en Redis con un TTL largo; las señales se encargarán de mantenerlo fresco
                cache.set(self._get_volatile_cache_key(item_id), state, timeout=86400)
            
            # --- VALIDACIÓN CRÍTICA EN TIEMPO REAL ---
            # Si el producto está pausado o no tiene stock en el Nivel Volátil, 
            # se descarta silenciosamente en la RAM de Django antes de llegar a Flutter.
            if state["paused"] or state["stock"] <= 0:
                continue
                
            # Sobrescribimos el esqueleto con los valores reales y mutables de Redis
            item_data["stock"] = state["stock"]
            item_data["paused"] = state["paused"]
            item_data["custom_price"] = state["custom_price"]
            
            # Re-calculamos el offer si existía un custom_price dinámico en RAM
            if state["custom_price"] and item_data.get("offer"):
                # Si requieres lógica extra para ajustar porcentajes en caliente, se procesa aquí
                pass
                
            final_feed.append(item_data)
            
        return final_feed

    def __init__(self, lat: float, lng: float, user=None):
        self.user_location = Point(lng, lat, srid=4326)
        self.user = user
        
        # Al instanciar, construimos su huella digital de intereses
        self.user_top_categories = self._build_user_affinity_profile()
    
    def _build_user_affinity_profile(self):
        if not self.user or not self.user.is_authenticated:
            return []

        date_threshold = timezone.now() - timedelta(days=30)

        liked_categories = ProductLike.objects.filter(
            user=self.user,
            creation__gte=date_threshold
        ).values_list('product__product__category_id', flat=True)

        viewed_categories = ProductViewLog.objects.filter(
            client=self.user,
            start_time__gte=date_threshold
        ).filter(
            Q(added_to_cart=True) | Q(bought=True) | Q(end_time__isnull=False)
        ).values_list('inventory_item__product__category_id', flat=True)

        all_categories = list(liked_categories) + list(viewed_categories)
        
        if not all_categories:
            return []

        frequency = {}
        for cat_id in all_categories:
            if cat_id:
                frequency[cat_id] = frequency.get(cat_id, 0) + 1

        sorted_categories = sorted(frequency.items(), key=lambda x: x[1], reverse=True)
        top_5_category_ids = [cat[0] for cat in sorted_categories[:5]]

        return top_5_category_ids

    def _get_base_active_queryset(self):
        now = timezone.now()
        qs = InventoryItem.objects.select_related(
            'product',
            'product__category',
            'offer',
            'store',
            'store__company'
        ).annotate(
            avg_rating=Coalesce(Avg('product__califications__rating'), Value(0.0), output_field=FloatField()),
            rating_count=Count('product__califications')
        ).filter(
            paused=False,
            stock__gt=0,
            store__is_active=True,
            # Regla global: El vendedor de este producto DEBE tener suscripción activa
            store__company__owner__subscription__isnull=False,
            store__company__owner__subscription__valid_until__gte=now
        )

        # =====================================================================
        # 💡 NUEVO: Filtro ORTODOXO de Límite de Sucursales según Plan
        # =====================================================================
        qs = qs.filter(
            # Condición A: El plan SÍ permite múltiples sucursales
            Q(store__company__owner__subscription__plan__company_branches=True) |
            # Condición B: El plan NO permite sucursales (pasa solo la marcada como is_main_store)
            Q(
                store__company__owner__subscription__plan__company_branches=False,
                store__is_main_store=True
            )
        )

        # =====================================================================
        # Filtro Anti-Auto-Compra / Anti-Auto-Recomendación
        # =====================================================================
        if self.user and self.user.is_authenticated:
            is_active_merchant = MerchantSubscription.objects.filter(
                merchant=self.user,
                valid_until__gte=now
            ).exists()
            
            if is_active_merchant:
                qs = qs.exclude(store__company__owner=self.user)
                
        return qs
    
    def _annotate_proximity_flag(self, queryset):
        dist_expr = Distance('store__location__coordinates', self.user_location, spheroid=True)
        
        return queryset.annotate(
            real_distance_meters=dist_expr,
            is_very_close=Case(
                When(store__location__coordinates__distance_lte=(self.user_location, D(m=599.99)), then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            ),
            is_close=Case(
                When(
                    store__location__coordinates__distance_gte=(self.user_location, D(m=600)),
                    store__location__coordinates__distance_lte=(self.user_location, D(m=1200)),
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField()
            )
        )

    def _annotate_ranking_score(self, queryset):
        platinum_multiplier = Case(
            When(store__company__is_platinum=True, then=Value(1.10)),
            default=Value(1.0),
            output_field=FloatField()
        )

        if self.user_top_categories:
            affinity_multiplier = Case(
                When(product__category_id__in=self.user_top_categories, then=Value(1.30)),
                default=Value(1.0),
                output_field=FloatField()
            )
        else:
            affinity_multiplier = Value(1.0, output_field=FloatField())

        score_expression = ExpressionWrapper(
            F('cached_popularity_score') * platinum_multiplier * affinity_multiplier,
            output_field=FloatField()
        )
        
        return queryset.annotate(ranking_score=score_expression)

    def _apply_monopoly_prevention(self, queryset):
        qs = queryset.annotate(
            company_rank=Window(
                expression=RowNumber(),
                partition_by=[F('store__company_id')],
                order_by=[F('ranking_score').desc(), F('id').asc()]
            )
        )
        return qs.order_by('company_rank', '-ranking_score', 'id')

    def _apply_feed_sorting(self, qs, sort_by: str, price_order: str):
        if sort_by == 'relevance' and not price_order:
            qs = self._annotate_ranking_score(qs)
            return self._apply_monopoly_prevention(qs)

        order_params = []

        if sort_by == 'distance':
            qs = qs.annotate(distance_to_user=Distance('store__location__coordinates', self.user_location))
            order_params.extend(['distance_to_user', 'id']) 

        elif sort_by == 'rating':
            qs = qs.annotate(
                avg_rating=Coalesce(Avg('product__califications__rating'), Value(0.0), output_field=FloatField())
            )
            order_params.extend(['-avg_rating', 'id'])

        if price_order in ['asc', 'desc']:
            qs = qs.annotate(effective_price=Coalesce('custom_price', 'product__price'))
            
            if price_order == 'asc':
                order_params.extend(['effective_price', 'id'])
            else:
                order_params.extend(['-effective_price', 'id'])

        return qs.order_by(*order_params)

    # =========================================================================
    # MÉTODOS PÚBLICOS
    # =========================================================================

    # =========================================================================
    # CORE: ORQUESTADOR DE CACHÉ ESTRUCTURAL
    # =========================================================================

    def _get_cached_structural_feed(self, cache_key: str, queryset, limit: int = 100) -> list:
        """
        Abstracción DRY para resolver el Nivel Estructural de cualquier feed.
        """
        structural_feed = cache.get(cache_key)
        
        if not structural_feed:
            # 1. Materializamos el QuerySet en memoria (PostgreSQL -> RAM)
            structural_feed = [item.get_json() for item in queryset[:limit]]
            # 2. Guardamos la estructura en Redis por 10 minutos
            cache.set(cache_key, structural_feed, timeout=600)
            
        # 3. Stitching Volátil: Inyectamos stock y precios en milisegundos
        return self._stitch_and_filter_results(structural_feed)

    # =========================================================================
    # MÉTODOS PÚBLICOS
    # =========================================================================

    def get_category_feed(self, sub_category_id: int, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        cache_key = f"cartmaker:struct:cat:{sub_category_id}:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(
            product__category_id=sub_category_id,
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        qs = self._apply_feed_sorting(qs, sort_by, price_order)
        
        return self._get_cached_structural_feed(cache_key, qs)

    def get_offers_feed(self, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        now = timezone.now()
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        cache_key = f"cartmaker:struct:offers:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(
            offer__isnull=False,
            offer__valid_until__gte=now,
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        qs = self._apply_feed_sorting(qs, sort_by, price_order)
        
        return self._get_cached_structural_feed(cache_key, qs)

    def get_store_feed(self, store_id: str = None, company_id: str = None, category_id: int = None, price_order: str = None) -> list:
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        # Llave compuesta para el catálogo de una tienda
        cache_key = f"cartmaker:struct:store:{store_id}:{company_id}:{category_id}:{approx_lat}:{approx_lng}:{price_order}"
        
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        if store_id:
            qs = qs.filter(store_id=store_id)
        elif company_id:
            qs = qs.filter(store__company_id=company_id)
            
        if category_id:
            qs = qs.filter(product__category_id=category_id)
        
        if price_order in ['asc', 'desc']:
            qs = qs.annotate(effective_price=Coalesce('custom_price', 'product__price'))
            qs = qs.order_by('effective_price' if price_order == 'asc' else '-effective_price')
        else:
            qs = qs.annotate(ranking_score=F('cached_popularity_score'))
            qs = qs.order_by('-ranking_score')
            
        return self._get_cached_structural_feed(cache_key, qs)
        
    def get_text_search_feed(self, search_query: str, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        # Encriptamos el query de texto para generar una llave limpia en Redis
        query_hash = hashlib.md5(search_query.strip().lower().encode()).hexdigest() if search_query else "empty"
        cache_key = f"cartmaker:struct:search:{query_hash}:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )

        if search_query:
            clean_query = search_query.strip()
            qs = qs.filter(
                Q(product__name__icontains=clean_query) | 
                Q(product__description__icontains=clean_query) |
                Q(product__category__name__icontains=clean_query) |
                Q(product__company__name__icontains=clean_query)
            ).distinct()

        qs = self._apply_feed_sorting(qs, sort_by, price_order)
        return self._get_cached_structural_feed(cache_key, qs)
    
    def get_home_feed(self, max_distance_meters: float = 15000) -> list:
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        affinity_hash = hashlib.md5(str(self.user_top_categories).encode()).hexdigest()
        
        cache_key = f"cartmaker:struct:home:{approx_lat}:{approx_lng}:{affinity_hash}"
        
        qs = self._get_base_active_queryset()
        
        if self.user and self.user.is_authenticated:
            is_liked_subquery = ProductLike.objects.filter(
                user=self.user, 
                product=OuterRef('pk')
            )
            qs = qs.annotate(is_liked=Exists(is_liked_subquery))
        else:
            qs = qs.annotate(is_liked=Value(False, output_field=BooleanField()))
        
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        qs = self._annotate_ranking_score(qs)
        qs = self._apply_monopoly_prevention(qs)
        
        return self._get_cached_structural_feed(cache_key, qs)
    
    def get_favorites_feed(self, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        if not self.user or not self.user.is_authenticated:
            return []

        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        # Incluimos el ID del usuario en la llave, ya que los favoritos son únicos por perfil
        cache_key = f"cartmaker:struct:favs:{self.user.id}:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
        structural_feed = cache.get(cache_key)
        
        if not structural_feed:
            qs = self._get_base_active_queryset()
            qs = self._annotate_proximity_flag(qs)
            
            qs = qs.filter(
                likes__user=self.user,
                store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
            )
            qs = qs.annotate(is_liked=Value(True, output_field=BooleanField()))
            
            if sort_by == 'relevance' and not price_order:
                qs = qs.annotate(like_date=F('likes__creation')).order_by('-like_date')
            else:
                qs = self._apply_feed_sorting(qs, sort_by, price_order)
                
            structural_feed = [item.get_json() for item in qs[:100]]
            cache.set(cache_key, structural_feed, timeout=600)
            
        return self._stitch_and_filter_results(structural_feed)