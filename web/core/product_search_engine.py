from datetime import datetime
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F, Q, Exists, FloatField, ExpressionWrapper, Avg, OuterRef
from django.db.models.expressions import Window
from django.db.models.functions import RowNumber, Coalesce
from django.db.models import Case, When, Value, Count, BooleanField
from django.contrib.gis.measure import D

# Ajusta las importaciones según la ruta real de tu proyecto
from web.models import InventoryItem, MerchantSubscription, ProductLike

class ProductSearchEngine:
    """
    Motor centralizado para la búsqueda, filtrado y ranking de productos en CartMaker.
    Maneja la lógica espacial (PostGIS), verificación de suscripciones, filtros de 
    ordenamiento dinámico y el algoritmo de diversificación (Anti-Monopolio).
    """

    def __init__(self, lat: float, lng: float):
        """
        Inicializa el motor con la ubicación actual del usuario.
        """
        self.user_location = Point(lng, lat, srid=4326)
    
    def _get_base_active_queryset(self):
        """
        Aplica los filtros CRÍTICOS del negocio y pre-carga relaciones
        para evitar el problema de consultas N+1 durante la serialización JSON.
        """
        now = timezone.now()
        
        return InventoryItem.objects.select_related(
            'product',
            'product__category',
            'offer'
        ).annotate(
            # 💡 ANOTACIÓN MASIVA: Calculamos el promedio y el total de reviews en una sola consulta SQL
            avg_rating=Coalesce(Avg('product__califications__rating'), Value(0.0), output_field=FloatField()),
            rating_count=Count('product__califications')
        ).filter(
            paused=False,
            stock__gt=0,
            store__is_active=True,
            store__company__owner__subscription__isnull=False,
            store__company__owner__subscription__valid_until__gte=now
        )
    
    def _annotate_proximity_flag(self, queryset):
        """
        Anota dos banderas:
        - is_very_close: <= 599.99m
        - is_close: 600m a 1.2 km
        """
        # Definimos la distancia para cálculos, con spheroid=True para precisión en metros
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
        Calcula el 'Score' basándose ÚNICAMENTE en la competencia comercial.
        Asigna un boost del 10% de prioridad a vendedores platinium.
        """
        platinum_multiplier = Case(
            When(store__company__is_platinum=True, then=Value(1.10)),
            default=Value(1.0),
            output_field=FloatField()
        )
        score_expression = ExpressionWrapper(
            F('cached_popularity_score') * platinum_multiplier,
            output_field=FloatField()
        )
        return queryset.annotate(ranking_score=score_expression)

    def _apply_monopoly_prevention(self, queryset):
        """
        El algoritmo mágico que evita que una sola tienda acapare los resultados.
        """
        qs = queryset.annotate(
            store_rank=Window(
                expression=RowNumber(),
                partition_by=[F('store_id')],
                order_by=F('ranking_score').desc()
            )
        )
        return qs.order_by('store_rank', '-ranking_score')

    def _apply_feed_sorting(self, qs, sort_by: str, price_order: str):
        """
        Aplica las reglas de ordenamiento solicitadas por el usuario.
        Si no hay ordenamiento explícito, aplica el flujo de relevancia y anti-monopolio.
        """
        # 1. CASO POR DEFECTO: Relevancia (Anti-monopolio)
        if sort_by == 'relevance' and not price_order:
            qs = self._annotate_ranking_score(qs)
            return self._apply_monopoly_prevention(qs)

        # 2. CASOS DE ORDENAMIENTO EXPLÍCITO
        order_params = []

        # -- Orden Primario --
        if sort_by == 'distance':
            qs = qs.annotate(distance_to_user=Distance('store__location__coordinates', self.user_location))
            order_params.append('distance_to_user') # Ascendente: los más cercanos primero

        elif sort_by == 'rating':
            # Anotamos el promedio de calificación del producto (Si no tiene, asume 0.0)
            qs = qs.annotate(
                avg_rating=Coalesce(Avg('product__califications__rating'), Value(0.0), output_field=FloatField())
            )
            order_params.append('-avg_rating') # Descendente: los mejor calificados primero

        # -- Orden Secundario (Precio) --
        if price_order in ['asc', 'desc']:
            # Calculamos el precio real (Si hay custom_price en el lote, lo usa, si no, usa el del producto)
            qs = qs.annotate(effective_price=Coalesce('custom_price', 'product__price'))
            
            if price_order == 'asc':
                order_params.append('effective_price')
            else:
                order_params.append('-effective_price')

        return qs.order_by(*order_params)

    # =========================================================================
    # MÉTODOS PÚBLICOS
    # =========================================================================

    def get_category_feed(self, sub_category_id: int, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000):
        """
        Retorna productos de una subcategoría, ordenados de forma dinámica.
        """
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        # Barrera de entrada estricta
        qs = qs.filter(
            product__category_id=sub_category_id,
            # Corregido: Agregamos D(m=...) para acotar la distancia en metros
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        
        return self._apply_feed_sorting(qs, sort_by, price_order)

    def get_offers_feed(self, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000):
        """
        Retorna productos en oferta, ordenados de forma dinámica.
        """
        now = timezone.now()
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        # Barrera de entrada y vigencia de la oferta
        qs = qs.filter(
            offer__isnull=False,
            offer__valid_until__gte=now,
            # Corregido: Agregamos D(m=...) para acotar la distancia en metros
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        
        return self._apply_feed_sorting(qs, sort_by, price_order)

    def get_store_feed(self, store_id: str, price_order: str = None):
        """
        Retorna TODOS los productos de una tienda.
        Soporta ordenamiento por precio o por popularidad (por defecto).
        """
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(store_id=store_id)
        
        if price_order in ['asc', 'desc']:
            qs = qs.annotate(effective_price=Coalesce('custom_price', 'product__price'))
            return qs.order_by('effective_price' if price_order == 'asc' else '-effective_price')
        else:
            # Orden por defecto de la tienda: Popularidad
            qs = qs.annotate(ranking_score=F('cached_popularity_score'))
            return qs.order_by('-ranking_score')
        
    def get_text_search_feed(self, search_query: str, sort_by: str = 'relevance', price_order: str = None, max_distance_meters: float = 10000):
        """
        Retorna productos que coincidan con un texto de búsqueda, cruzado con el filtro hiperlocal.
        Busca coincidencias en el nombre del producto, la categoría, y el nombre de la tienda.
        """
        qs = self._get_base_active_queryset()
        qs = self._annotate_proximity_flag(qs)
        
        # 1. Filtro Geográfico y disponibilidad base
        qs = qs.filter(
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )

        # 2. Búsqueda de Texto Flexible
        if search_query:
            # Limpiamos espacios en blanco extra
            clean_query = search_query.strip()
            
            # Filtramos usando el objeto Q para abarcar múltiples campos.
            # Nota: __icontains es funcional, pero si usas PostgreSQL, puedes migrar esto a 
            # SearchVector o TrigramSimilarity para mejor tolerancia a errores ortográficos.
            qs = qs.filter(
                Q(product__name__icontains=clean_query) | 
                Q(product__description__icontains=clean_query) |
                Q(product__category__name__icontains=clean_query) |
                Q(product__company__name__icontains=clean_query)
            ).distinct() # Agregamos distinct() por si los JOINs del 'OR' generan duplicados

        # 3. Aplicamos las reglas de ordenamiento o anti-monopolio
        return self._apply_feed_sorting(qs, sort_by, price_order)
    
    def get_home_feed(self, user, max_distance_meters: float = 15000):
        qs = self._get_base_active_queryset()
        
        # 1. ANOTAMOS EL "IS_LIKED" (Esto es extremadamente rápido)
        # Comprobamos si existe un registro en ProductLike donde el usuario sea el actual
        # y el producto sea el que estamos iterando (OuterRef('pk'))
        is_liked_subquery = ProductLike.objects.filter(
            user=user, 
            product=OuterRef('pk')
        )
        qs = qs.annotate(is_liked=Exists(is_liked_subquery))
        
        # 2. Resto de tu lógica
        qs = self._annotate_proximity_flag(qs)
        qs = qs.filter(
            store__location__coordinates__distance_lte=(self.user_location, D(m=max_distance_meters))
        )
        qs = self._annotate_ranking_score(qs)
        return self._apply_monopoly_prevention(qs)