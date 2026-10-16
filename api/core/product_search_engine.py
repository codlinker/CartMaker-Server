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
from api.core.ve_geo import describe_zone, proximity_label
from api.core.ve_malls import find_mall_near, display_mall_name

class ProductSearchEngine:
    """
    Motor Híbrido de CartMaker para la busqueda de productos.
    Combina geolocalización, prevención de monopolios, popularidad global 
    y filtrado basado en contenido (afinidad del usuario) en tiempo real.
    """

    def __init__(self, lat: float, lng: float, user=None, seed: str = 'default'):
        self.user_location = Point(lng, lat, srid=4326)
        # id de InventoryItem -> {'zone', 'address', 'proximity', 'mall_name', 'mall_floor'} de los finalistas de Atlas.
        # Vive fuera del payload para no alterar el JSON que consume Flutter.
        self.purchase_places = {}
        self.user = user
        self.seed = str(seed)

        # Carga perezosa (Lazy) + Caché en Redis del perfil híbrido de intereses:
        # Evita disparar 11 consultas SQL en endpoints que no usan afinidad (ej. stores_with_tokens, favorites)
        # o cuando Flutter lanza 4 peticiones simultáneas al abrir el Home.
        self._affinity_loaded = False
        self._user_onboarding_category_ids = []
        self._onboarding_weight = 1.0
        self._user_top_categories = []

    def _ensure_affinity_loaded(self):
        if self._affinity_loaded:
            return
        self._affinity_loaded = True
        if not self.user or not self.user.is_authenticated:
            self._user_onboarding_category_ids = []
            self._onboarding_weight = 0.0
            self._user_top_categories = []
            return

        cache_key = f"cartmaker:affinity_profile:v1:{self.user.id}"
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            self._user_top_categories = cached.get('top_categories', [])
            self._user_onboarding_category_ids = cached.get('onboarding_ids', [])
            self._onboarding_weight = float(cached.get('onboarding_weight', 0.0))
            return

        self._user_top_categories = self._build_user_affinity_profile()
        cache.set(
            cache_key,
            {
                'top_categories': self._user_top_categories,
                'onboarding_ids': self._user_onboarding_category_ids,
                'onboarding_weight': self._onboarding_weight,
            },
            timeout=180,
        )

    @property
    def user_top_categories(self) -> list:
        self._ensure_affinity_loaded()
        return self._user_top_categories

    @user_top_categories.setter
    def user_top_categories(self, value):
        self._user_top_categories = value

    @property
    def user_onboarding_category_ids(self) -> list:
        self._ensure_affinity_loaded()
        return self._user_onboarding_category_ids

    @user_onboarding_category_ids.setter
    def user_onboarding_category_ids(self, value):
        self._user_onboarding_category_ids = value

    @property
    def onboarding_weight(self) -> float:
        self._ensure_affinity_loaded()
        return self._onboarding_weight

    @onboarding_weight.setter
    def onboarding_weight(self, value):
        self._onboarding_weight = value

    def _get_affinity_hash(self) -> str:
        """
        Genera una firma determinista del perfil de intereses actual del usuario
        (combinando afinidad conductual + preferencias de onboarding ponderadas)
        para aislar el caché estructural según sus gustos.
        """
        signature = (
            f"beh:{sorted(self.user_top_categories)}|"
            f"onb:{sorted(self.user_onboarding_category_ids)}|"
            f"w:{round(self.onboarding_weight, 1)}"
        )
        return hashlib.md5(signature.encode()).hexdigest()

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
                
        volatile_states = self._get_items_volatile_state(list(item_ids_to_fetch)) if item_ids_to_fetch else {}

        # 3. Bulk fetch de Likes (Conteos y Estado del Usuario) restringido a los IDs de esta página
        product_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)
        
        like_filter = Q()
        if product_ids:
            like_filter |= Q(content_type=product_ct, object_id__in=product_ids)
        if video_ids:
            like_filter |= Q(content_type=video_ct, object_id__in=video_ids)

        count_map = {}
        user_likes_set = set()
        if like_filter:
            like_counts = UniversalLike.objects.filter(like_filter).values('content_type', 'object_id').annotate(total=Count('id'))
            count_map = {(d['content_type'], d['object_id']): d['total'] for d in like_counts}

            if self.user and self.user.is_authenticated:
                user_likes = UniversalLike.objects.filter(user=self.user).filter(like_filter).values('content_type', 'object_id')
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
        qs_videos = CompanyVideoStory.objects.select_related(
            'company',
            'associated_item',
            'associated_item__product',
            'associated_item__product__category',
            'associated_item__product__category__parent_category',
            'associated_item__product__company',
            'associated_item__offer',
            'associated_item__store',
            'associated_item__store__company',
        ).filter(
            expires_at__gt=now,
            video_file__isnull=False,
            company__stores__is_main_store=True,
            company__stores__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters)),
            company__stores__is_active=True,
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
        
        behavioral_set = set(self.user_top_categories or [])
        onboarding_set = set(self.user_onboarding_category_ids or [])

        # 3. Agrupamos por compañía y calculamos afinidad de sus historias
        companies_map = {}
        for v in videos:
            cid = str(v.company_id)
            if cid not in companies_map:
                companies_map[cid] = {
                    "store_id": cid,
                    "store_name": v.company.name,
                    "profile_picture_img_url": storage_manager.get_url(v.company.image) if v.company.image else "",
                    "new_stories": [],
                    "watched_stories": [],
                    "_affinity_score": 0.0,
                }
            
            # Evaluamos si el producto vinculado al video coincide con los gustos del usuario
            assoc = getattr(v, 'associated_item', None)
            prod = getattr(assoc, 'product', None) if assoc else None
            subcat = getattr(prod, 'category', None) if prod else None
            if subcat:
                story_affinity = 0.0
                if subcat.id in behavioral_set:
                    story_affinity += 1.5
                if subcat.parent_category_id in onboarding_set:
                    story_affinity += 1.2 * self.onboarding_weight
                if story_affinity > companies_map[cid]["_affinity_score"]:
                    companies_map[cid]["_affinity_score"] = story_affinity

            vid_data = v.get_json()
            vid_data["feed_type"] = "video"
            
            if getattr(v, 'is_viewed', False):
                companies_map[cid]["watched_stories"].append(vid_data)
            else:
                companies_map[cid]["new_stories"].append(vid_data)

        # 4. Convertimos a lista y ordenamos:
        # PRIMERO: las que tienen historias nuevas.
        # SEGUNDO: mayor afinidad con el usuario (conductual + onboarding).
        # TERCERO: la cantidad total de historias.
        companies_list = list(companies_map.values())
        companies_list.sort(
            key=lambda x: (
                len(x["new_stories"]) > 0,
                round(x.get("_affinity_score", 0.0), 3),
                len(x["new_stories"]) + len(x["watched_stories"]),
            ), 
            reverse=True
        )
        for comp in companies_list:
            comp.pop("_affinity_score", None)
        
        return companies_list
    
    def _get_base_video_queryset(self):
        now = timezone.now()
        qs = CompanyVideoStory.objects.select_related(
            'company',
            'associated_item',
            'associated_item__product',
            'associated_item__product__category',
            'associated_item__product__category__parent_category',
            'associated_item__product__company',
            'associated_item__offer',
            'associated_item__store',
            'associated_item__store__company',
        ).filter(
            expires_at__gt=now,
            video_file__isnull=False,
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
        Calcula la relevancia del video basándose en Gravedad (Estilo Facebook/TikTok),
        combinando preferencias del Onboarding (Cold Start) con afinidad conductual real.
        """
        video_onboarding_boost = round(1.0 + (0.50 * self.onboarding_weight), 3)
        video_synergy_boost = round(1.55 + (0.12 * self.onboarding_weight), 3)

        if self.user_top_categories and self.user_onboarding_category_ids:
            affinity_multiplier = Case(
                When(
                    Q(associated_item__product__category_id__in=self.user_top_categories)
                    & Q(associated_item__product__category__parent_category_id__in=self.user_onboarding_category_ids),
                    then=Value(video_synergy_boost),
                ),
                When(
                    associated_item__product__category_id__in=self.user_top_categories,
                    then=Value(1.55),
                ),
                When(
                    associated_item__product__category__parent_category_id__in=self.user_onboarding_category_ids,
                    then=Value(video_onboarding_boost),
                ),
                default=Value(1.0),
                output_field=FloatField(),
            )
        elif self.user_top_categories:
            affinity_multiplier = Case(
                When(associated_item__product__category_id__in=self.user_top_categories, then=Value(1.55)),
                default=Value(1.0),
                output_field=FloatField()
            )
        elif self.user_onboarding_category_ids:
            affinity_multiplier = Case(
                When(
                    associated_item__product__category__parent_category_id__in=self.user_onboarding_category_ids,
                    then=Value(video_onboarding_boost),
                ),
                default=Value(1.0),
                output_field=FloatField(),
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
        """
        Construye el perfil híbrido de intereses del usuario:
        1. Carga las categorías principales seleccionadas en el Onboarding (`user.preferred_categories`).
        2. Analiza las señales reales de comportamiento de los últimos 30 días
           (vistas, carrito, compras, likes de productos/videos, engagement de videos y preguntas).
        3. Calcula `self.onboarding_weight` mediante decaimiento exponencial suave:
           - Al principio (Cold Start, 0 interacciones): `onboarding_weight = 1.0` (100% protagonismo).
           - Conforme el usuario interactúa con la app: decae progresivamente hasta `0.15`,
             cediendo el protagonismo a las subcategorías reales (`top_5_category_ids`).
        """
        if not self.user or not self.user.is_authenticated:
            self.user_onboarding_category_ids = []
            self.onboarding_weight = 0.0
            return []

        # 0. PREFERENCIAS DE ONBOARDING (Categorías Padre)
        try:
            self.user_onboarding_category_ids = list(
                self.user.preferred_categories.order_by('id').values_list('id', flat=True)
            )
        except Exception:
            self.user_onboarding_category_ids = []

        date_threshold = timezone.now() - timedelta(days=30)
        
        product_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)

        # 1. AFINIDAD POR LIKES (Productos y Videos en 1 sola consulta a UniversalLike)
        raw_likes = list(UniversalLike.objects.filter(
            user=self.user,
            content_type__in=[product_ct, video_ct],
            creation__gte=date_threshold,
        ).values_list('content_type_id', 'object_id'))

        liked_product_ids = [oid for ct_id, oid in raw_likes if ct_id == product_ct.id]
        liked_video_ids = [oid for ct_id, oid in raw_likes if ct_id == video_ct.id]

        liked_categories = list(InventoryItem.objects.filter(
            id__in=liked_product_ids
        ).values_list('product__category_id', flat=True)) if liked_product_ids else []

        liked_video_categories = list(CompanyVideoStory.objects.filter(
            id__in=liked_video_ids,
            associated_item__isnull=False
        ).values_list('associated_item__product__category_id', flat=True)) if liked_video_ids else []

        # 2. AFINIDAD POR VISUALIZACIONES / CARRITO / COMPRAS EN PRODUCTOS
        view_logs = list(ProductViewLog.objects.filter(
            client=self.user,
            start_time__gte=date_threshold
        ).filter(
            Q(added_to_cart=True) | Q(bought=True) | Q(end_time__isnull=False)
        ).values_list(
            'inventory_item__product__category_id',
            'added_to_cart',
            'bought',
        ))

        # 3. AFINIDAD POR ENGAGEMENT EN VIDEOS
        video_logs = list(VideoEngagementLog.objects.filter(
            client=self.user,
            timestamp__gte=date_threshold,
            video__associated_item__isnull=False,
        ).filter(
            Q(video_completed=True)
            | Q(interacted_with_product=True)
            | Q(added_to_cart_from_video=True)
            | Q(bought_from_video=True)
        ).values_list(
            'video__associated_item__product__category_id',
            'video_completed',
            'interacted_with_product',
            'added_to_cart_from_video',
            'bought_from_video',
        ))

        # 4. AFINIDAD POR COMENTARIOS / PREGUNTAS (Alta Señal en 1 sola consulta a UniversalComment)
        raw_comments = list(UniversalComment.objects.filter(
            client=self.user,
            content_type__in=[product_ct, video_ct],
            question_creation__gte=date_threshold,
        ).values_list('content_type_id', 'object_id'))

        commented_product_ids = [oid for ct_id, oid in raw_comments if ct_id == product_ct.id]
        commented_video_ids = [oid for ct_id, oid in raw_comments if ct_id == video_ct.id]

        commented_prod_categories = list(InventoryItem.objects.filter(
            id__in=commented_product_ids
        ).values_list('product__category_id', flat=True)) if commented_product_ids else []

        commented_video_categories = list(CompanyVideoStory.objects.filter(
            id__in=commented_video_ids,
            associated_item__isnull=False
        ).values_list('associated_item__product__category_id', flat=True)) if commented_video_ids else []

        # =========================================================================
        # 5. PONDERACIÓN ASIMÉTRICA DE INTERACCIONES Y DECAIMIENTO DEL ONBOARDING
        # =========================================================================
        frequency = {}

        # Likes en productos o videos suman 2 puntos
        for cat_id in liked_categories + liked_video_categories:
            if cat_id:
                frequency[cat_id] = frequency.get(cat_id, 0) + 2

        # Vistas (+1), Carrito (+4), Compras (+6)
        for cat_id, added_to_cart, bought in view_logs:
            if not cat_id:
                continue
            pts = 6 if bought else (4 if added_to_cart else 1)
            frequency[cat_id] = frequency.get(cat_id, 0) + pts

        # Video Engagement: Completado (+1), Click producto (+2), Carrito (+4), Compra (+6)
        for cat_id, completed, clicked, carted, bought_vid in video_logs:
            if not cat_id:
                continue
            pts = 6 if bought_vid else (4 if carted else (2 if clicked else (1 if completed else 0)))
            if pts > 0:
                frequency[cat_id] = frequency.get(cat_id, 0) + pts

        # Comentarios / Preguntas demuestran alta intención: Suman 3 puntos
        for cat_id in commented_prod_categories + commented_video_categories:
            if cat_id:
                frequency[cat_id] = frequency.get(cat_id, 0) + 3

        total_behavioral_points = sum(frequency.values())

        # Decaimiento progresivo del peso del Onboarding conforme crecen las señales reales:
        # - Con 0 puntos conductuales -> onboarding_weight = 1.00 (Cold Start puro)
        # - Con ~12 puntos conductuales -> onboarding_weight ≈ 0.51 (Transición híbrida)
        # - Con >=35 puntos conductuales -> onboarding_weight = 0.15 (Dominan los gustos reales)
        if self.user_onboarding_category_ids:
            self.onboarding_weight = round(
                max(0.15, math.exp(-float(total_behavioral_points) / 18.0)),
                3,
            )
        else:
            self.onboarding_weight = 0.0

        # Ordenamos de mayor a menor y extraemos el Top 5 de subcategorías conductuales
        sorted_categories = sorted(frequency.items(), key=lambda x: x[1], reverse=True)
        top_5_category_ids = [cat[0] for cat in sorted_categories[:5]]

        return top_5_category_ids

    def _get_base_active_queryset(self):
        prod_cal_sub = ProductCalification.objects.filter(
            product_id=OuterRef('product_id')
        ).values('product_id')
        prod_avg = prod_cal_sub.annotate(avg=Avg('rating')).values('avg')[:1]
        prod_cnt = prod_cal_sub.annotate(cnt=Count('id')).values('cnt')[:1]

        qs = InventoryItem.objects.select_related(
            'product',
            'product__category',
            'product__category__parent_category',
            'product__company',
            'offer',
            'store',
            'store__company',
        ).annotate(
            avg_rating=Coalesce(Subquery(prod_avg, output_field=FloatField()), Value(0.0), output_field=FloatField()),
            rating_count=Coalesce(Subquery(prod_cnt, output_field=FloatField()), Value(0.0), output_field=FloatField()),
        ).filter(
            paused=False,
            stock__gt=0,
            store__is_active=True,
        )

        # 💡 LÓGICA MOVIDA AQUÍ: Disponible globalmente para todos los endpoints
        if self.user and self.user.is_authenticated:
            is_viewed_subquery = ProductViewLog.objects.filter(
                client=self.user,
                inventory_item=OuterRef('pk')
            )
            qs = qs.annotate(
                is_liked=Value(False, output_field=BooleanField()),
                is_viewed=Exists(is_viewed_subquery)
            )
            
            # Un comerciante con compañía no compra su propio inventario.
            try:
                self.user.company
            except Company.DoesNotExist:
                pass
            else:
                qs = qs.exclude(store__company__owner=self.user)
        else:
            qs = qs.annotate(
                is_liked=Value(False, output_field=BooleanField()),
                is_viewed=Value(False, output_field=BooleanField())
            )
                
        return qs
    
    def _annotate_proximity_flag(self, queryset):
        # 1 sola función geodésica en SQL; is_very_close (<600m) e is_close (600m-1200m)
        # se derivan en O(1) en Python dentro de InventoryItem.get_json() a partir de real_distance_meters.
        dist_expr = Distance('store__location__coordinates', self.user_location, spheroid=True)
        return queryset.annotate(real_distance_meters=dist_expr)

    def _annotate_ranking_score(self, queryset):
        """
        Calcula la relevancia del producto estático aplicando Gravedad,
        Fatiga de Impresión, Jitter por Semilla y Afinidad Híbrida Progresiva
        (Preferencias de Onboarding en Cold Start -> Gustos Reales por Interacción).
        """
        platinum_multiplier = Case(
            When(store__company__is_platinum=True, then=Value(1.20)),
            default=Value(1.0),
            output_field=FloatField()
        )

        product_onboarding_boost = round(1.0 + (0.35 * self.onboarding_weight), 3)
        product_synergy_boost = round(1.35 + (0.10 * self.onboarding_weight), 3)

        if self.user_top_categories and self.user_onboarding_category_ids:
            affinity_multiplier = Case(
                When(
                    Q(product__category_id__in=self.user_top_categories)
                    & Q(product__category__parent_category_id__in=self.user_onboarding_category_ids),
                    then=Value(product_synergy_boost),
                ),
                When(
                    product__category_id__in=self.user_top_categories,
                    then=Value(1.35),
                ),
                When(
                    product__category__parent_category_id__in=self.user_onboarding_category_ids,
                    then=Value(product_onboarding_boost),
                ),
                default=Value(1.0),
                output_field=FloatField(),
            )
        elif self.user_top_categories:
            affinity_multiplier = Case(
                When(product__category_id__in=self.user_top_categories, then=Value(1.35)),
                default=Value(1.0),
                output_field=FloatField()
            )
        elif self.user_onboarding_category_ids:
            affinity_multiplier = Case(
                When(
                    product__category__parent_category_id__in=self.user_onboarding_category_ids,
                    then=Value(product_onboarding_boost),
                ),
                default=Value(1.0),
                output_field=FloatField(),
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
            order_params.extend(['real_distance_meters', 'id'])

        elif sort_by == 'rating':
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

    # Palabras genéricas de intención logística/comercial que el usuario o el LLM suelen
    # mezclar en `query` (ej. "productos con delivery inmediato cerca de mi ubicación").
    # Si se filtran como nombre de producto literal, arruinan el recall.
    ATLAS_INTENT_NOISE_WORDS = frozenset({
        'producto', 'productos', 'articulo', 'articulos', 'cosas', 'algo',
        'con', 'sin', 'para', 'por', 'que', 'tenga', 'tengan', 'tienen', 'hay',
        'delivery', 'domicilio', 'envio', 'inmediato', 'rapido', 'express',
        'cerca', 'cercano', 'cercanos', 'cercana', 'cercanas', 'aqui', 'aca',
        'mi', 'tu', 'su', 'ubicacion', 'zona', 'sector', 'alrededor',
        'abierto', 'abiertos', 'abierta', 'abiertas', 'ahorita', 'ahora', 'hoy',
        'oferta', 'ofertas', 'descuento', 'descuentos', 'promo', 'promocion', 'promociones',
        'token', 'tokens', 'puntos', 'canje', 'canjear',
        'barato', 'baratos', 'barata', 'baratas', 'economico', 'economicos', 'mejor', 'mejores', 'precio', 'precios',
        'tienda', 'tiendas', 'comercio', 'comercios', 'local', 'locales', 'negocio', 'negocios',
        'comprar', 'busco', 'buscar', 'quiero', 'necesito', 'recomienda', 'recomendame', 'mostrar', 'muestrame', 'ver',
        'disponible', 'disponibles', 'stock',
    })

    @classmethod
    def _clean_intent_noise_from_query(cls, raw_query: str) -> tuple:
        """
        Separa las palabras de intención logística/comercial del término real de producto.
        Retorna `(clean_product_query, inferred_flags_dict)`.
        Si el usuario pidió 'Productos con delivery inmediato cerca de mi ubicación',
        `clean_product_query` queda `''` (modo descubrimiento) e infiere filtros útiles.
        """
        if not raw_query or not str(raw_query).strip():
            return "", {}

        raw_str = str(raw_query).strip()
        # Normalizar tildes básicas para comparar con ATLAS_INTENT_NOISE_WORDS
        norm = (
            raw_str.lower()
            .replace('á', 'a').replace('é', 'e').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u')
        )
        tokens = re.findall(r'[a-z0-9ñ]+', norm)
        inferred = {}

        if any(w in tokens for w in ('abierto', 'abiertos', 'abierta', 'abiertas', 'ahorita', 'ahora', 'inmediato', 'rapido', 'express')):
            inferred['prefer_open_now'] = True
        if any(w in tokens for w in ('oferta', 'ofertas', 'descuento', 'descuentos', 'promo', 'promocion', 'promociones')):
            inferred['only_offers'] = True
        if any(w in tokens for w in ('token', 'tokens', 'puntos', 'canje', 'canjear')):
            inferred['only_token_discounts'] = True
        if any(w in tokens for w in ('barato', 'baratos', 'barata', 'baratas', 'economico', 'economicos')):
            inferred['mode'] = 'cheap'
        elif any(w in tokens for w in ('cerca', 'cercano', 'cercanos', 'inmediato', 'delivery', 'domicilio')):
            inferred['mode'] = 'nearby'

        kept_words = []
        for orig_word in raw_str.split():
            w_clean = (
                re.sub(r'[^a-záéíóúñ0-9]', '', orig_word.lower())
                .replace('á', 'a').replace('é', 'e').replace('í', 'i')
                .replace('ó', 'o').replace('ú', 'u')
            )
            if w_clean and w_clean not in cls.ATLAS_INTENT_NOISE_WORDS and len(w_clean) >= 2:
                kept_words.append(orig_word)

        return " ".join(kept_words).strip(), inferred

    @staticmethod
    def _compute_bearing_and_cardinal(lat1: float, lng1: float, lat2: float, lng2: float) -> tuple:
        """
        Calcula el rumbo (bearing en grados 0-360) y punto cardinal desde (lat1, lng1) hacia (lat2, lng2)
        para que el frontend pueda animar radares direccionales, flechas 3D o trayectorias de cámara.
        """
        try:
            phi1 = math.radians(float(lat1))
            phi2 = math.radians(float(lat2))
            delta_lng = math.radians(float(lng2) - float(lng1))
            x = math.sin(delta_lng) * math.cos(phi2)
            y = math.cos(phi1) * math.sin(phi2) - (math.sin(phi1) * math.cos(phi2) * math.cos(delta_lng))
            initial_bearing = math.degrees(math.atan2(x, y))
            compass_bearing = round((initial_bearing + 360) % 360, 1)
            directions = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
            idx = int(round(compass_bearing / 45.0)) % 8
            return compass_bearing, directions[idx]
        except Exception:
            return 0.0, "N"

    @staticmethod
    def _estimate_travel_times(distance_meters: float) -> dict:
        """
        Estimación determinista de tiempos de traslado/entrega según distancia en línea recta
        con factor de tortuosidad urbana venezolana (1.35x).
        """
        if distance_meters is None:
            return {"walking_minutes": None, "moto_delivery_minutes": None, "driving_minutes": None}
        road_m = max(50.0, float(distance_meters) * 1.35)
        walking_min = max(1, int(round(road_m / 75.0)))          # ~4.5 km/h caminando
        moto_delivery_min = max(5, int(round(road_m / 420.0)) + 6)  # ~25 km/h moto urbana + despacho
        driving_min = max(2, int(round(road_m / 500.0)) + 2)     # ~30 km/h carro urbano
        return {
            "walking_minutes": walking_min,
            "moto_delivery_minutes": moto_delivery_min,
            "driving_minutes": driving_min,
        }

    def _apply_purchase_text_filter(self, queryset, query: str):
        """Recall alto para Atlas: sinónimos VE + trigram + tokens + categorías padre/hija."""
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
                    | Q(product__category__parent_category__name__iregex=pattern)
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
                    | Q(product__category__parent_category__name__iregex=pattern)
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
            category.get('parent_category_name'),
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

    @staticmethod
    def _match_variant_for_query(product_json: dict, query: str, attr_filter: str = "") -> dict | None:
        """
        Si el producto tiene variantes (ej. 250g/500g/1kg, Talla 42, 256GB) y el usuario
        mencionó alguna en la búsqueda, devuelve la variante exacta para que Flutter
        la pre-seleccione automáticamente.
        """
        variants = product_json.get('variants') or []
        if not variants or not isinstance(variants, list):
            return None
        combined = f"{query or ''} {attr_filter or ''}".strip().lower()
        if not combined:
            return None
        tokens = [t for t in re.findall(r'[a-z0-9ñ.]+', combined) if len(t) >= 1]
        best_var = None
        best_hits = 0
        for v in variants:
            if not isinstance(v, dict) or not v.get('is_available', True):
                continue
            v_text = f"{v.get('name', '')} {' '.join(str(val) for val in (v.get('options') or {}).values())}".lower()
            hits = sum(1 for t in tokens if t in v_text)
            if hits > best_hits:
                best_hits = hits
                best_var = v
        return best_var if best_hits > 0 else None

    @staticmethod
    def _compute_token_discount_opportunity(product_json: dict, effective_price: float, user_tokens: int, company) -> dict:
        """
        Calcula determinísticamente qué descuento por tokens puede desbloquear el usuario
        AHORA MISMO con su saldo en `TokenWallet`, o cuántos tokens le faltan para el siguiente nivel,
        además de cuántos tokens ganará al comprar este producto.
        """
        gamification_on = bool(getattr(company, 'gamification_enabled', False))
        tokens_per_dollar = int(getattr(company, 'gamification_tokens_per_dollar', 0) or 0) if gamification_on else 0
        tokens_earned = int(math.floor(max(0.0, float(effective_price)) * tokens_per_dollar)) if tokens_per_dollar > 0 else 0

        discounts_active = bool(product_json.get('discounts_by_tokens_active')) and gamification_on
        raw_tiers = product_json.get('discounts_data') if discounts_active else []
        valid_tiers = []
        if isinstance(raw_tiers, list):
            for t in raw_tiers:
                if isinstance(t, dict):
                    try:
                        t_tok = int(t.get('tokens', 0))
                        t_pct = float(t.get('percentage', 0))
                        if t_tok > 0 and 0 < t_pct <= 100:
                            valid_tiers.append({'tokens': t_tok, 'percentage': t_pct})
                    except (ValueError, TypeError):
                        continue
        valid_tiers.sort(key=lambda x: x['percentage'], reverse=True)

        best_affordable = None
        next_goal = None
        if valid_tiers:
            for tier in valid_tiers:
                if user_tokens >= tier['tokens']:
                    savings = round(effective_price * (tier['percentage'] / 100.0), 2)
                    best_affordable = {
                        'tokens': tier['tokens'],
                        'percentage': tier['percentage'],
                        'savings_usd': savings,
                        'final_price_usd': round(max(0.0, effective_price - savings), 2),
                    }
                    break
            # El tier más accesible que aún no alcanza
            unreached = [t for t in valid_tiers if t['tokens'] > user_tokens]
            if unreached:
                closest = min(unreached, key=lambda x: x['tokens'])
                savings = round(effective_price * (closest['percentage'] / 100.0), 2)
                next_goal = {
                    'tokens_needed': closest['tokens'],
                    'tokens_missing': max(0, closest['tokens'] - user_tokens),
                    'percentage': closest['percentage'],
                    'potential_savings_usd': savings,
                }

        return {
            'gamification_enabled': gamification_on,
            'tokens_per_dollar': tokens_per_dollar,
            'user_wallet_balance': int(user_tokens or 0),
            'tokens_earned_on_purchase': tokens_earned,
            'discounts_by_tokens_active': discounts_active,
            'available_tiers': valid_tiers,
            'best_tier_affordable': best_affordable,
            'next_tier_goal': next_goal,
        }

    def _batch_enrich_finalists(
        self,
        finalists_light: list,
        location_label: str,
        query: str,
        attr_filter: str = "",
    ) -> list:
        """
        Hidrata los finalistas en lote (0 consultas N+1) agregando:
        - Coordenadas exactas de la tienda (`store_coordinates`), rumbo (`bearing_degrees`, `cardinal_direction`)
          y tiempos estimados de traslado (`estimated_travel`).
        - Detalles completos de ubicación/centro comercial (`store_location_details`) y `contact_methods`.
        - Billetera de tokens del usuario en cada comercio (`user_wallet_balance`, `token_opportunity`).
        - Video historia activa de 30s asociada al producto o a la tienda (`associated_video_story`).
        - Badges inteligentes de comparación (`atlas_badges`) y variante pre-seleccionada (`matched_variant`).
        """
        if not finalists_light:
            return []

        items = [f['_item'] for f in finalists_light]
        item_ids = [it.id for it in items]
        store_ids = list({it.store_id for it in items})
        company_ids = list({it.store.company_id for it in items})

        # 1. Batch query: TokenWallet del usuario autenticado (1 sola consulta SQL)
        wallet_by_company = {}
        if self.user and getattr(self.user, 'is_authenticated', False) and company_ids:
            for cid, bal in TokenWallet.objects.filter(
                user=self.user, company_id__in=company_ids
            ).values_list('company_id', 'balance'):
                wallet_by_company[str(cid)] = int(bal or 0)

        # 2. Batch query: Video Historias activas (30s) asociadas al ítem o al comercio (1 sola consulta SQL)
        video_by_item = {}
        video_by_company = {}
        if company_ids:
            now_ts = timezone.now()
            active_videos = (
                CompanyVideoStory.objects.filter(expires_at__gt=now_ts)
                .filter(Q(associated_item_id__in=item_ids) | Q(company_id__in=company_ids))
                .exclude(video_file__isnull=True)
                .exclude(video_file__exact='')
                .select_related('company')
                .order_by('-creation')[:30]
            )
            for vid in active_videos:
                v_payload = {
                    'video_id': str(vid.id),
                    'video_url': storage_manager.get_url(vid.video_file) if vid.video_file else None,
                    'thumbnail_url': storage_manager.get_url(vid.thumbnail) if vid.thumbnail else None,
                    'duration_seconds': float(vid.duration_seconds or 0.0),
                    'description': vid.description or '',
                    'views_count': int(vid.views_count or 0),
                    'company_id': str(vid.company_id),
                    'company_name': vid.company.name,
                    'associated_item_id': str(vid.associated_item_id) if vid.associated_item_id else None,
                }
                if vid.associated_item_id and str(vid.associated_item_id) not in video_by_item:
                    video_by_item[str(vid.associated_item_id)] = {**v_payload, 'is_direct_product_video': True}
                if str(vid.company_id) not in video_by_company:
                    video_by_company[str(vid.company_id)] = {**v_payload, 'is_direct_product_video': False}

        # 3. Batch query: Métodos de contacto de las sucursales (1 sola consulta SQL)
        contacts_by_store = {}
        if store_ids:
            for cm in StoreContactMethod.objects.filter(store_id__in=store_ids):
                s_map = contacts_by_store.setdefault(str(cm.store_id), {})
                try:
                    key_name = ContactMethodType(cm.method_type).name.lower()
                except ValueError:
                    key_name = str(cm.method_type)
                s_map[key_name] = cm.value

        results = []
        user_lat = float(self.user_location.y)
        user_lng = float(self.user_location.x)

        for light in finalists_light:
            item = light['_item']
            payload = self._serialize_purchase_item(item, location_label, query)
            payload['purchase_score'] = light['purchase_score']
            payload['triad'] = light['triad']

            place = self._resolve_item_place(item)
            self.purchase_places[str(item.id)] = place

            location = getattr(item.store, 'location', None)
            coords = getattr(location, 'coordinates', None)
            store_lat = float(coords.y) if coords else None
            store_lng = float(coords.x) if coords else None

            if store_lat is not None and store_lng is not None:
                bearing_deg, cardinal_dir = self._compute_bearing_and_cardinal(
                    user_lat, user_lng, store_lat, store_lng
                )
            else:
                bearing_deg, cardinal_dir = 0.0, "N"

            dist_m = payload.get('distance_meters')
            travel_info = self._estimate_travel_times(dist_m)
            company = item.store.company
            company_id_str = str(company.id)
            store_id_str = str(item.store_id)

            try:
                store_type_label = str(StoreType(item.store.store_type).label)
            except Exception:
                store_type_label = "Local comercial"

            payload['company_id'] = company_id_str
            payload['store_coordinates'] = {
                'lat': store_lat,
                'lng': store_lng,
            }
            payload['user_reference_coordinates'] = {
                'lat': user_lat,
                'lng': user_lng,
                'label': location_label,
            }
            payload['bearing_degrees'] = bearing_deg
            payload['cardinal_direction'] = cardinal_dir
            payload['estimated_travel'] = travel_info
            payload['store_location_details'] = {
                'zone': place.get('zone'),
                'address': place.get('address'),
                'reference_details': (getattr(location, 'details', None) or '').strip() or None,
                'proximity_label': place.get('proximity'),
                'is_mall': bool(place.get('mall_name')),
                'mall_id': getattr(location, 'mall_id', None),
                'mall_name': place.get('mall_name'),
                'mall_floor': place.get('mall_floor'),
                'store_type': item.store.store_type,
                'store_type_label': store_type_label,
                'store_img_url': storage_manager.get_url(item.store.store_img_url) if item.store.store_img_url else None,
                'company_presentation_video_url': (
                    storage_manager.get_url(company.presentation_video_url)
                    if company.presentation_video_url else None
                ),
            }
            payload['contact_methods'] = contacts_by_store.get(store_id_str, {})

            # Gamificación y Billetera de Tokens del usuario
            user_tokens = wallet_by_company.get(company_id_str, 0)
            token_opp = self._compute_token_discount_opportunity(
                payload.get('product') or {},
                float(payload.get('effective_price') or 0.0),
                user_tokens,
                company,
            )
            payload['user_wallet_balance'] = user_tokens
            payload['tokens_earned_on_purchase'] = token_opp['tokens_earned_on_purchase']
            payload['token_opportunity'] = token_opp

            # Video Historia de 30s (directa del producto o promocional de la tienda)
            payload['associated_video_story'] = (
                video_by_item.get(str(item.id))
                or video_by_company.get(company_id_str)
            )

            # Variante coincidente si el usuario pidió un peso/talla/capacidad específica
            payload['matched_variant'] = self._match_variant_for_query(
                payload.get('product') or {}, query, attr_filter
            )
            payload['atlas_badges'] = []
            results.append(payload)

        # 4. Asignación determinista de `atlas_badges` comparativos entre los finalistas
        if results:
            valid_prices = [float(r['effective_price']) for r in results if r.get('effective_price') is not None]
            min_price_val = min(valid_prices) if valid_prices else None

            open_with_dist = [
                r for r in results
                if r.get('is_open_now') and r.get('distance_meters') is not None
            ]
            nearest_open_id = (
                min(open_with_dist, key=lambda r: float(r['distance_meters']))['id']
                if open_with_dist else None
            )

            rated_candidates = [
                r for r in results
                if max(float(r.get('avg_rating') or 0.0), float(r.get('merchant_avg_rating') or 0.0)) >= 4.0
            ]
            top_rated_id = (
                max(
                    rated_candidates,
                    key=lambda r: max(float(r.get('avg_rating') or 0.0), float(r.get('merchant_avg_rating') or 0.0)),
                )['id']
                if rated_candidates else None
            )

            for r in results:
                badges = []
                if min_price_val is not None and float(r.get('effective_price') or 0) <= min_price_val + 0.005:
                    badges.append('BEST_PRICE')
                if nearest_open_id and str(r.get('id')) == str(nearest_open_id):
                    badges.append('NEAREST_OPEN')
                if top_rated_id and str(r.get('id')) == str(top_rated_id):
                    badges.append('TOP_RATED')
                if int(r.get('offer_percentage') or 0) > 0:
                    badges.append('FLASH_OFFER')
                tok_opp = r.get('token_opportunity') or {}
                if tok_opp.get('best_tier_affordable'):
                    badges.append('TOKEN_SAVINGS_READY')
                elif tok_opp.get('tokens_earned_on_purchase', 0) > 0:
                    badges.append('EARNS_TOKENS')
                if r.get('associated_video_story'):
                    badges.append('HAS_VIDEO_REEL')
                if r.get('is_platinum'):
                    badges.append('PLATINUM_MERCHANT')
                r['atlas_badges'] = badges

        return results

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
        parent_cat = category.parent_category if (category and category.parent_category_id) else None
        offer = item._active_offer()

        if variants:
            matches_lexically = lexical_match(
                [
                    product.name,
                    product.description,
                    category.name if category else None,
                    parent_cat.name if parent_cat else None,
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
        query: str = "",
        max_distance_meters: float = 15000.0,
        limit: int = 8,
        location_label: str = 'Tu ubicación actual',
        mode: str = 'best',
        min_distance_meters: float = 0.0,
        category_query: str = None,
        company_or_store_query: str = None,
        only_open_now: bool = False,
        only_offers: bool = False,
        only_token_discounts: bool = False,
        only_user_redeemable_tokens: bool = False,
        min_price: float = None,
        max_price: float = None,
        selling_unit: str = None,
        attribute_or_variant_query: str = None,
        mall_only: bool = False,
    ) -> list:
        """
        Candidatos para Atlas 2.0: stock vivo, geo, matching VE, filtros estructurados
        (categoría, ofertas, tiendas abiertas, tokens, rango de precio, unidades/variantes, C.C.)
        y enriquecimiento espacial/multimedia en lote.
        """
        raw_query = (query or "").strip()
        cleaned_query, inferred = self._clean_intent_noise_from_query(raw_query)

        # Si el query original era SOLO ruido logístico (ej. "productos con delivery inmediato cerca"),
        # usamos búsqueda abierta por filtros en vez de buscar la palabra literal "delivery".
        effective_query = cleaned_query
        if not effective_query and inferred:
            if inferred.get('only_offers') and not only_offers:
                only_offers = True
            if inferred.get('only_token_discounts') and not only_token_discounts:
                only_token_discounts = True
            if inferred.get('mode') and mode == 'best':
                mode = inferred['mode']

        prefer_open_now = bool(only_open_now or inferred.get('prefer_open_now'))

        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = self._annotate_merchant_rating(qs)
        # Un solo JOIN para todo lo que get_json()/is_currently_open/effective_work_* tocan.
        qs = qs.select_related(
            'product',
            'product__category',
            'product__category__parent_category',
            'product__company',
            'offer',
            'store',
            'store__location',
            'store__location__mall',
            'store__company',
        )
        qs = qs.filter(
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        if min_distance_meters and min_distance_meters > 0:
            qs = qs.filter(
                store__location__coordinates__distance_gt=(self.user_location, D(m=min_distance_meters))
            )

        # --- FILTROS ESTRUCTURADOS DE ATLAS 2.0 ---
        if category_query and str(category_query).strip():
            cat_pat = substring_regex(str(category_query).strip())
            qs = qs.filter(
                Q(product__category__name__iregex=cat_pat)
                | Q(product__category__parent_category__name__iregex=cat_pat)
                | Q(store__company__category__name__iregex=cat_pat)
            )

        if company_or_store_query and str(company_or_store_query).strip():
            comp_pat = substring_regex(str(company_or_store_query).strip())
            qs = qs.filter(
                Q(store__company__name__iregex=comp_pat)
                | Q(store__name__iregex=comp_pat)
                | Q(store__location__mall__name__iregex=comp_pat)
            )

        if only_offers:
            qs = qs.filter(offer__isnull=False, offer__valid_until__gte=timezone.now())

        if only_token_discounts:
            qs = qs.filter(
                store__company__gamification_enabled=True,
                product__discounts_by_tokens_active=True,
            )

        if only_user_redeemable_tokens and self.user and getattr(self.user, 'is_authenticated', False):
            user_company_ids = list(
                TokenWallet.objects.filter(user=self.user, balance__gt=0).values_list('company_id', flat=True)
            )
            if user_company_ids:
                qs = qs.filter(store__company_id__in=user_company_ids)
            else:
                qs = qs.filter(
                    store__company__gamification_enabled=True,
                    product__discounts_by_tokens_active=True,
                )

        if mall_only:
            qs = qs.filter(store__location__mall__isnull=False)

        if selling_unit and str(selling_unit).strip():
            qs = qs.filter(product__selling_unit__iexact=str(selling_unit).strip())

        qs = qs.annotate(effective_price=Coalesce(F('custom_price'), F('product__price')))

        if min_price is not None:
            try:
                qs = qs.filter(effective_price__gte=float(min_price))
            except (ValueError, TypeError):
                pass
        if max_price is not None:
            try:
                qs = qs.filter(effective_price__lte=float(max_price))
            except (ValueError, TypeError):
                pass

        if attribute_or_variant_query and str(attribute_or_variant_query).strip():
            attr_str = str(attribute_or_variant_query).strip()
            attr_pat = substring_regex(attr_str)
            qs = qs.annotate(
                attrs_text=Cast('product__attributes', output_field=CharField()),
                vars_text=Cast('product__variants', output_field=CharField()),
            ).filter(
                Q(attrs_text__iregex=attr_pat)
                | Q(vars_text__iregex=attr_pat)
                | Q(product__name__iregex=attr_pat)
                | Q(product__description__iregex=attr_pat)
            )

        if effective_query:
            qs = self._apply_purchase_text_filter(qs, effective_query)

        # Ordenar por similitud semántica si se aplicó el filtro de texto, o por cercanía y popularidad
        if 'match_sim' in qs.query.annotations:
            qs = qs.order_by('-match_sim', 'real_distance_meters', 'effective_price')
        else:
            qs = qs.order_by('real_distance_meters', '-cached_popularity_score', 'effective_price')

        variants = expand_search_variants(effective_query) if effective_query else []

        # Pool ligero: solo los valores necesarios para el score, sin get_json().
        pool = []
        seen = set()
        for item in qs[:80]:
            item_id = str(item.id)
            if item_id in seen:
                continue
            seen.add(item_id)
            pool.append(self._build_purchase_light_record(item, variants))

        # Si hay filtro de solo abiertos ahora, filtramos (con fallback inteligente si ninguno está abierto a esa hora)
        if only_open_now:
            open_pool = [p for p in pool if p.get('is_open_now')]
            if open_pool:
                pool = open_pool
        elif prefer_open_now:
            open_pool = [p for p in pool if p.get('is_open_now')]
            if len(open_pool) >= min(3, len(pool)):
                pool = open_pool

        scored = self._score_purchase_payloads(pool, mode=mode)
        finalists = self._diversify_purchase_results(scored, limit=limit, max_per_company=2)

        return self._batch_enrich_finalists(
            finalists,
            location_label=location_label,
            query=effective_query or raw_query,
            attr_filter=attribute_or_variant_query or "",
        )

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
            'address': (location.name or '').strip() or None,
            'proximity': proximity_label(item._distance_meters_value()),
            'mall_name': mall_name,
            'mall_floor': mall_floor,
        }

    # Anillos de expansión (metros). Cada anillo cubre SOLO la franja entre el
    # radio anterior y el siguiente: nunca se vuelve a consultar lo ya buscado.
    PURCHASE_EXPANSION_RADII_M = (40000.0, 100000.0, 250000.0, 600000.0, 1500000.0)

    def search_purchase_expanding(
        self,
        query: str = "",
        base_radius_meters: float = 15000.0,
        limit: int = 6,
        location_label: str = 'Tu ubicación actual',
        mode: str = 'best',
        **filter_kwargs,
    ) -> dict:
        """
        Busca en el radio base y, si no hay nada, avanza por anillos concéntricos
        disjuntos hasta encontrar existencias. Acepta todos los filtros estructurados
        de `search_purchase_candidates` vía `**filter_kwargs`.
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
            **filter_kwargs,
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
                **filter_kwargs,
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

    @staticmethod
    def _parse_requested_quantity(qty_str: str, product_json: dict) -> float:
        """
        Interpreta una cantidad expresada en texto (ej. '500g', '0.5 kg', '2 unidades', '3')
        y la adapta a la unidad de venta (`selling_unit`) y reglas (`allow_fractional_quantity`, `min_order_quantity`)
        del producto para que el `smart_bundle` tenga cantidades listas para agregar al carrito.
        """
        selling_unit = (product_json.get('selling_unit') or 'unit').lower()
        allow_frac = bool(product_json.get('allow_fractional_quantity', False))
        min_qty = float(product_json.get('min_order_quantity') or 1.0)
        if not qty_str or not str(qty_str).strip():
            return min_qty if allow_frac else max(1.0, round(min_qty))

        raw = str(qty_str).strip().lower().replace(',', '.')
        if 'medio' in raw or '1/2' in raw:
            num = 0.5
        elif 'cuarto' in raw or '1/4' in raw:
            num = 0.25
        else:
            m = re.search(r'(\d+(?:\.\d+)?)', raw)
            num = float(m.group(1)) if m else 1.0

        # Conversión automática entre gramos y kilogramos o ml y litros
        if ('g' in raw and 'kg' not in raw and 'kilo' not in raw) and selling_unit == 'kg' and num >= 25:
            num = round(num / 1000.0, 3)
        elif ('kg' in raw or 'kilo' in raw) and selling_unit == 'g' and num <= 20:
            num = round(num * 1000.0, 1)
        elif ('ml' in raw) and selling_unit == 'l' and num >= 50:
            num = round(num / 1000.0, 3)

        if not allow_frac:
            return float(max(1, int(round(num))))
        return float(max(min_qty, round(num, 3)))

    def resolve_shopping_list(
        self,
        needs: list,
        max_distance_meters: float = 15000.0,
        location_label: str = 'Tu ubicación actual',
        mode: str = 'best',
        budget_usd: float = None,
    ) -> dict:
        """
        Arma un plan inteligente de compras (receta, mercado, combo o presupuesto)
        priorizando consolidar en la menor cantidad de paradas posibles, calculando:
        - `route_stops`: Ruta geográfica ordenada por cercanía con coordenadas (lat, lng) y rumbo.
        - `one_tap_cart_batches`: Lotes listos para despachar al carrito en 1 toque.
        - `estimated_total_usd`, `estimated_total_with_tokens_usd`, `within_budget`.
        """
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
                    'company_id': candidate.get('company_id'),
                    'company_name': candidate.get('company_name'),
                    'company_image': candidate.get('company_image'),
                    'distance_meters': candidate.get('distance_meters'),
                    'store_coordinates': candidate.get('store_coordinates'),
                    'bearing_degrees': candidate.get('bearing_degrees'),
                    'cardinal_direction': candidate.get('cardinal_direction'),
                    'estimated_travel': candidate.get('estimated_travel'),
                    'store_location_details': candidate.get('store_location_details'),
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
        items_plan = []
        missing = []
        used_ids = set()
        need_qty_by_item_id = {}

        if primary:
            for bucket in buckets:
                pick = primary['by_need'].get(bucket['query'])
                if pick:
                    found_items.append(pick)
                    used_ids.add(str(pick['id']))
                    need_qty_by_item_id[str(pick['id'])] = (bucket['query'], bucket.get('cantidad', ''))
                else:
                    missing.append(bucket)

            # Completar faltantes con el mejor candidato global (otra tienda).
            still_missing = []
            for bucket in missing:
                alts = [c for c in bucket['candidates'] if str(c['id']) not in used_ids]
                if alts:
                    picked_alt = alts[0]
                    found_items.append(picked_alt)
                    used_ids.add(str(picked_alt['id']))
                    need_qty_by_item_id[str(picked_alt['id'])] = (bucket['query'], bucket.get('cantidad', ''))
                    bucket['filled_elsewhere'] = picked_alt
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

        # Construcción del plan detallado de cantidades, ruta de paradas y lotes 1-Tap Cart
        total_usd = 0.0
        total_with_tokens_usd = 0.0
        stops_map = {}

        for item in found_items:
            item_id_str = str(item['id'])
            need_query, raw_qty_str = need_qty_by_item_id.get(item_id_str, (item.get('match_query', ''), ''))
            prod_json = item.get('product') or {}
            matched_var = self._match_variant_for_query(prod_json, need_query, raw_qty_str)
            qty_val = self._parse_requested_quantity(raw_qty_str, prod_json)

            unit_price = float(
                matched_var.get('price')
                if (matched_var and matched_var.get('price') is not None)
                else (item.get('effective_price') or 0.0)
            )
            line_subtotal = round(unit_price * qty_val, 2)

            tok_opp = item.get('token_opportunity') or {}
            best_tok = tok_opp.get('best_tier_affordable')
            line_token_savings = float(best_tok['savings_usd']) if best_tok else 0.0
            line_net_with_tokens = round(max(0.0, line_subtotal - line_token_savings), 2)

            total_usd = round(total_usd + line_subtotal, 2)
            total_with_tokens_usd = round(total_with_tokens_usd + line_net_with_tokens, 2)

            plan_entry = {
                'need_query': need_query,
                'requested_amount_text': raw_qty_str or f"{qty_val:g} {prod_json.get('unit_label', 'und')}",
                'inventory_item_id': item_id_str,
                'product_id': str(prod_json.get('id', '')),
                'product_name': prod_json.get('name', ''),
                'product_image': (prod_json.get('images') or [None])[0],
                'store_id': str(item.get('store_id')),
                'store_name': item.get('store_name'),
                'company_name': item.get('company_name'),
                'recommended_quantity': qty_val,
                'selling_unit': prod_json.get('selling_unit', 'unit'),
                'unit_label': prod_json.get('unit_label', 'und'),
                'unit_price_usd': round(unit_price, 2),
                'subtotal_usd': line_subtotal,
                'subtotal_with_tokens_usd': line_net_with_tokens,
                'selected_variant': matched_var,
                'token_discount_ready': best_tok,
            }
            items_plan.append(plan_entry)

            st_id = str(item.get('store_id'))
            stop = stops_map.setdefault(st_id, {
                'store_id': st_id,
                'store_name': item.get('store_name'),
                'company_id': item.get('company_id'),
                'company_name': item.get('company_name'),
                'company_image': item.get('company_image'),
                'store_coordinates': item.get('store_coordinates'),
                'distance_meters': item.get('distance_meters'),
                'bearing_degrees': item.get('bearing_degrees'),
                'cardinal_direction': item.get('cardinal_direction'),
                'estimated_travel': item.get('estimated_travel'),
                'store_location_details': item.get('store_location_details'),
                'is_open_now': item.get('is_open_now'),
                'subtotal_usd': 0.0,
                'items': [],
                'cart_items_payload': [],
            })
            stop['subtotal_usd'] = round(stop['subtotal_usd'] + line_subtotal, 2)
            stop['items'].append(plan_entry)
            stop['cart_items_payload'].append({
                'id': item_id_str,
                'quantity': qty_val,
                'selected_variant_id': matched_var.get('id') if matched_var else None,
                'token_discount': (
                    {'tokens': best_tok['tokens'], 'percentage': best_tok['percentage']}
                    if best_tok else None
                ),
                'isFromAtlas': True,
            })

        # Ordenar las paradas geográficamente desde la más cercana hasta la más lejana
        route_stops = sorted(
            stops_map.values(),
            key=lambda s: float(s.get('distance_meters') if s.get('distance_meters') is not None else 999999.0),
        )
        for idx, st in enumerate(route_stops, start=1):
            st['stop_number'] = idx

        primary_count = len(primary['by_need']) if primary else 0
        within_budget = (total_usd <= float(budget_usd)) if budget_usd is not None else True

        return {
            'type': 'shopping_plan',
            'primary_store': {
                'store_id': primary.get('store_id') if primary else None,
                'store_name': primary.get('store_name') if primary else None,
                'company_id': primary.get('company_id') if primary else None,
                'company_name': primary.get('company_name') if primary else None,
                'company_image': primary.get('company_image') if primary else None,
                'store_coordinates': primary.get('store_coordinates') if primary else None,
                'distance_meters': primary.get('distance_meters') if primary else None,
                'bearing_degrees': primary.get('bearing_degrees') if primary else None,
                'cardinal_direction': primary.get('cardinal_direction') if primary else None,
                'estimated_travel': primary.get('estimated_travel') if primary else None,
                'store_location_details': primary.get('store_location_details') if primary else None,
                'is_open_now': primary.get('is_open_now') if primary else None,
                'items_in_store': primary_count,
                'needs_total': len(buckets),
            } if primary else None,
            'found': found_items,
            'items_plan': items_plan,
            'route_stops': route_stops,
            'one_tap_cart_batches': [
                {
                    'store_id': st['store_id'],
                    'store_name': st['store_name'],
                    'company_name': st['company_name'],
                    'subtotal_usd': st['subtotal_usd'],
                    'items': st['cart_items_payload'],
                }
                for st in route_stops
            ],
            'missing_queries': [b['query'] for b in missing],
            'filled_elsewhere': [
                {
                    'query': b['query'],
                    'item_name': b['filled_elsewhere'].get('product', {}).get('name'),
                    'store_id': str(b['filled_elsewhere'].get('store_id')),
                    'store_name': b['filled_elsewhere'].get('store_name'),
                    'company_name': b['filled_elsewhere'].get('company_name'),
                    'store_coordinates': b['filled_elsewhere'].get('store_coordinates'),
                }
                for b in filled_elsewhere
            ],
            'alternatives': alternatives,
            'estimated_total_usd': total_usd,
            'estimated_total_with_tokens_usd': total_with_tokens_usd,
            'total_token_savings_usd': round(max(0.0, total_usd - total_with_tokens_usd), 2),
            'budget_usd': float(budget_usd) if budget_usd is not None else None,
            'within_budget': within_budget,
            'budget_remaining_usd': round(float(budget_usd) - total_usd, 2) if budget_usd is not None else None,
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

    def _stamp_viewer_likes(self, items: list) -> list:
        """is_liked sale del usuario que pide el feed, no del que llenó el caché."""
        if not items:
            return items
        if not self.user or not self.user.is_authenticated:
            for item in items:
                if isinstance(item, dict) and 'is_liked' in item:
                    item['is_liked'] = False
            return items
        product_ids = [
            str(item.get('id')) for item in items
            if isinstance(item, dict) and item.get('feed_type') != 'video' and item.get('id')
        ]
        liked = set()
        if product_ids:
            product_ct = ContentType.objects.get_for_model(InventoryItem)
            liked = set(UniversalLike.objects.filter(
                user=self.user,
                content_type=product_ct,
                object_id__in=product_ids,
            ).values_list('object_id', flat=True))
        for item in items:
            if isinstance(item, dict) and 'is_liked' in item:
                item['is_liked'] = str(item.get('id')) in liked
        return items

    def _get_merchant_exclusion_scope(self) -> str:
        if self.user and self.user.is_authenticated:
            try:
                return f":excl_{self.user.company.id}"
            except Company.DoesNotExist:
                pass
        return ""

    def _get_cached_structural_feed(self, base_cache_key: str, queryset, page: int, page_size: int) -> list:
        """
        Abstracción DRY para resolver el Nivel Estructural de CUALQUIER feed.
        Hace el corte de paginación directo en PostgreSQL.
        """
        # Le pegamos el alcance de exclusión de comercio (si aplica), la página y el tamaño a la llave para aislar la memoria
        cache_key = f"{base_cache_key}{self._get_merchant_exclusion_scope()}:p_{page}:sz_{page_size}"
        
        structural_feed = cache.get(cache_key)
        
        if structural_feed is None:
            # 1. Calculamos el offset y limit para SQL
            start = (page - 1) * page_size
            end = start + page_size
            
            # 2. Slicing en SQL e INYECCIÓN del feed_type
            structural_feed = []
            for item in queryset[start:end]:
                item_data = item.get_json()
                item_data["feed_type"] = "product"
                structural_feed.append(item_data)
            
            # 3. Guardamos la estructura en Redis por 10 minutos (incluyendo [] para evitar cache miss perpetuo)
            cache.set(cache_key, structural_feed, timeout=600)

        if not structural_feed:
            return []

        # Copia: is_liked y estados volátiles se inyectan en _stitch_and_filter_results
        structural_feed = [dict(item) for item in structural_feed]
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
        affinity_hash = self._get_affinity_hash() if (sort_by == 'relevance' and not price_order) else "global"
        
        base_cache_key = f"cartmaker:struct:offers:{approx_lat}:{approx_lng}:{affinity_hash}:{sort_by}:{price_order}"
        
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
        affinity_hash = self._get_affinity_hash()
        
        # Llave de Redis aislada por página y alcance de comerciante
        cache_key = f"cartmaker:struct:home:{approx_lat}:{approx_lng}:{affinity_hash}{self._get_merchant_exclusion_scope()}:seed_{self.seed}:p_{page}:sz_{page_size}"
        structural_page_feed = cache.get(cache_key)

        # 🕵️ ESPÍA 2: ¿Qué llave estamos buscando?
        print(f"🔍 [CACHE] Llave solicitada: {cache_key}")
        
        if structural_page_feed is None:
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

            qs_products_base = self._get_base_active_queryset()
            qs_products_base = self._annotate_proximity_flag(qs_products_base)

            qs_products_local = qs_products_base.filter(
                store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
            )
            qs_products_local = self._annotate_ranking_score(qs_products_local)
            qs_products_local = self._apply_monopoly_prevention(qs_products_local)

            home_horizon = timezone.now() - timedelta(days=45)
            # 💡 FILTRO INTELIGENTE: Pasan los nuevos OR los que tienen actividad viva (> 0)
            qs_products_recent = qs_products_local.filter(
                Q(creation__gte=home_horizon) | Q(cached_popularity_score__gt=0.0)
            )
            
            # Slicing dinámico de productos en SQL con el punto de partida real
            products_list = list(qs_products_recent[p_start:p_end])

            # Fallback 1: Si el horizonte de 45 días deja la página vacía o incompleta en esta zona,
            # usamos todo el inventario activo de la zona sin restricción de antigüedad.
            if len(products_list) < products_needed:
                products_list = list(qs_products_local[p_start:p_end])

            # Fallback 2: Si en el radio local (15km) no hay absolutamente ningún video ni producto
            # en la página 1, abrimos el radio para no dejar jamás el feed en blanco.
            if page == 1 and not videos_list and not products_list:
                qs_fallback_videos = self._get_base_video_queryset().filter(
                    company__stores__is_main_store=True,
                    company__stores__is_active=True,
                ).distinct()
                qs_fallback_videos = self._annotate_video_ranking(qs_fallback_videos)
                qs_fallback_videos = self._apply_video_monopoly_prevention(qs_fallback_videos)
                videos_list = list(qs_fallback_videos[:ideal_videos_count])

                fallback_products_needed = page_size - len(videos_list)
                qs_fallback_products = self._annotate_ranking_score(qs_products_base)
                qs_fallback_products = self._apply_monopoly_prevention(qs_fallback_products)
                products_list = list(qs_fallback_products[:fallback_products_needed])
            
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
                cache.set(cache_key, [], timeout=600)
                return {"results": []}

            # 3. ENTRELAZAMOS
            structural_page_feed = self._interleave_feeds(videos_list, products_list, v_ratio=3, p_ratio=1)
            
            # Guardamos el esqueleto de la página por 10 minutos
            cache.set(cache_key, structural_page_feed, timeout=600)
            
        # 4. STITCHING VOLÁTIL (incluye inyección de is_liked y likes_count)
        final_feed = self._stitch_and_filter_results([dict(item) for item in structural_page_feed]) if structural_page_feed else []
        
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
        cache_key = f"{base_cache_key}:p_{page}:sz_{page_size}"

        cached = cache.get(cache_key)
        if cached is not None:
            if not cached:
                return []
            return self._stitch_and_filter_results([dict(item) for item in cached])
        
        # 1. Obtenemos el ContentType de InventoryItem
        product_ct = ContentType.objects.get_for_model(InventoryItem)
        
        # 💡 FIX: Consultamos UniversalLike directamente.
        liked_ids = list(UniversalLike.objects.filter(
            user=self.user,
            content_type=product_ct
        ).values_list('object_id', flat=True))

        if not liked_ids:
            cache.set(cache_key, [], timeout=600)
            return []

        # Construimos el QuerySet base
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        # Filtramos usando los IDs obtenidos de UniversalLike
        qs = qs.filter(
            id__in=liked_ids,
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

        merchant_avg_sub = MerchantCalification.objects.filter(
            merchant_id=OuterRef('company_id')
        ).values('merchant_id').annotate(avg=Avg('rating')).values('avg')[:1]

        # Filtramos billeteras con saldo > 0 de compañías que tengan tiendas cerca y activas
        wallets = TokenWallet.objects.select_related('company', 'company__category').annotate(
            company_avg_rating=Coalesce(Subquery(merchant_avg_sub, output_field=FloatField()), Value(0.0), output_field=FloatField())
        ).filter(
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
            avg_rating = float(getattr(wallet, 'company_avg_rating', 0.0) or 0.0)
            
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