from datetime import datetime, timedelta
import hashlib
import math
import re
import statistics
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import F, Q, CharField, Exists, FloatField, ExpressionWrapper, Avg, OuterRef, Subquery
from django.db.models.expressions import Window
from django.db.models.functions import Cast, RowNumber, Coalesce, Power, Extract, Ln, Greatest
from django.db.models.functions import Now
from django.db.models import Case, When, Value, Count, BooleanField
from django.contrib.gis.measure import D
from django.db.models.expressions import RawSQL
from django.core.cache import cache
from api.models import *
from api.core.ve_commerce_lexicon import (
    expand_search_variants,
    significant_tokens,
    is_short_term,
    word_boundary_regex,
    substring_regex,
    lexical_match,
)
from api.core.ve_geo import describe_zone
from api.core.ve_malls import find_mall_near, display_mall_name

class ProductSearchEngine:
    """
    Motor Híbrido de CartMaker para la busqueda de productos.
    Combina geolocalización, prevención de monopolios, popularidad global 
    y filtrado basado en contenido (afinidad del usuario) en tiempo real.
    """

    def __init__(self, lat: float, lng: float, user=None, seed: str = 'default'):
        self.user_location = Point(lng, lat, srid=4326)
        # id de InventoryItem -> {'zone', 'mall_name', 'mall_floor'} de los finalistas de Atlas.
        # Vive fuera del payload para no alterar el JSON que consume Flutter.
        self.purchase_places = {}
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

    def _annotate_merchant_rating(self, queryset):
        merchant_sub = MerchantCalification.objects.filter(
            merchant_id=OuterRef('store__company_id')
        ).values('merchant_id')

        merchant_avg = merchant_sub.annotate(avg=Avg('rating')).values('avg')[:1]
        merchant_count = merchant_sub.annotate(cnt=Count('id')).values('cnt')[:1]

        return queryset.annotate(
            merchant_avg_rating=Coalesce(
                Subquery(merchant_avg, output_field=FloatField()),
                Value(0.0),
                output_field=FloatField(),
            ),
            merchant_rating_count=Coalesce(
                Subquery(merchant_count, output_field=FloatField()),
                Value(0.0),
                output_field=FloatField(),
            )
        )

    def _apply_purchase_text_filter(self, queryset, query: str):
        """Recall alto para Atlas: sinónimos VE + trigram + tokens."""
        if not query or not str(query).strip():
            return queryset

        variants = expand_search_variants(query)
        text_q = Q()
        for variant in variants:
            clean_variant = variant.strip()
            if len(clean_variant) < 2:
                continue
            if is_short_term(clean_variant):
                # Términos cortos: solo palabra aislada (evita 'res' -> 'refresco').
                pattern = word_boundary_regex(clean_variant)
                text_q |= (
                    Q(product__name__iregex=pattern)
                    | Q(product__description__iregex=pattern)
                    | Q(product__category__name__iregex=pattern)
                    | Q(store__company__name__iregex=pattern)
                    | Q(store__name__iregex=pattern)
                )
            else:
                # Subcadena sin distinguir tildes ('camara' encuentra 'Cámara Digital').
                pattern = substring_regex(clean_variant)
                text_q |= (
                    Q(product__name__iregex=pattern)
                    | Q(product__description__iregex=pattern)
                    | Q(product__category__name__iregex=pattern)
                    | Q(store__company__name__iregex=pattern)
                    | Q(store__name__iregex=pattern)
                )

        short_query = str(query).strip()[:80]
        # Coalesce previene errores si description es NULL
        queryset = queryset.annotate(
            name_sim=Coalesce(TrigramSimilarity('product__name', short_query), Value(0.0), output_field=FloatField()),
            desc_sim=Coalesce(TrigramSimilarity('product__description', short_query), Value(0.0), output_field=FloatField()),
        ).annotate(
            match_sim=Greatest(F('name_sim'), F('desc_sim'))
        )

        if text_q and is_short_term(short_query):
            # La similitud trigram de queries cortas ('res' ~ 'refresco') reintroduce
            # los falsos positivos: aquí solo cuenta la coincidencia léxica por palabra.
            queryset = queryset.filter(text_q)
        elif text_q:
            queryset = queryset.filter(text_q | Q(match_sim__gte=0.18))
        else:
            queryset = queryset.filter(match_sim__gte=0.22)

        return queryset

    def _purchase_weights(self, mode: str):
        if mode == 'cheap':
            return {'price': 0.48, 'distance': 0.22, 'rating': 0.14, 'offer': 0.08, 'open': 0.05, 'platinum': 0.03}
        if mode == 'nearby':
            return {'price': 0.22, 'distance': 0.48, 'rating': 0.14, 'offer': 0.06, 'open': 0.07, 'platinum': 0.03}
        if mode == 'quality':
            return {'price': 0.18, 'distance': 0.22, 'rating': 0.38, 'offer': 0.06, 'open': 0.06, 'platinum': 0.10}
        return {'price': 0.32, 'distance': 0.32, 'rating': 0.18, 'offer': 0.08, 'open': 0.06, 'platinum': 0.04}

    # Multiplicador severo para ítems sin ninguna coincidencia léxica ni trigram.
    PURCHASE_IRRELEVANT_PENALTY = 0.05

    def _purchase_payload_is_relevant(self, payload: dict, variants_cache: dict) -> bool:
        """
        Compuerta de relevancia. Relevante si hay similitud trigram (match_sim > 0)
        o coincidencia léxica directa con el query original o sus sinónimos.
        Los registros ligeros ya traen 'lexical_match' precalculado; los payloads
        completos (p. ej. alternativas de resolve_shopping_list) se evalúan aquí.
        """
        if float(payload.get('match_sim') or 0.0) > 0.0:
            return True
        if 'lexical_match' in payload:
            return bool(payload['lexical_match'])

        query = (payload.get('match_query') or '').strip()
        if not query:
            return True
        if query not in variants_cache:
            variants_cache[query] = expand_search_variants(query)

        product = payload.get('product') or {}
        category = product.get('category') or {}
        texts = [
            product.get('name'),
            product.get('description'),
            category.get('name'),
            payload.get('company_name'),
            payload.get('store_name'),
        ]
        return lexical_match(texts, variants_cache[query])

    def _score_purchase_payloads(self, payloads: list, mode: str = 'best') -> list:
        if not payloads:
            return []

        variants_cache = {}
        prices = [p.get('effective_price') for p in payloads if p.get('effective_price') is not None]
        dists = [p.get('distance_meters') for p in payloads if p.get('distance_meters') is not None]
        median_price = statistics.median(prices) if prices else 1.0
        median_dist = statistics.median(dists) if dists else 1200.0
        weights = self._purchase_weights(mode)

        for payload in payloads:
            price = float(payload.get('effective_price') or median_price or 1.0)
            meters = float(payload.get('distance_meters') if payload.get('distance_meters') is not None else median_dist)
            
            # Datos reales del comercio
            m_rating = float(payload.get('merchant_avg_rating') or 0.0)
            m_count = int(payload.get('merchant_rating_count') or 0)
            
            # Datos reales del producto
            p_rating = float(payload.get('avg_rating') or 0.0)
            p_count = int(payload.get('rating_count') or 0)

            # Rating para cálculo algorítmico interno (no penaliza a tiendas nuevas a 3.6)
            if m_count > 0:
                calc_rating = ((m_rating * m_count) + (4.0 * 2)) / (m_count + 2)
            else:
                calc_rating = 3.8 # Valor neutral de arranque para comercios nuevos

            price_score = median_price / max(price, 0.05)
            price_score = min(price_score, 3.0) / 3.0
            distance_score = math.exp(-max(meters, 1.0) / 3500.0)
            rating_score = calc_rating / 5.0
            offer_score = 1.0 if (payload.get('offer_percentage') or 0) > 0 else 0.35
            open_score = 1.0 if payload.get('is_open_now') else 0.45
            platinum_score = 1.0 if payload.get('is_platinum') else 0.55
            match_sim = float(payload.get('match_sim') or 0.0)

            raw = (
                weights['price'] * price_score
                + weights['distance'] * distance_score
                + weights['rating'] * rating_score
                + weights['offer'] * offer_score
                + weights['open'] * open_score
                + weights['platinum'] * platinum_score
            )
            score = raw * (0.82 + min(match_sim, 0.5) * 0.36)
            is_relevant = self._purchase_payload_is_relevant(payload, variants_cache)
            if not is_relevant:
                # La relevancia es una compuerta: un ítem barato pero sin relación
                # con lo buscado jamás debe superar a un resultado pertinente.
                score *= self.PURCHASE_IRRELEVANT_PENALTY
            payload['purchase_score'] = round(score, 4)
            payload['_is_relevant'] = is_relevant
            
            # 💡 AQUÍ PASAMOS LA VERDAD REAL A LA TRÍADA, NADA DE BAYES DISFRAZADO
            payload['triad'] = {
                'price_usd': round(price, 2),
                'distance_m': round(meters, 1),
                'merchant_rating': round(m_rating, 1),
                'merchant_reviews_count': m_count,
                'product_rating': round(p_rating, 1),
                'product_reviews_count': p_count,
                'offer_pct': int(payload.get('offer_percentage') or 0),
                'open_now': bool(payload.get('is_open_now')),
                'platinum': bool(payload.get('is_platinum')),
            }
        payloads.sort(
            key=lambda p: (bool(p.get('_is_relevant', True)), p.get('purchase_score', 0)),
            reverse=True,
        )
        for payload in payloads:
            payload.pop('_is_relevant', None)
        return payloads

    def _diversify_purchase_results(self, payloads: list, limit: int, max_per_company: int = 2) -> list:
        picked = []
        per_company = {}
        overflow = []
        for payload in payloads:
            company = str(payload.get('product', {}).get('company_id') or payload.get('company_name'))
            count = per_company.get(company, 0)
            if count < max_per_company:
                picked.append(payload)
                per_company[company] = count + 1
            else:
                overflow.append(payload)
            if len(picked) >= limit:
                return picked
        for payload in overflow:
            if len(picked) >= limit:
                break
            picked.append(payload)
        return picked

    def _serialize_purchase_item(self, item, location_label: str, query: str) -> dict:
        payload = item.get_json()
        payload['nearest_saved_location_name'] = location_label
        payload['match_query'] = query
        payload['match_sim'] = float(getattr(item, 'match_sim', 0.0) or 0.0)
        if payload.get('distance_meters') is None:
            payload['distance_meters'] = item._distance_meters_value()
        if payload.get('effective_price') is None:
            payload['effective_price'] = item.get_effective_price()
        return payload

    def _build_purchase_light_record(self, item, variants: list) -> dict:
        """
        Registro liviano (dict en memoria) con solo los campos que consumen
        _score_purchase_payloads y _diversify_purchase_results. Requiere que el
        item venga con select_related completo para no disparar queries lazy.
        """
        product = item.product
        store = item.store
        company = store.company
        category = product.category
        offer = item._active_offer()

        if variants:
            matches_lexically = lexical_match(
                [
                    product.name,
                    product.description,
                    category.name if category else None,
                    company.name,
                    store.name,
                ],
                variants,
            )
        else:
            matches_lexically = True

        return {
            '_item': item,
            'id': str(item.id),
            'effective_price': item.get_effective_price(),
            'distance_meters': item._distance_meters_value(),
            'avg_rating': round(float(getattr(item, 'avg_rating', 0.0) or 0.0), 2),
            'rating_count': int(getattr(item, 'rating_count', 0) or 0),
            'merchant_avg_rating': round(float(getattr(item, 'merchant_avg_rating', 0.0) or 0.0), 2),
            'merchant_rating_count': int(getattr(item, 'merchant_rating_count', 0) or 0),
            'offer_percentage': int(offer.percentage) if offer else 0,
            'is_open_now': store.is_currently_open,
            'is_platinum': bool(getattr(company, 'is_platinum', False)),
            'match_sim': float(getattr(item, 'match_sim', 0.0) or 0.0),
            'lexical_match': matches_lexically,
            'company_name': company.name,
            'product': {'company_id': product.company_id},
        }

    def search_purchase_candidates(
        self,
        query: str,
        max_distance_meters: float = 15000.0,
        limit: int = 8,
        location_label: str = 'Tu ubicación actual',
        mode: str = 'best',
        min_distance_meters: float = 0.0,
    ) -> list:
        """
        Candidatos para Atlas: stock vivo, geo, matching VE y score de compra.

        Busca en el ANILLO (min_distance_meters, max_distance_meters]. Con
        min_distance_meters > 0 se omite todo lo ya cubierto por radios menores.
        Por cada finalista registra en self.purchase_places la zona deducida y el
        centro comercial (si lo hay), sin tocar las claves del payload.
        """
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = self._annotate_merchant_rating(qs)
        # Un solo JOIN para todo lo que get_json()/is_currently_open/effective_work_* tocan.
        qs = qs.select_related(
            'product',
            'product__category',
            'product__company',
            'store',
            'store__location',
            'store__location__mall',
            'store__company',
            'store__company__owner__subscription__plan',
        )
        qs = qs.filter(
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        if min_distance_meters and min_distance_meters > 0:
            qs = qs.filter(
                store__location__coordinates__distance_gt=(self.user_location, D(m=min_distance_meters))
            )
        qs = self._apply_purchase_text_filter(qs, query)
        qs = qs.annotate(effective_price=Coalesce(F('custom_price'), F('product__price')))

        # Ordenar por similitud semántica si se aplicó el filtro de texto, o por cercanía
        if 'match_sim' in qs.query.annotations:
            qs = qs.order_by('-match_sim', 'real_distance_meters', 'effective_price')
        else:
            qs = qs.order_by('real_distance_meters', 'effective_price')

        query_text = (query or '').strip()
        variants = expand_search_variants(query_text) if query_text else []

        # Pool ligero: solo los valores necesarios para el score, sin get_json().
        pool = []
        seen = set()
        for item in qs[:70]:
            item_id = str(item.id)
            if item_id in seen:
                continue
            seen.add(item_id)
            pool.append(self._build_purchase_light_record(item, variants))

        scored = self._score_purchase_payloads(pool, mode=mode)
        finalists = self._diversify_purchase_results(scored, limit=limit, max_per_company=2)

        # Solo los finalistas pagan el costo de la serialización completa.
        results = []
        for light in finalists:
            payload = self._serialize_purchase_item(light['_item'], location_label, query)
            payload['purchase_score'] = light['purchase_score']
            payload['triad'] = light['triad']
            self.purchase_places[str(light['_item'].id)] = self._resolve_item_place(light['_item'])
            results.append(payload)
        return results

    def _resolve_item_place(self, item) -> dict:
        """
        Zona (ciudad) y centro comercial de la tienda del ítem. El mall asignado en
        StoreLocation manda; si no hay, se deduce por cercanía con malls.json.
        """
        location = item.store.location
        coordinates = location.coordinates
        mall_name = None
        mall_floor = None
        mall = location.mall
        if mall is not None:
            mall_name = display_mall_name(mall.name)
            mall_floor = location.mall_floor
        else:
            nearby_mall = find_mall_near(coordinates.y, coordinates.x)
            if nearby_mall:
                mall_name = nearby_mall['name']
        return {
            'zone': describe_zone(coordinates.y, coordinates.x),
            'mall_name': mall_name,
            'mall_floor': mall_floor,
        }

    # Anillos de expansión (metros). Cada anillo cubre SOLO la franja entre el
    # radio anterior y el siguiente: nunca se vuelve a consultar lo ya buscado.
    PURCHASE_EXPANSION_RADII_M = (40000.0, 100000.0, 250000.0, 600000.0, 1500000.0)

    def search_purchase_expanding(
        self,
        query: str,
        base_radius_meters: float = 15000.0,
        limit: int = 6,
        location_label: str = 'Tu ubicación actual',
        mode: str = 'best',
    ) -> dict:
        """
        Busca en el radio base y, si no hay nada, avanza por anillos concéntricos
        disjuntos hasta encontrar existencias. Devuelve:
        {
            'results': [...payloads sin claves internas...],
            'expanded': bool,
            'origin_zone': 'Guatire',
            'found_zone': 'Caracas' | None,
            'zones_by_item': {id_item: 'Caracas', ...} (solo si expanded),
            'nearest_distance_meters': float | None,
            'searched_radius_meters': float,
        }
        """
        origin_zone = describe_zone(self.user_location.y, self.user_location.x)
        outcome = {
            'results': [],
            'expanded': False,
            'origin_zone': origin_zone,
            'found_zone': None,
            'nearest_distance_meters': None,
            'searched_radius_meters': float(base_radius_meters),
        }

        # Anillo 0: círculo base alrededor del usuario.
        results = self.search_purchase_candidates(
            query=query,
            max_distance_meters=base_radius_meters,
            limit=limit,
            location_label=location_label,
            mode=mode,
        )
        if results:
            outcome['results'] = results
            return outcome

        inner = float(base_radius_meters)
        for outer in self.PURCHASE_EXPANSION_RADII_M:
            if outer <= inner:
                continue
            results = self.search_purchase_candidates(
                query=query,
                max_distance_meters=outer,
                min_distance_meters=inner,
                limit=limit,
                location_label=location_label,
                mode=mode,
            )
            outcome['searched_radius_meters'] = outer
            if results:
                zones = [self.purchase_places.get(str(p.get('id')), {}).get('zone') for p in results]
                distances = [p.get('distance_meters') for p in results if p.get('distance_meters') is not None]
                nearest_idx = min(
                    range(len(results)),
                    key=lambda i: results[i].get('distance_meters') if results[i].get('distance_meters') is not None else float('inf'),
                )
                outcome.update({
                    'results': results,
                    'expanded': True,
                    'zones_by_item': {str(p.get('id')): zone for p, zone in zip(results, zones)},
                    'found_zone': zones[nearest_idx],
                    'nearest_distance_meters': min(distances) if distances else None,
                })
                return outcome
            inner = outer

        return outcome

    def resolve_shopping_list(
        self,
        needs: list,
        max_distance_meters: float = 15000.0,
        location_label: str = 'Tu ubicación actual',
        mode: str = 'best',
    ) -> dict:
        """Arma una lista de compras priorizando un mismo local cuando se puede."""
        buckets = []
        for raw_need in (needs or [])[:12]:
            if isinstance(raw_need, str):
                query = raw_need
                qty = ''
            else:
                query = (raw_need.get('query') or raw_need.get('name') or '').strip()
                qty = (raw_need.get('cantidad') or raw_need.get('qty') or '').strip()
            if not query:
                continue
            candidates = self.search_purchase_candidates(
                query=query,
                max_distance_meters=max_distance_meters,
                limit=8,
                location_label=location_label,
                mode=mode,
            )
            buckets.append({'query': query, 'cantidad': qty, 'candidates': candidates})

        store_coverage = {}
        for bucket in buckets:
            need = bucket['query']
            for candidate in bucket['candidates']:
                store_id = str(candidate.get('store_id'))
                slot = store_coverage.setdefault(store_id, {
                    'store_id': store_id,
                    'store_name': candidate.get('store_name'),
                    'company_name': candidate.get('company_name'),
                    'distance_meters': candidate.get('distance_meters'),
                    'is_open_now': candidate.get('is_open_now'),
                    'is_platinum': candidate.get('is_platinum'),
                    'location_label': candidate.get('nearest_saved_location_name'),
                    'by_need': {},
                })
                prev = slot['by_need'].get(need)
                if not prev or (candidate.get('purchase_score', 0) > prev.get('purchase_score', 0)):
                    slot['by_need'][need] = candidate

        def store_rank(slot):
            items = list(slot['by_need'].values())
            total = sum(float(i.get('effective_price') or 0) for i in items)
            dist = float(slot.get('distance_meters') or 99999)
            return (len(items), -dist, -total)

        ranked_stores = sorted(store_coverage.values(), key=store_rank, reverse=True)
        primary = ranked_stores[0] if ranked_stores else None

        found_items = []
        missing = []
        used_ids = set()
        if primary:
            for bucket in buckets:
                pick = primary['by_need'].get(bucket['query'])
                if pick:
                    found_items.append(pick)
                    used_ids.add(str(pick['id']))
                else:
                    missing.append(bucket)

            # Completar faltantes con el mejor candidato global (otra tienda).
            still_missing = []
            for bucket in missing:
                alts = [c for c in bucket['candidates'] if str(c['id']) not in used_ids]
                if alts:
                    found_items.append(alts[0])
                    used_ids.add(str(alts[0]['id']))
                    bucket['filled_elsewhere'] = alts[0]
                    still_missing.append(bucket)
                else:
                    still_missing.append(bucket)
            missing = [b for b in still_missing if not b.get('filled_elsewhere')]
            filled_elsewhere = [b for b in still_missing if b.get('filled_elsewhere')]
        else:
            filled_elsewhere = []
            missing = buckets

        alternatives = []
        for bucket in buckets:
            for candidate in bucket['candidates'][:3]:
                if str(candidate['id']) not in used_ids:
                    alternatives.append(candidate)

        alternatives = self._score_purchase_payloads(alternatives, mode=mode)[:6]
        injected = []
        for item in found_items + alternatives:
            if str(item['id']) not in {str(x['id']) for x in injected}:
                injected.append(item)

        total = round(sum(float(i.get('effective_price') or 0) for i in found_items), 2)
        primary_count = len(primary['by_need']) if primary else 0

        return {
            'type': 'shopping_plan',
            'primary_store': {
                'store_id': primary.get('store_id') if primary else None,
                'store_name': primary.get('store_name') if primary else None,
                'company_name': primary.get('company_name') if primary else None,
                'distance_meters': primary.get('distance_meters') if primary else None,
                'is_open_now': primary.get('is_open_now') if primary else None,
                'items_in_store': primary_count,
                'needs_total': len(buckets),
            } if primary else None,
            'found': found_items,
            'missing_queries': [b['query'] for b in missing],
            'filled_elsewhere': [
                {
                    'query': b['query'],
                    'item_name': b['filled_elsewhere'].get('product', {}).get('name'),
                    'store_name': b['filled_elsewhere'].get('store_name'),
                    'company_name': b['filled_elsewhere'].get('company_name'),
                }
                for b in filled_elsewhere
            ],
            'alternatives': alternatives,
            'estimated_total_usd': total,
            'injected': injected[:16],
            'needs': [{'query': b['query'], 'cantidad': b.get('cantidad', '')} for b in buckets],
        }

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
            import operator
            from functools import reduce

            search_terms = search_query.strip().split()
            word_queries = []
            
            # 🕵️ DEBUG 3: Ver los términos exactos que exige la consulta SQL
            print(f"🔍 ENGINE SQL -> Buscando coincidencia ESTRICTA (AND) para las palabras: {search_terms}")
            
            for term in search_terms:
                if len(term) > 2:
                    term_filter = (
                        Q(product__name__icontains=term) | 
                        Q(product__description__icontains=term) |
                        Q(product__category__name__icontains=term) |
                        Q(product__company__name__icontains=term)
                    )
                    word_queries.append(term_filter)
            
            if word_queries:
                global_search_filter = reduce(operator.and_, word_queries)
                qs = qs.filter(global_search_filter).distinct()

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
    
    def get_stores_with_tokens_feed(self, page: int = 1, page_size: int = 20, max_distance_meters: float = 10000) -> list:
        if not self.user or not self.user.is_authenticated:
            return []

        # Filtramos billeteras con saldo > 0 de compañías que tengan tiendas cerca y activas
        wallets = TokenWallet.objects.select_related('company', 'company__category').filter(
            user=self.user,
            balance__gt=0,
            company__stores__is_active=True,
            company__stores__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        ).distinct().order_by('-balance')

        start = (page - 1) * page_size
        end = start + page_size
        
        results = []
        for wallet in wallets[start:end]:
            company = wallet.company
            
            # Obtenemos la calificación promedio de la compañía
            avg_rating = MerchantCalification.objects.filter(
                merchant=company
            ).aggregate(average=Avg('rating'))['average'] or 0.0
            
            results.append({
                "company_id": str(company.id),
                "storeName": company.name,
                "storeProfilePictureUrl": storage_manager.get_url(company.image) if company.image else "",
                "category": company.category.name if company.category else "Comercio",
                "isPlatinium": company.is_platinum,
                "tokens": wallet.balance,
                "calification": round(avg_rating, 2)
            })
            
        return results