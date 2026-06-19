from datetime import datetime, timedelta
import hashlib
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F, Q, CharField, Exists, FloatField, ExpressionWrapper, Avg, OuterRef, Subquery
from django.db.models.expressions import Window
from django.db.models.functions import Cast, RowNumber, Coalesce, Power, Extract, Ln
from django.db.models.functions import Now
from django.db.models import Case, When, Value, Count, BooleanField
from django.contrib.gis.measure import D
from django.db.models.expressions import RawSQL
from django.core.cache import cache
from api.models import *

class ProductSearchEngine:
    """
    Motor Híbrido de CartMaker para la busqueda de productos.
    Combina geolocalización, prevención de monopolios, popularidad global 
    y filtrado basado en contenido (afinidad del usuario) en tiempo real.
    """

    def __init__(self, lat: float, lng: float, user=None, seed: str = 'default'):
        self.user_location = Point(lng, lat, srid=4326)
        self.user = user
        self.seed = str(seed)
        
        # Al instanciar, construimos su huella digital de intereses
        self.user_top_categories = self._build_user_affinity_profile()

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
            is_liked_subquery = UniversalLike.objects.filter(
                user=self.user, 
                content_type=video_ct, 
                object_id=Cast(OuterRef('pk'), output_field=CharField(max_length=50))
            )
            # 💡 Subquery para saber si ya lo vio (Impresión)
            is_viewed_subquery = VideoEngagementLog.objects.filter(
                client=self.user, 
                video=OuterRef('pk')
            )
            qs = qs.annotate(
                is_liked=Exists(is_liked_subquery),
                is_viewed=Exists(is_viewed_subquery) # 👈 Nueva anotación
            )
        else:
            qs = qs.annotate(
                is_liked=Value(False, output_field=BooleanField()),
                is_viewed=Value(False, output_field=BooleanField())
            )
        return qs

    def _annotate_video_ranking(self, queryset):
        """
        Calcula la relevancia del video basándose en Gravedad (Estilo Facebook/TikTok).
        """
        now = timezone.now()
        
        if self.user_top_categories:
            affinity_multiplier = Case(
                When(associated_item__product__category_id__in=self.user_top_categories, then=Value(1.50)),
                default=Value(1.0),
                output_field=FloatField()
            )
        else:
            affinity_multiplier = Value(1.0, output_field=FloatField())

        age_in_hours = ExpressionWrapper(
            (Extract(Now(), 'epoch') - Extract(F('creation'), 'epoch')) / 3600.0,
            output_field=FloatField()
        )

        gravity = Power(age_in_hours + 2.0, 1.5)

        # 💡 TÉCNICA 1: Fatiga de Impresión para videos
        viewed_penalty = Case(
            When(is_viewed=True, then=Value(0.05)),
            default=Value(1.0),
            output_field=FloatField()
        )

        # 💡 TÉCNICA 2: Jitter con Referencia Explícita a la Tabla
        table_name = CompanyVideoStory._meta.db_table
        jitter = RawSQL(f"((abs(hashtext(%s || {table_name}.id::text)) %% 100) / 100.0) * 0.4 + 0.8", (self.seed,))

        # 🚀 Fórmula integrada con Logaritmo para videos
        score_expression = ExpressionWrapper(
            ((Ln(F('views_count') + 2.0) * affinity_multiplier) / gravity) * viewed_penalty * jitter,
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
        
        product_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)

        # 1. AFINIDAD POR LIKES (Productos)
        liked_product_ids = UniversalLike.objects.filter(
            user=self.user,
            content_type=product_ct,
            creation__gte=date_threshold
        ).values_list('object_id', flat=True)

        liked_categories = InventoryItem.objects.filter(
            id__in=list(liked_product_ids)
        ).values_list('product__category_id', flat=True)

        # 2. AFINIDAD POR VISUALIZACIONES / CARRITO / COMPRAS
        viewed_categories = ProductViewLog.objects.filter(
            client=self.user,
            start_time__gte=date_threshold
        ).filter(
            Q(added_to_cart=True) | Q(bought=True) | Q(end_time__isnull=False)
        ).values_list('inventory_item__product__category_id', flat=True)

        # =========================================================================
        # 💡 NUEVA CAPA: AFINIDAD POR COMENTARIOS / PREGUNTAS (Alta Señal)
        # =========================================================================
        # Caso A: Categorías de productos donde el usuario dejó una duda
        commented_product_ids = UniversalComment.objects.filter(
            client=self.user,
            content_type=product_ct,
            question_creation__gte=date_threshold
        ).values_list('object_id', flat=True)
        
        commented_prod_categories = InventoryItem.objects.filter(
            id__in=list(commented_product_ids)
        ).values_list('product__category_id', flat=True)

        # Caso B: Categorías de los productos vinculados a los VIDEOS que el usuario comentó
        commented_video_ids = UniversalComment.objects.filter(
            client=self.user,
            content_type=video_ct,
            question_creation__gte=date_threshold
        ).values_list('object_id', flat=True)
        
        commented_video_categories = CompanyVideoStory.objects.filter(
            id__in=list(commented_video_ids),
            associated_item__isnull=False
        ).values_list('associated_item__product__category_id', flat=True)

        # =========================================================================
        # 3. PONDERACIÓN ASIMÉTRICA DE INTERACCIONES
        # =========================================================================
        frequency = {}
        
        # Likes y Views suman 1 punto de interés
        for cat_id in list(liked_categories) + list(viewed_categories):
            if cat_id:
                frequency[cat_id] = frequency.get(cat_id, 0) + 1
                
        # 💡 Los comentarios demuestran alta intención: Suman 3 puntos directo al score
        for cat_id in list(commented_prod_categories) + list(commented_video_categories):
            if cat_id:
                frequency[cat_id] = frequency.get(cat_id, 0) + 3

        # Ordenamos de mayor a menor y extraemos el Top 5
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
            store__company__owner__subscription__isnull=False,
            store__company__owner__subscription__valid_until__gte=now
        ).filter(
            Q(store__company__owner__subscription__plan__company_branches=True) |
            Q(
                store__company__owner__subscription__plan__company_branches=False,
                store__is_main_store=True
            )
        )

        # 💡 LÓGICA MOVIDA AQUÍ: Disponible globalmente para todos los endpoints
        if self.user and self.user.is_authenticated:
            product_ct = ContentType.objects.get_for_model(InventoryItem)
            is_liked_subquery = UniversalLike.objects.filter(
                user=self.user, 
                content_type=product_ct, 
                object_id=Cast(OuterRef('pk'), output_field=CharField(max_length=50))
            )
            is_viewed_subquery = ProductViewLog.objects.filter(
                client=self.user,
                inventory_item=OuterRef('pk')
            )
            qs = qs.annotate(
                is_liked=Exists(is_liked_subquery),
                is_viewed=Exists(is_viewed_subquery)
            )
            
            # Filtro Anti-Auto-Compra
            is_active_merchant = MerchantSubscription.objects.filter(
                merchant=self.user,
                valid_until__gte=now
            ).exists()
            
            if is_active_merchant:
                qs = qs.exclude(store__company__owner=self.user)
        else:
            qs = qs.annotate(
                is_liked=Value(False, output_field=BooleanField()),
                is_viewed=Value(False, output_field=BooleanField())
            )
                
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
        Calcula la relevancia del producto estático aplicando Gravedad,
        Fatiga de Impresión y Jitter por Semilla.
        """
        now = timezone.now()

        platinum_multiplier = Case(
            When(store__company__is_platinum=True, then=Value(1.20)),
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

        age_in_hours = ExpressionWrapper(
            (Extract(Now(), 'epoch') - Extract(F('creation'), 'epoch')) / 3600.0,
            output_field=FloatField()
        )

        gravity = Power(age_in_hours + 2.0, 1.2)

        # 💡 TÉCNICA 1: Fatiga de Impresión para productos
        viewed_penalty = Case(
            When(is_viewed=True, then=Value(0.05)),
            default=Value(1.0),
            output_field=FloatField()
        )

        # 💡 TÉCNICA 2: Jitter con Referencia Explícita a la Tabla
        table_name = InventoryItem._meta.db_table
        jitter = RawSQL(f"((abs(hashtext(%s || {table_name}.id::text)) %% 100) / 100.0) * 0.4 + 0.8", (self.seed,))

        # 🚀 Fórmula integrada con Logaritmo para controlar productos virales
        score_expression = ExpressionWrapper(
            ((Ln(F('cached_popularity_score') + 2.0) * platinum_multiplier * affinity_multiplier) / gravity) * viewed_penalty * jitter,
            output_field=FloatField()
        )
        
        # 🕵️ ESPÍA 4: Exponemos el jitter y la penalización como columnas virtuales
        return queryset.annotate(
            ranking_score=score_expression,
            debug_jitter=jitter,
        )

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
    
    def get_home_feed(self, page: int = 1, page_size: int = 20, max_distance_meters: float = 15000) -> dict:
        """
        Orquesta el feed mixto dinámicamente por página.
        Soporta escalabilidad infinita y compensación por falta de contenido multimedia.
        """
        approx_lat = round(self.user_location.y, 3)
        approx_lng = round(self.user_location.x, 3)
        affinity_hash = hashlib.md5(str(self.user_top_categories).encode()).hexdigest()
        
        # Llave de Redis aislada por página
        cache_key = f"cartmaker:struct:home:{approx_lat}:{approx_lng}:{affinity_hash}:seed_{self.seed}:p_{page}:sz_{page_size}"
        structural_page_feed = cache.get(cache_key)

        # 🕵️ ESPÍA 2: ¿Qué llave estamos buscando?
        print(f"🔍 [CACHE] Llave solicitada: {cache_key}")
        
        if not structural_page_feed:
            print(f"⚙️ [CACHE MISS] Calculando feed fresco desde la Base de Datos...")
            ideal_videos_count = int(page_size * 0.75)  # Ej: 15 si el tamaño es 20
            
            # 1. EVALUAMOS VIDEOS VIGENTES
            qs_videos = self._get_base_video_queryset()
            qs_videos = qs_videos.filter(
                company__stores__is_main_store=True,
                company__stores__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
            ).distinct() 
            
            qs_videos = self._annotate_video_ranking(qs_videos)
            
            # 💡 CONTAMOS ANTES DEL WINDOW FUNCTION: Para no romper la base de datos
            total_videos = qs_videos.count()
            
            qs_videos = self._apply_video_monopoly_prevention(qs_videos)
            
            # =========================================================================
            # 💡 MATEMÁTICA EXACTA PARA EVITAR REPETIDOS (Offset Fijo)
            # =========================================================================
            # ¿Cuántos videos reales nos saltamos de TODAS las páginas anteriores?
            v_start = min((page - 1) * ideal_videos_count, total_videos)
            v_end = v_start + ideal_videos_count
            
            videos_list = list(qs_videos[v_start:v_end])
            
            # 2. EVALUAMOS PRODUCTOS
            # ¿Cuántos items EN TOTAL se mostraron en páginas anteriores? -> (page - 1) * page_size
            # Como sabemos matemáticamente que 'v_start' de esos items fueron videos, el resto fueron obligatoriamente productos.
            p_start = ((page - 1) * page_size) - v_start
            
            # ¿Cuántos productos necesitamos AHORA para completar esta página a tope?
            products_needed = page_size - len(videos_list)
            p_end = p_start + products_needed

            qs_products = self._get_base_active_queryset()
                
            qs_products = self._annotate_proximity_flag(qs_products)
            qs_products = qs_products.filter(store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters)))
            qs_products = self._annotate_ranking_score(qs_products)
            qs_products = self._apply_monopoly_prevention(qs_products)
            home_horizon = timezone.now() - timedelta(days=45)
            # 💡 FILTRO INTELIGENTE: Pasan los nuevos OR los que tienen actividad viva (> 0)
            qs_products = qs_products.filter(
                Q(creation__gte=home_horizon) | Q(cached_popularity_score__gt=0.0)
            )
            
            # Slicing dinámico de productos en SQL con el punto de partida real
            products_list = list(qs_products[p_start:p_end])
            
            # ==========================================
            # 💡 DEBUG: AUDITORÍA DE RANKING DE PRODUCTOS
            # ==========================================
            print(f"\n📦 --- AUDITORÍA DE PRODUCTOS (Página {page}) ---")
            for idx, p in enumerate(products_list):
                score = round(getattr(p, 'ranking_score', 0.0), 4)
                prod_name = p.product.name if getattr(p, 'product', None) else "Desconocido"
                is_viewed = getattr(p, 'is_viewed', False)
                jitter_val = round(getattr(p, 'debug_jitter', 0.0), 4)
                pop_score = getattr(p, 'cached_popularity_score', 0.0)
                
                # Símbolos visuales para detectar rápido si aplicó la fatiga
                viewed_icon = "🔴 YA VISTO (-95%)" if is_viewed else "🟢 NUEVO"
                
                print(f" #{idx + 1} | Score: {score} | Jitter: {jitter_val}x | {viewed_icon} | Pop: {pop_score} | {prod_name}")
            print("--------------------------------------------------\n")
            
            if not videos_list and not products_list:
                return {"results": []}

            # 3. ENTRELAZAMOS
            structural_page_feed = self._interleave_feeds(videos_list, products_list, v_ratio=3, p_ratio=1)
            
            # Guardamos el esqueleto de la página por 10 minutos
            cache.set(cache_key, structural_page_feed, timeout=600)
            
        # 4. STITCHING VOLÁTIL
        final_feed = self._stitch_and_filter_results(structural_page_feed)
        
        response_data = {"results": final_feed}
        
        # Solo calculamos la barra de historias (StoryViewer) si es la primera página
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