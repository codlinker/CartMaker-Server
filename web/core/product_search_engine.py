from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F, Q, Exists, FloatField, ExpressionWrapper, Avg, OuterRef
from django.db.models.expressions import Window
from django.db.models.functions import RowNumber, Coalesce
from django.db.models import Case, When, Value, Count, BooleanField
from django.contrib.gis.measure import D

# Ajusta las importaciones según la ruta real de tu proyecto
from web.models import InventoryItem, MerchantSubscription, ProductLike, ProductViewLog

class ProductSearchEngine:
    """
    Motor Híbrido de CartMaker.
    Combina geolocalización, prevención de monopolios, popularidad global 
    y filtrado basado en contenido (afinidad del usuario) en tiempo real.
    """

    def __init__(self, lat: float, lng: float, user=None):
        self.user_location = Point(lng, lat, srid=4326)
        self.user = user
        
        # Al instanciar, construimos su huella digital de intereses
        self.user_top_categories = self._build_user_affinity_profile()
    
    def _build_user_affinity_profile(self):
        """
        Lee el historial de interacciones explícitas (Likes) e implícitas (Vistas largas/Carritos)
        y devuelve una lista con los IDs de sus categorías preferidas.
        """
        if not self.user or not self.user.is_authenticated:
            return []

        # Analizamos los últimos 30 días para mantener la relevancia fresca
        date_threshold = timezone.now() - timedelta(days=30)

        # 1. Señales Explícitas (Likes)
        liked_categories = ProductLike.objects.filter(
            user=self.user,
            creation__gte=date_threshold
        ).values_list('product__product__category_id', flat=True)

        # 2. Señales Implícitas de Alta Intención (Agregó al carrito, compró, o lo miró mucho)
        viewed_categories = ProductViewLog.objects.filter(
            client=self.user,
            start_time__gte=date_threshold
        ).filter(
            Q(added_to_cart=True) | Q(bought=True) | Q(end_time__isnull=False)
        ).values_list('inventory_item__product__category_id', flat=True)

        # Unimos, contamos las frecuencias y sacamos el Top 5 de categorías
        all_categories = list(liked_categories) + list(viewed_categories)
        
        if not all_categories:
            return []

        # Contamos la frecuencia de cada categoría de forma eficiente en Python
        # para no recargar la BD con agregaciones complejas en tablas de logs enormes
        frequency = {}
        for cat_id in all_categories:
            if cat_id:
                frequency[cat_id] = frequency.get(cat_id, 0) + 1

        # Ordenamos de mayor a menor y extraemos los IDs
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
        # 💡 NUEVO: Filtro Anti-Auto-Compra / Anti-Auto-Recomendación
        # =====================================================================
        if self.user and self.user.is_authenticated:
            # Comprobamos si el usuario actual es un comerciante con suscripción vigente.
            # Usamos .exists() para que sea una consulta SQL súper ligera (1ms) sin 
            # traernos todo el objeto a la memoria RAM de Python.
            is_active_merchant = MerchantSubscription.objects.filter(
                merchant=self.user,
                valid_until__gte=now
            ).exists()
            if is_active_merchant:
                # Excluimos todos los productos que vengan de una tienda 
                # cuya compañía sea propiedad de este usuario.
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
        Calcula el Score cruzando Popularidad + Platinum + Perfil de Afinidad Personal.
        """
        # Multiplicador Platino (Estático del vendedor)
        platinum_multiplier = Case(
            When(store__company__is_platinum=True, then=Value(1.10)),
            default=Value(1.0),
            output_field=FloatField()
        )

        # Multiplicador de Afinidad (Dinámico del usuario)
        # Si el producto pertenece al Top 5 de gustos del usuario, le damos un boost del 30%
        if self.user_top_categories:
            affinity_multiplier = Case(
                When(product__category_id__in=self.user_top_categories, then=Value(1.30)),
                default=Value(1.0),
                output_field=FloatField()
            )
        else:
            affinity_multiplier = Value(1.0, output_field=FloatField())

        # Cálculo matemático final dentro de la BD
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
            # 💡 IMPORTANTE: Siempre añade 'id' al final para desempatar
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

    def get_category_feed(self, sub_category_id: int, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000):
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        qs = qs.filter(
            product__category_id=sub_category_id,
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        
        return self._apply_feed_sorting(qs, sort_by, price_order)

    def get_offers_feed(self, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000):
        now = timezone.now()
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        qs = qs.filter(
            offer__isnull=False,
            offer__valid_until__gte=now,
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        
        return self._apply_feed_sorting(qs, sort_by, price_order)

    def get_store_feed(self, store_id: str = None, company_id: str = None, category_id: int = None, price_order: str = None):
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
            return qs.order_by('effective_price' if price_order == 'asc' else '-effective_price')
        else:
            qs = qs.annotate(ranking_score=F('cached_popularity_score'))
            return qs.order_by('-ranking_score')
        
    def get_text_search_feed(self, search_query: str, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000):
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

        return self._apply_feed_sorting(qs, sort_by, price_order)
    
    def get_home_feed(self, max_distance_meters: float = 15000):
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
        return self._apply_monopoly_prevention(qs)
    
    def get_favorites_feed(self, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000):
        if not self.user or not self.user.is_authenticated:
            return InventoryItem.objects.none()

        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        qs = qs.filter(
            likes__user=self.user,
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        
        qs = qs.annotate(is_liked=Value(True, output_field=BooleanField()))
        
        if sort_by == 'relevance' and not price_order:
            qs = qs.annotate(like_date=F('likes__creation')).order_by('-like_date')
            return qs
            
        return self._apply_feed_sorting(qs, sort_by, price_order)