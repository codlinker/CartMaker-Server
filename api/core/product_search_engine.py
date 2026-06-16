from datetime import datetime, timedelta
import hashlib
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F, Q, CharField, Exists, FloatField, ExpressionWrapper, Avg, OuterRef, Subquery
from django.db.models.expressions import Window
from django.db.models.functions import Cast, RowNumber, Coalesce
from django.db.models import Case, When, Value, Count, BooleanField
from django.contrib.gis.measure import D
from django.core.cache import cache
from api.models import *

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
        Fusiona el esqueleto estructural con el estado volátil y los likes en tiempo real.
        """
        if not structural_results:
            return []

        # 1. Preparación de IDs para bulk fetch
        product_ids = []
        video_ids = []
        for item in structural_results:
            if item.get("feed_type") == "product":
                product_ids.append(str(item["id"]))
            elif item.get("feed_type") == "video":
                video_ids.append(str(item["id"]))

        # 2. Bulk fetch de Estados Volátiles (Stock/Precios)
        # Combinamos IDs de productos directos y de productos en videos
        item_ids_to_fetch = set(product_ids)
        for item in structural_results:
            if item.get("feed_type") == "video" and item.get("associated_item"):
                item_ids_to_fetch.add(item["associated_item"]["id"])
                
        volatile_states = self._get_items_volatile_state(list(item_ids_to_fetch))

        # 3. Bulk fetch de Likes (Conteos y Estado del Usuario)
        product_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)
        
        # Conteos masivos
        like_counts = UniversalLike.objects.filter(
            Q(content_type=product_ct, object_id__in=product_ids) |
            Q(content_type=video_ct, object_id__in=video_ids)
        ).values('content_type', 'object_id').annotate(total=Count('id'))
        
        # Mapa: {(content_type_id, object_id): count}
        count_map = {(d['content_type'], d['object_id']): d['total'] for d in like_counts}

        # Likes del usuario actual
        user_likes_set = set()
        if self.user and self.user.is_authenticated:
            user_likes = UniversalLike.objects.filter(user=self.user).values('content_type', 'object_id')
            user_likes_set = {(l['content_type'], l['object_id']) for l in user_likes}

        final_feed = []
        
        # 4. Procesamiento final (Stitching)
        for item_data in structural_results:
            feed_type = item_data.get("feed_type")
            item_id = str(item_data.get("id"))
            
            # Determinar el ContentType actual
            ct_id = product_ct.id if feed_type == "product" else video_ct.id

            # Inyectar likes
            item_data["is_liked"] = (ct_id, item_id) in user_likes_set
            item_data["likes_count"] = count_map.get((ct_id, item_id), 0)

            # ==========================================================
            # PROCESAMIENTO DE PRODUCTOS
            # ==========================================================
            if feed_type == "product":
                state = volatile_states.get(item_id)
                if not state:
                    state = {
                        "stock": int(item_data.get("stock", 0)),
                        "paused": bool(item_data.get("paused", False)),
                        "custom_price": item_data.get("custom_price")
                    }
                    cache.set(self._get_volatile_cache_key(item_id), state, timeout=86400)
                
                if state["paused"] or state["stock"] <= 0:
                    continue
                    
                item_data["stock"] = state["stock"]
                item_data["paused"] = state["paused"]
                item_data["custom_price"] = state["custom_price"]
                final_feed.append(item_data)

            # ==========================================================
            # PROCESAMIENTO DE VIDEOS
            # ==========================================================
            elif feed_type == "video":
                if item_data.get("associated_item"):
                    assoc_id = item_data["associated_item"]["id"]
                    state = volatile_states.get(assoc_id)
                    if not state:
                        state = {
                            "stock": int(item_data["associated_item"].get("stock", 0)),
                            "paused": bool(item_data["associated_item"].get("paused", False)),
                            "custom_price": item_data["associated_item"].get("custom_price")
                        }
                        cache.set(self._get_volatile_cache_key(assoc_id), state, timeout=86400)
                    
                    item_data["associated_item"]["stock"] = state["stock"]
                    item_data["associated_item"]["paused"] = state["paused"]
                    item_data["associated_item"]["custom_price"] = state["custom_price"]
                    item_data["associated_item"]["is_sold_out_volatile"] = state["paused"] or state["stock"] <= 0

                final_feed.append(item_data)
                
        return final_feed

    def __init__(self, lat: float, lng: float, user=None):
        self.user_location = Point(lng, lat, srid=4326)
        self.user = user
        
        # Al instanciar, construimos su huella digital de intereses
        self.user_top_categories = self._build_user_affinity_profile()

    # =========================================================================
    # 💡 NUEVA CAPA: QUERYSETS DE VIDEOS
    # =========================================================================

    def _apply_video_monopoly_prevention(self, queryset):
        """
        Evita que una sola compañía acapare los videos consecutivos del feed.
        """
        qs = queryset.annotate(
            company_rank=Window(
                expression=RowNumber(),
                partition_by=[F('company_id')],
                order_by=[F('ranking_score').desc(), F('id').asc()]
            )
        )
        return qs.order_by('company_rank', '-ranking_score', 'id')

    def _get_stories_feed(self, max_distance_meters: float) -> list:
        now = timezone.now()
        # 1. Obtenemos los videos vigentes de tiendas cercanas
        qs_videos = CompanyVideoStory.objects.select_related('company').filter(
            expires_at__gt=now,
            video_file__isnull=False,
            company__stores__is_main_store=True,
            company__stores__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters)),
            company__owner__subscription__isnull=False,
            company__owner__subscription__valid_until__gte=now
        ).distinct()

        # 2. Verificamos si el usuario ya vio el video usando el log de engagement
        if self.user and self.user.is_authenticated:
            is_viewed_subquery = VideoEngagementLog.objects.filter(
                client=self.user, 
                video=OuterRef('pk')
            )
            qs_videos = qs_videos.annotate(is_viewed=Exists(is_viewed_subquery))
        else:
            qs_videos = qs_videos.annotate(is_viewed=Value(False, output_field=BooleanField()))

        videos = list(qs_videos.order_by('-creation'))
        
        # 3. Agrupamos por compañía
        companies_map = {}
        for v in videos:
            cid = str(v.company_id)
            if cid not in companies_map:
                companies_map[cid] = {
                    "store_id": cid,
                    "store_name": v.company.name,
                    "profile_picture_img_url": storage_manager.get_url(v.company.image) if v.company.image else "",
                    "new_stories": [],
                    "watched_stories": []
                }
            
            vid_data = v.get_json()
            vid_data["feed_type"] = "video"
            
            if getattr(v, 'is_viewed', False):
                companies_map[cid]["watched_stories"].append(vid_data)
            else:
                companies_map[cid]["new_stories"].append(vid_data)

        # 4. Convertimos a lista y ordenamos: 
        # PRIMERO: las que tienen historias nuevas. SEGUNDO: la cantidad total de historias.
        companies_list = list(companies_map.values())
        companies_list.sort(
            key=lambda x: (len(x["new_stories"]) > 0, len(x["new_stories"]) + len(x["watched_stories"])), 
            reverse=True
        )
        
        return companies_list
    
    def _get_base_video_queryset(self):
        now = timezone.now()
        qs = CompanyVideoStory.objects.select_related(
            'company',
            'associated_item',
            'associated_item__product__category'
        ).filter(
            expires_at__gt=now,
            video_file__isnull=False,
            company__owner__subscription__isnull=False,
            company__owner__subscription__valid_until__gte=now
        )
        
        if self.user and self.user.is_authenticated:
            video_ct = ContentType.objects.get_for_model(CompanyVideoStory)
            # 💡 FIX: Cast explícito a CharField(max_length=50)
            is_liked_subquery = UniversalLike.objects.filter(
                user=self.user, 
                content_type=video_ct, 
                object_id=Cast(OuterRef('pk'), output_field=CharField(max_length=50))
            )
            qs = qs.annotate(is_liked=Exists(is_liked_subquery))
        else:
            qs = qs.annotate(is_liked=Value(False, output_field=BooleanField()))
        return qs

    def _annotate_video_ranking(self, queryset):
        """
        Calcula la relevancia del video basándose en:
        1. Vistas (Popularidad)
        2. Afinidad del usuario (Categorías favoritas)
        3. 💡 Novedad (Freshness Boost para evitar el estancamiento)
        """
        now = timezone.now()
        
        # 💡 FRESHNESS BOOST: Los videos de las últimas 48h valen x3. Los de la última semana x1.5.
        freshness_multiplier = Case(
            When(creation__gte=now - timedelta(days=2), then=Value(3.0)),
            When(creation__gte=now - timedelta(days=7), then=Value(1.5)),
            default=Value(1.0),
            output_field=FloatField()
        )

        if self.user_top_categories:
            affinity_multiplier = Case(
                When(associated_item__product__category_id__in=self.user_top_categories, then=Value(1.50)),
                default=Value(1.0),
                output_field=FloatField()
            )
        else:
            affinity_multiplier = Value(1.0, output_field=FloatField())

        # 💡 PUNTAJE BASE (+ 1.0): Evita que un video nuevo con 0 vistas multiplique todo por cero.
        score_expression = ExpressionWrapper(
            (F('views_count') + 1.0) * affinity_multiplier * freshness_multiplier,
            output_field=FloatField()
        )
        return queryset.annotate(ranking_score=score_expression).order_by('-ranking_score')

    # =========================================================================
    # CORE: ORQUESTADOR DE CACHÉ Y ENTRELAZADO (INTERLEAVING)
    # =========================================================================

    def _interleave_feeds(self, videos: list, products: list, v_ratio: int = 3, p_ratio: int = 1) -> list:
        """
        Entrelaza las listas de videos y productos de la página actual.
        Garantiza que el orden sea estrictamente V-V-V-P.
        """
        feed = []
        v_idx, p_idx = 0, 0
        
        while v_idx < len(videos) or p_idx < len(products):
            # Inyectamos el ratio de videos
            for _ in range(v_ratio):
                if v_idx < len(videos):
                    video_data = videos[v_idx].get_json()
                    video_data["feed_type"] = "video"
                    feed.append(video_data)
                    v_idx += 1
                    
            # Inyectamos el ratio de productos
            for _ in range(p_ratio):
                if p_idx < len(products):
                    product_data = products[p_idx].get_json()
                    product_data["feed_type"] = "product"
                    feed.append(product_data)
                    p_idx += 1
                    
        return feed
    
    def _build_user_affinity_profile(self):
        if not self.user or not self.user.is_authenticated:
            return []

        date_threshold = timezone.now() - timedelta(days=30)
        
        # 1. Obtenemos el ContentType de InventoryItem
        product_ct = ContentType.objects.get_for_model(InventoryItem)

        # 2. Paso 1: Obtenemos los IDs de los productos que el usuario ha dado Like
        # (Buscamos en la tabla polimórfica filtrando por el tipo 'product')
        liked_product_ids = UniversalLike.objects.filter(
            user=self.user,
            content_type=product_ct,
            creation__gte=date_threshold
        ).values_list('object_id', flat=True)

        # 3. Paso 2: Obtenemos las categorías de esos productos específicos
        liked_categories = InventoryItem.objects.filter(
            id__in=list(liked_product_ids)
        ).values_list('product__category_id', flat=True)

        # 4. Obtenemos categorías de productos visualizados
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
        """
        Calcula la relevancia del producto estático.
        """
        now = timezone.now()

        # 💡 FRESHNESS BOOST: Productos recién creados compiten contra los más vendidos.
        freshness_multiplier = Case(
            When(creation__gte=now - timedelta(days=3), then=Value(3.0)),
            When(creation__gte=now - timedelta(days=10), then=Value(1.5)),
            default=Value(1.0),
            output_field=FloatField()
        )

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

        # 💡 PUNTAJE BASE (+ 1.0): Evita que productos sin historial de compras queden en 0 absoluto.
        score_expression = ExpressionWrapper(
            (F('cached_popularity_score') + 1.0) * platinum_multiplier * affinity_multiplier * freshness_multiplier,
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

    # =========================================================================
    # CORE: ORQUESTADOR DE CACHÉ ESTRUCTURAL
    # =========================================================================

    def _get_cached_structural_feed(self, base_cache_key: str, queryset, page: int, page_size: int) -> list:
        """
        Abstracción DRY para resolver el Nivel Estructural de CUALQUIER feed.
        Hace el corte de paginación directo en PostgreSQL.
        """
        # Le pegamos la página y el tamaño a la llave para aislar la memoria
        cache_key = f"{base_cache_key}:p_{page}:sz_{page_size}"
        
        structural_feed = cache.get(cache_key)
        
        if not structural_feed:
            # 1. Calculamos el offset y limit para SQL
            start = (page - 1) * page_size
            end = start + page_size
            
            # 2. Slicing en SQL e INYECCIÓN del feed_type
            structural_feed = []
            for item in queryset[start:end]:
                item_data = item.get_json()
                item_data["feed_type"] = "product" # 👈 LA SOLUCIÓN AQUÍ
                structural_feed.append(item_data)
            
            # 3. Guardamos la estructura en Redis por 10 minutos
            cache.set(cache_key, structural_feed, timeout=600)
            
        # 4. Stitching Volátil: Inyectamos stock y precios en milisegundos
        return self._stitch_and_filter_results(structural_feed)

    def get_category_feed(self, sub_category_id: int, page: int = 1, page_size: int = 20, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        base_cache_key = f"cartmaker:struct:cat:{sub_category_id}:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(
            product__category_id=sub_category_id,
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        qs = self._apply_feed_sorting(qs, sort_by, price_order)
        
        return self._get_cached_structural_feed(base_cache_key, qs, page, page_size)

    def get_offers_feed(self, page: int = 1, page_size: int = 20, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        now = timezone.now()
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        base_cache_key = f"cartmaker:struct:offers:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(
            offer__isnull=False,
            offer__valid_until__gte=now,
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        qs = self._apply_feed_sorting(qs, sort_by, price_order)
        
        return self._get_cached_structural_feed(base_cache_key, qs, page, page_size)

    def get_store_feed(self, page: int = 1, page_size: int = 20, store_id: str = None, company_id: str = None, category_id: int = None, price_order: str = None) -> list:
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        base_cache_key = f"cartmaker:struct:store:{store_id}:{company_id}:{category_id}:{approx_lat}:{approx_lng}:{price_order}"
        
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
            
        return self._get_cached_structural_feed(base_cache_key, qs, page, page_size)
        
    def get_text_search_feed(self, search_query: str, page: int = 1, page_size: int = 20, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        query_hash = hashlib.md5(search_query.strip().lower().encode()).hexdigest() if search_query else "empty"
        base_cache_key = f"cartmaker:struct:search:{query_hash}:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
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
        return self._get_cached_structural_feed(base_cache_key, qs, page, page_size)
    
    def get_home_feed(self, page: int = 1, page_size: int = 20, max_distance_meters: float = 15000) -> list:
        """
        Orquesta el feed mixto dinámicamente por página.
        Soporta escalabilidad infinita y compensación por falta de contenido multimedia.
        """
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        affinity_hash = hashlib.md5(str(self.user_top_categories).encode()).hexdigest()
        
        # Llave de Redis aislada por página
        cache_key = f"cartmaker:struct:home_mixed:{approx_lat}:{approx_lng}:{affinity_hash}:p_{page}:sz_{page_size}"
        structural_page_feed = cache.get(cache_key)
        
        if not structural_page_feed:
            # Calcular cuántos elementos ideales de cada tipo corresponden a esta página
            ideal_videos_count = int(page_size * 0.75)  # Ej: 15 si el tamaño es 20
            ideal_products_count = page_size - ideal_videos_count  # Ej: 5
            
            # Offsets para base de datos
            v_start = (page - 1) * ideal_videos_count
            v_end = v_start + ideal_videos_count
            
            p_start = (page - 1) * ideal_products_count

            # 1. EVALUAMOS VIDEOS VIGENTES
            qs_videos = self._get_base_video_queryset()
            qs_videos = qs_videos.filter(
                company__stores__is_main_store=True,
                company__stores__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
            ).distinct() 
            
            # Anotamos el puntaje base
            qs_videos = self._annotate_video_ranking(qs_videos)
            
            # 💡 SOLUCIÓN AQUÍ: Mezclamos los videos de distintas compañías
            qs_videos = self._apply_video_monopoly_prevention(qs_videos)
            
            # Slicing nativo en SQL de los videos de esta página
            videos_list = list(qs_videos[v_start:v_end])
            
            # 💡 COMPENSACIÓN DE CONTENIDO (Mantenemos la página siempre llena)
            video_deficit = ideal_videos_count - len(videos_list)
            real_products_to_fetch = ideal_products_count + video_deficit
            
            # Ajustamos dinámicamente el final del corte de productos en SQL
            p_end_adjusted = p_start + real_products_to_fetch

            # 2. EVALUAMOS PRODUCTOS
            qs_products = self._get_base_active_queryset()
            if self.user and self.user.is_authenticated:
                product_ct = ContentType.objects.get_for_model(InventoryItem)
                # 💡 FIX: Cast explícito a CharField(max_length=50)
                is_liked_subquery = UniversalLike.objects.filter(
                    user=self.user, 
                    content_type=product_ct, 
                    object_id=Cast(OuterRef('pk'), output_field=CharField(max_length=50))
                )
                qs_products = qs_products.annotate(is_liked=Exists(is_liked_subquery))
            else:
                qs_products = qs_products.annotate(is_liked=Value(False, output_field=BooleanField()))
                
            qs_products = self._annotate_proximity_flag(qs_products)
            qs_products = qs_products.filter(store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters)))
            qs_products = self._annotate_ranking_score(qs_products)
            qs_products = self._apply_monopoly_prevention(qs_products)
            
            # Slicing optimizado de productos en SQL
            products_list = list(qs_products[p_start:p_end_adjusted])
            
            if not videos_list and not products_list:
                return []

            # 3. ENTRELAZAMOS
            structural_page_feed = self._interleave_feeds(videos_list, products_list, v_ratio=3, p_ratio=1)
            
            # Guardamos el esqueleto de la página por 10 minutos
            cache.set(cache_key, structural_page_feed, timeout=600)
            
        # 4. STITCHING VOLÁTIL
        final_feed = self._stitch_and_filter_results(structural_page_feed)
        
        # 💡 NUEVO: Retornamos un diccionario
        response_data = {"results": final_feed}
        
        # Solo calculamos la barra de historias si es la primera página
        if page == 1:
            response_data["stories"] = self._get_stories_feed(max_distance_meters)
        return response_data
    
    def get_favorites_feed(self, page: int = 1, page_size: int = 20, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000) -> list:
        if not self.user or not self.user.is_authenticated:
            return []

        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        
        base_cache_key = f"cartmaker:struct:favs:{self.user.id}:{approx_lat}:{approx_lng}:{sort_by}:{price_order}"
        
        # 1. Obtenemos el ContentType de InventoryItem
        product_ct = ContentType.objects.get_for_model(InventoryItem)
        
        # 💡 FIX: Consultamos UniversalLike directamente. 
        # Esto es mucho más seguro que depender de un GenericRelation en el modelo.
        liked_product_ids = UniversalLike.objects.filter(
            user=self.user,
            content_type=product_ct
        ).values_list('object_id', flat=True)

        # Construimos el QuerySet base
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        # Filtramos usando los IDs obtenidos de UniversalLike
        qs = qs.filter(
            id__in=list(liked_product_ids),
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        
        # Anotamos el is_liked como True (ya que estamos en la lista de favoritos)
        qs = qs.annotate(is_liked=Value(True, output_field=BooleanField()))
        
        # Aplicamos ordenamiento
        if sort_by == 'relevance' and not price_order:
            # Para ordenar por fecha de like, necesitamos obtener el object_id como UUID
            qs = qs.annotate(
                like_date=Subquery(
                    UniversalLike.objects.filter(
                        user=self.user, 
                        content_type=product_ct, 
                        object_id=Cast(OuterRef('pk'), output_field=CharField())
                    ).values('creation')[:1]
                )
            ).order_by('-like_date')
        else:
            qs = self._apply_feed_sorting(qs, sort_by, price_order)
            
        return self._get_cached_structural_feed(base_cache_key, qs, page, page_size)