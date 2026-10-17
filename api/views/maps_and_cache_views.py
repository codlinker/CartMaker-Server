"""PostGIS Map Views, Redis Split-Cache Synchronization, Dynamic Category Schemas (SDUI), and User Preferences."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

#########################################################
#################### MANEJO DE MAPAS ####################
#########################################################

from pprint import pprint

class CartMakerMapViewSet(viewsets.ViewSet):
    """
    API exclusiva para el motor de renderizado del mapa principal de CartMaker.
    Utiliza Grid Snapping (Alineación de Cuadrícula) y filtrado In-Memory 
    para absorber el tráfico masivo de map panning sin golpear a PostGIS.
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ('get_locations', 'store_products'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def _snap_to_grid(self, val: float, step: float = 0.04) -> float:
        """
        Redondea una coordenada a una cuadrícula virtual determinista.
        Un step de 0.04 grados equivale aproximadamente a bloques de 4.5 km.
        """
        return math.floor(val / step) * step

    @action(detail=False, methods=['get'])
    def get_locations(self, request):
        try:
            min_lng = float(request.query_params.get('min_lng'))
            min_lat = float(request.query_params.get('min_lat'))
            max_lng = float(request.query_params.get('max_lng'))
            max_lat = float(request.query_params.get('max_lat'))
        except (TypeError, ValueError):
            return Response({'error': 'Parámetros de coordenadas inválidos'}, status=status.HTTP_400_BAD_REQUEST)

        # Captura de Filtros
        filters_dict = {
            'c_cat': request.query_params.get('company_category_id'),
            'plat': request.query_params.get('is_platinum') == 'true',
            'p_cat': request.query_params.get('category_id'),
            'p_sub': request.query_params.get('subcategory_id'),
            'min_p': request.query_params.get('min_price'),
            'max_p': request.query_params.get('max_price'),
            'q': request.query_params.get('search', '').strip().lower()
        }
        
        has_filters = any(v for v in filters_dict.values() if v is not False and v != '')
        # Hasheamos los filtros de forma determinista para la llave de Redis
        filters_hash = hashlib.md5(json.dumps(filters_dict, sort_keys=True).encode()).hexdigest()

        # =========================================================================
        # 1. GENERACIÓN DE LLAVE DETERMINISTA (GRID SNAPPING)
        # =========================================================================
        if has_filters:
            # Si hay filtros, tu lógica original usaba un radio de 200km desde el centro.
            # Hacemos snapping del centroide para estabilizar el caché de la búsqueda.
            centroid_lng = self._snap_to_grid((min_lng + max_lng) / 2, step=0.1)
            centroid_lat = self._snap_to_grid((min_lat + max_lat) / 2, step=0.1)
            cache_key = f"map:radius:{centroid_lng:.2f}:{centroid_lat:.2f}:{filters_hash}"
        else:
            # Panning libre: Expandimos el BBox del usuario al bloque estático más cercano
            grid_min_lng = self._snap_to_grid(min_lng)
            grid_min_lat = self._snap_to_grid(min_lat)
            grid_max_lng = self._snap_to_grid(max_lng) + 0.04
            grid_max_lat = self._snap_to_grid(max_lat) + 0.04
            cache_key = f"map:grid:{grid_min_lng:.2f}:{grid_min_lat:.2f}:{grid_max_lng:.2f}:{grid_max_lat:.2f}:{filters_hash}"

        # Intentamos recuperar el bloque gigante de la RAM
        cached_features = cache.get(cache_key)

        # =========================================================================
        # 2. CACHE MISS: CONSULTA PESADA A POSTGIS
        # =========================================================================
        if cached_features is None:
            bbox = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
            bbox.srid = 4326

            if has_filters:
                # Usamos el centroide real para la consulta (PostGIS es rápido en esto)
                queryset = StoreLocation.objects.select_related('store', 'mall').filter(
                    coordinates__distance_lte=(bbox.centroid, D(km=200)),
                    store__is_active=True
                )
            else:
                # Usamos la cuadrícula GIGANTE redondeada para almacenar datos de sobra
                grid_bbox = Polygon.from_bbox((grid_min_lng, grid_min_lat, grid_max_lng, grid_max_lat))
                grid_bbox.srid = 4326
                queryset = StoreLocation.objects.select_related('store', 'mall').filter(
                    coordinates__coveredby=grid_bbox,
                    store__is_active=True
                )

            # --- APLICACIÓN DE FILTROS ORIGINALES ---
            if filters_dict['c_cat']:
                queryset = queryset.filter(store__company__category_id=filters_dict['c_cat'])
            if filters_dict['plat']:
                queryset = queryset.filter(store__company__is_platinum=True)

            if filters_dict['p_cat'] or filters_dict['p_sub'] or filters_dict['min_p'] or filters_dict['max_p']:
                inventory_query = Q(store__product_items__paused=False, store__product_items__stock__gt=0)
                if filters_dict['p_sub']:
                    inventory_query &= Q(store__product_items__product__category_id=filters_dict['p_sub'])
                elif filters_dict['p_cat']:
                    inventory_query &= Q(store__product_items__product__category__parent_category_id=filters_dict['p_cat'])

                if filters_dict['min_p']:
                    min_val = float(filters_dict['min_p'])
                    inventory_query &= (
                        Q(store__product_items__custom_price__isnull=False, store__product_items__custom_price__gte=min_val) |
                        Q(store__product_items__custom_price__isnull=True, store__product_items__product__price__gte=min_val)
                    )
                if filters_dict['max_p']:
                    max_val = float(filters_dict['max_p'])
                    inventory_query &= (
                        Q(store__product_items__custom_price__isnull=False, store__product_items__custom_price__lte=max_val) |
                        Q(store__product_items__custom_price__isnull=True, store__product_items__product__price__lte=max_val)
                    )
                queryset = queryset.filter(inventory_query).distinct()

            if filters_dict['q']:
                search_terms = filters_dict['q'].split()
                word_queries = []
                for term in search_terms:
                    term_filter = (
                        Q(store__name__icontains=term) |
                        Q(store__company__name__icontains=term) |
                        Q(store__company__category__name__icontains=term) |
                        Q(store__product_items__product__name__icontains=term, store__product_items__paused=False, store__product_items__stock__gt=0) |
                        Q(store__product_items__product__category__name__icontains=term, store__product_items__paused=False, store__product_items__stock__gt=0) |
                        Q(store__product_items__product__category__parent_category__name__icontains=term, store__product_items__paused=False, store__product_items__stock__gt=0)
                    )
                    word_queries.append(term_filter)
                global_search_filter = reduce(operator.and_, word_queries)
                queryset = queryset.filter(global_search_filter).distinct()

            locations = queryset.values(
                'store_id', 'coordinates', 'mall_id', 'mall_floor',
                'store__store_type', 'store__name', 'store__company__name', 
                'store__company__image', 'store__company__category__name', 
                'store__company__is_platinum', 'store__work_hours',
                'store__work_days', 'store__company__main_work_hours',
                'store__company__main_work_days'
            )[:600]

            cached_features = []
            for loc in locations:
                type_int = loc['store__store_type']
                type_name = StoreType(type_int).name if type_int is not None else "STREET"
                raw_image = loc['store__company__image']
                image_url = storage_manager.get_url(raw_image) if raw_image else "https://via.placeholder.com/150"

                work_hours = loc['store__work_hours'] or loc['store__company__main_work_hours']
                work_days = loc['store__work_days'] or loc['store__company__main_work_days'] or [0, 1, 2, 3, 4]

                cached_features.append({
                    "store_id": str(loc['store_id']),
                    "lat": loc['coordinates'].y,
                    "lng": loc['coordinates'].x,
                    "mall_id": loc['mall_id'],
                    "floor": loc['mall_floor'] or 1,
                    "store_type": type_name,
                    "company_name": loc['store__company__name'],
                    "branch_name": loc['store__name'],
                    "category": loc['store__company__category__name'] or "General",
                    "profile_pic": image_url,
                    "is_platinum": loc['store__company__is_platinum'],
                    "work_hours": work_hours, 
                    "work_days": work_days 
                })

            # Guardamos el bloque en Redis por 15 minutos
            cache.set(cache_key, cached_features, timeout=900)

        # =========================================================================
        # 3. MAP REDUCE IN-MEMORY (CACHE HIT)
        # =========================================================================
        # En memoria, recortamos matemáticamente los bordes del bloque gigante 
        # para enviar a Flutter ÚNICAMENTE lo que cabe en su pantalla milimétrica.
        exact_features = [
            f for f in cached_features 
            if min_lng <= f['lng'] <= max_lng and min_lat <= f['lat'] <= max_lat
        ]

        return Response({'data': exact_features}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def store_products(self, request):
        """
        Retorna el catálogo activo de una tienda específica filtrado por subcategoría y rango de precios,
        preservando estrictamente la estructura de datos extendida original mediante Split Caching.
        """
        try:
            store_id = request.query_params.get('store_id')
            if not store_id:
                return Response({'error': 'store_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)

            subcategory_id = request.query_params.get('subcategory_id') or 'all'
            min_price = request.query_params.get('min_price') or 'none'
            max_price = request.query_params.get('max_price') or 'none'

            # 1. Definir llave única estructural para esta combinación exacta de filtros en la sucursal
            struct_cache_key = f"cartmaker:struct:map_products:{store_id}:{subcategory_id}:{min_price}:{max_price}"
            structural_data = cache.get(struct_cache_key)

            # =========================================================================
            # CACHE MISS ESTRUCTURAL: CONSULTA OPTIMIZADA A POSTGRESQL
            # =========================================================================
            if structural_data is None:
                # Recuperamos el QuerySet base con todas sus relaciones cargadas
                queryset = InventoryItem.objects.select_related(
                    'product',
                    'product__category',
                    'product__category__parent_category',
                    'product__company',
                    'offer',
                    'store',
                    'store__company',
                ).filter(
                    store_id=store_id,
                    paused=False,
                    stock__gt=0
                )
                
                prod_avg_sq = Subquery(
                    ProductCalification.objects.filter(product_id=OuterRef('product_id'))
                    .values('product_id')
                    .annotate(v=Avg('rating'))
                    .values('v')[:1],
                    output_field=FloatField()
                )
                prod_cnt_sq = Subquery(
                    ProductCalification.objects.filter(product_id=OuterRef('product_id'))
                    .values('product_id')
                    .annotate(c=Count('id'))
                    .values('c')[:1],
                    output_field=IntegerField()
                )
                queryset = queryset.annotate(
                    avg_rating=Round(Coalesce(prod_avg_sq, Value(0.0, output_field=FloatField())), 1),
                    rating_count=Coalesce(prod_cnt_sq, Value(0, output_field=IntegerField()))
                )

                # Aplicar filtro por SubCategoría si viene en los parámetros
                if request.query_params.get('subcategory_id'):
                    queryset = queryset.filter(product__category_id=request.query_params.get('subcategory_id'))

                # Aplicar filtro de rango de precios original evaluando el costo real
                if request.query_params.get('min_price') or request.query_params.get('max_price'):
                    queryset = queryset.annotate(
                        actual_price=Coalesce('custom_price', 'product__price')
                    )
                    if request.query_params.get('min_price'):
                        queryset = queryset.filter(actual_price__gte=float(request.query_params.get('min_price')))
                    if request.query_params.get('max_price'):
                        queryset = queryset.filter(actual_price__lte=float(request.query_params.get('max_price')))

                # Evaluamos los primeros 50 ítems del catálogo de la tienda
                items = queryset[:50]
                
                # CRÍTICO: Mantenemos el método get_json() original del modelo con todos sus campos extendidos
                structural_data = [item.get_json() for item in items]
                
                # Almacenamos el esqueleto en RAM por 10 minutos
                cache.set(struct_cache_key, structural_data, timeout=600)

            # =========================================================================
            # REAL-TIME STITCHING: FUSIÓN DE VOLATILIDAD DIRECTA EN LA VISTA
            # =========================================================================
            if not structural_data:
                return Response({'data': []}, status=status.HTTP_200_OK)

            # Extraemos los IDs de los ítems del caché estructural
            item_ids = [item["id"] for item in structural_data]
            
            # Ejecutamos un MGET nativo por tubería mapeando las llaves volátiles generadas en signals.py
            volatile_keys_map = {f"cartmaker:volatile:item:{uid}": uid for uid in item_ids}
            cached_states = cache.get_many(volatile_keys_map.keys())

            final_realtime_data = []
            
            for item_data in structural_data:
                item_id = item_data["id"]
                v_key = f"cartmaker:volatile:item:{item_id}"
                state = cached_states.get(v_key)

                # Fallback atómico si la llave volátil expiró en Redis
                if not state:
                    state = {
                        "stock": int(item_data.get("stock", 0)),
                        "paused": bool(item_data.get("paused", False)),
                        "custom_price": item_data.get("custom_price")
                    }
                    cache.set(v_key, state, timeout=86400)

                # Validación de consistencia en vivo: si se agotó el stock o se pausó, se descarta al vuelo
                if state["paused"] or state["stock"] <= 0:
                    continue

                # Sincronizamos las propiedades mutables sobre el diccionario extendido original
                item_data["stock"] = state["stock"]
                item_data["paused"] = state["paused"]
                item_data["custom_price"] = state["custom_price"]
                
                final_realtime_data.append(item_data)

            # Retornamos la firma de respuesta idéntica a la original {'data': [...]}
            return Response({'data': final_realtime_data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetStoresLocations(APIView):
    """
    Endpoint optimizado para cargar tiendas basadas en el área visible del mapa.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # Obtención de parámetros del BBOX
            bbox_coords = (
                float(request.query_params.get('min_lng')),
                float(request.query_params.get('min_lat')),
                float(request.query_params.get('max_lng')),
                float(request.query_params.get('max_lat'))
            )
            bbox = Polygon.from_bbox(bbox_coords)
            bbox.srid = 4326

            stores = StoreLocation.objects.filter(
                store__is_active=True,
                coordinates__coveredby=bbox,
            ).values(
                'id', 
                'coordinates', 
                'name', 
                'mall_id', 
                'store__store_type'
            )[:500] 

            features = [{
                "id": s['id'],
                "lat": s['coordinates'].y,
                "lng": s['coordinates'].x,
                "mall_id": s['mall_id'],
                "name": s['name'],
                "type": s['store__store_type']
            } for s in stores]
            
            return Response({'data': features}, status=status.HTTP_200_OK)
            
        except (ValueError, TypeError, AttributeError):
            return Response({'error': 'Parámetros inválidos'}, status=status.HTTP_400_BAD_REQUEST)

####################################################
###################### CACHE #######################
####################################################

class GetMallsCache(APIView):
    """
    Devuelve todos los centros comerciales registrados para mapeo local.
    Caché Global: Se invalida solo si se agrega o edita un Mall.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "cartmaker:global:malls"
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        malls = Mall.objects.prefetch_related('stores').all()
        malls_data = [m.get_json() for m in malls]
        data = {'malls': malls_data}
        
        cache.set(cache_key, data, timeout=86400) # 24 horas
        return Response(data, status=status.HTTP_200_OK)

class CompanyCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cache_key = f"cartmaker:tenant:{request.user.id}:company"
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            if cached_data.get("message") == "Suscripción expirada.":
                cache.delete(cache_key)
            elif "error_status" in cached_data:
                return Response({'message': cached_data["message"]}, status=cached_data["error_status"])
            else:
                return Response(cached_data, status=status.HTTP_200_OK)
            
        try:
            company_obj = Company.objects.select_related('category').get(owner=request.user)
            company = company_obj.get_json()
        except Company.DoesNotExist:
            error_data = {"error_status": status.HTTP_404_NOT_FOUND, "message": "No ha configurado su tienda."}
            cache.set(cache_key, error_data, timeout=300)
            return Response({'message': error_data["message"]}, status=error_data["error_status"])

        stores_qs = CompanyStore.objects.filter(
            company_id=company['id']
        ).select_related(
            'location', 'location__mall', 'company'
        ).prefetch_related(
            'contact_methods'
        ).order_by('creation')
        stores = [company_store.get_json() for company_store in stores_qs]

        item_ct = ContentType.objects.get_for_model(InventoryItem)
        video_ct = ContentType.objects.get_for_model(CompanyVideoStory)

        items_pks = InventoryItem.objects.filter(store__company_id=company['id']).values_list('id', flat=True)
        videos_pks = CompanyVideoStory.objects.filter(company_id=company['id']).values_list('id', flat=True)

        pending_items = UniversalComment.objects.filter(content_type=item_ct).annotate(
            object_uuid=Cast('object_id', output_field=UUIDField())
        ).filter(object_uuid__in=items_pks).filter(Q(answer_text__isnull=True) | Q(answer_text__exact=''))

        pending_videos = UniversalComment.objects.filter(content_type=video_ct).annotate(
            object_uuid=Cast('object_id', output_field=UUIDField())
        ).filter(object_uuid__in=videos_pks).filter(Q(answer_text__isnull=True) | Q(answer_text__exact=''))

        pending_questions = list(pending_items.values_list('id', flat=True)) + list(pending_videos.values_list('id', flat=True))

        data = {'company': company, 'stores': stores, 'pending_questions': pending_questions}
        cache.set(cache_key, data, timeout=3600)
        return Response(data, status=status.HTTP_200_OK)

class SubscriptionsCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché por Usuario: Suscripciones, Wallet y Notificaciones.
        Altamente dinámico: Se invalida por señales al pagar o recibir saldo.
        """
        cache_key = f"cartmaker:tenant:{request.user.id}:subscriptions"
        cached_data = cache.get(cache_key)

        if cached_data is not None and "atlas_invoices" in cached_data:
            try:
                atlas_plan = getattr(request.user, 'atlas_plan', None) or AtlasPlusPlan.objects.filter(user=request.user).first()
                if atlas_plan:
                    cached_data["atlas_subscription"] = atlas_plan.get_json()
            except Exception:
                pass
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        config = SystemConfig.objects.order_by('-creation').first()
        user = User.objects.select_related(
            'subscription__plan',
            'atlas_plan',
            'wallet',
        ).prefetch_related(
            'subscription__payments__subscription__plan',
            'atlas_plan__payments__invoice',
        ).get(id=request.user.id)

        merchant_subscription = user.subscription if hasattr(user, 'subscription') else None
        atlas_subscription = user.atlas_plan if hasattr(user, 'atlas_plan') else None
        
        subscriptions_payments = {'atlas': [], 'merchant': []}
        atlas_invoices = []
        
        pending_rejection_notif = Notification.objects.filter(
            user=request.user,
            category=NotificationCategory.PAYMENT_REJECTED,
            is_read=False
        ).first()

        wallet_obj = user.wallet if hasattr(user, 'wallet') else UserWallet.objects.get_or_create(user=user)[0]
        wallet_data = wallet_obj.get_json()

        if atlas_subscription:
            payments_qs = sorted(atlas_subscription.payments.all(), key=lambda p: p.creation, reverse=True)
            for atlas_payment in payments_qs:
                pay_json = atlas_payment.get_json()
                subscriptions_payments['atlas'].append(pay_json)
                if pay_json.get('invoice'):
                    atlas_invoices.append(pay_json['invoice'])
        if merchant_subscription:
            subscriptions_payments['merchant'] = [merchant_payment.get_json() for merchant_payment in merchant_subscription.payments.all()]
        data = {
            "merchant_subscription": merchant_subscription.get_json() if merchant_subscription else None,
            "atlas_subscription": atlas_subscription.get_quota_status(config=config) if atlas_subscription else None,
            "subscriptions_payments": subscriptions_payments,
            "atlas_invoices": atlas_invoices,
            "billing_issuer": config.get_billing_issuer_json() if config else None,
            "wallet": wallet_data,
            "pending_payment_notification_retry_id": pending_rejection_notif.id if pending_rejection_notif else None,
        }
        cache.set(cache_key, data, timeout=3600) # 1 hora
        return Response(data, status=status.HTTP_200_OK)
    
class SystemConfigCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché de configuracion global y emisor fiscal SENIAT dinámico.
        """
        config = SystemConfig.objects.latest('creation')
        data = {
            'atlas_plus_price_usd': float(config.atlas_plus_price_usd),
            'atlas_plus_price_formatted': format_ve_amount(config.atlas_plus_price_usd, 2, "$", True),
            'atlas_plus_daily_limit': config.atlas_plus_daily_limit,
            'atlas_free_daily_limit': config.atlas_free_daily_limit,
            'atlas_anonymous_daily_limit': config.atlas_anonymous_daily_limit,
            'shared_with_atlas_business': True,
            'platinum_min_rating_promedy_requirement': config.platinum_min_rating_promedy_requirement,
            'platinum_min_sells_per_month_requirement': config.platinum_min_sells_per_month_requirement,
            'billing_issuer': config.get_billing_issuer_json(),
        }
        return Response(data, status=status.HTTP_200_OK)

class UserCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Caché por Usuario: Perfil base.
        """
        cache_key = f"cartmaker:tenant:{request.user.id}:profile"
        cached_data = cache.get(cache_key)

        if cached_data and "preferred_category_ids" in cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        user = User.objects.prefetch_related(
            'locations', 'contact_methods', 'preferred_categories'
        ).get(id=request.user.id)
        locations = [location.get_json() for location in user.locations.all()]
        contact_methods = [
            contact_method.get_json()
            for contact_method in sorted(user.contact_methods.all(), key=lambda c: c.method_type)
        ]
        preferred_category_ids = sorted(cat.id for cat in user.preferred_categories.all())

        data = {
            "user_id": user.id,
            "email": user.email,
            "creation": user.creation.strftime('%d/%m/%Y, %H:%M:%S'),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "birth_date": user.birth_date if user.birth_date else "",
            "email_verified": user.email_verified,
            "user_type": user.user_type,
            "profile_picture": user.get_profile_picture_url(),
            "cedula_document_url": user.cedula_document if user.cedula_document else "",
            "cedula_verified": user.cedula_verified,
            "cedula_number": user.cedula_number if user.cedula_number else "",
            "gender": user.gender,
            "locations": locations,
            "is_external_account": user.is_external_account,
            'contact_methods': contact_methods,
            "preferred_category_ids": preferred_category_ids,
        }
        
        cache.set(cache_key, data, timeout=86400) # 24 horas (Cambia rara vez)
        return Response(data, status=status.HTTP_200_OK)
    
class HomeCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "cartmaker:global:home"
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        announcements = [announcement.get_json() for announcement in Announcement.objects.filter(active=True).order_by('-creation')]
        
        # 👈 AQUÍ: aseguramos la iteración limpia usando el modelo Category
        company_categories = [cat.get_json() for cat in CompanyCategory.objects.all()]
        
        company_section_images = {
            "administrar_inventario": storage_manager.get_url('static/img/company_section_buttons/administrar_inventario.jpg', True),
            "administrar_suscripcion": storage_manager.get_url('static/img/company_section_buttons/administrar_suscripcion.jpg', True),
            "analiticas": storage_manager.get_url('static/img/company_section_buttons/analiticas.jpg', True),
            "empleados": storage_manager.get_url('static/img/company_section_buttons/empleados.jpg', True),
            "gamificacion": storage_manager.get_url('static/img/company_section_buttons/gamificacion.jpg', True),
            "mi_tienda": storage_manager.get_url('static/img/company_section_buttons/mi_tienda.jpg', True),
            "pedidos": storage_manager.get_url('static/img/company_section_buttons/pedidos.jpg', True),
            "preguntas_de_clientes": storage_manager.get_url('static/img/company_section_buttons/preguntas_de_clientes.jpg', True),
        }
        
        data = {
            "announcements": announcements,
            'company_categories': company_categories,
            'company_section_images': company_section_images,
        }
        
        cache.set(cache_key, data, timeout=86400) # 24h
        return Response(data, status=status.HTTP_200_OK)

class SearchCacheAPI(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Caché Global: UI del Buscador + Esquemas Dinámicos de Producto por Categoría/Subcategoría.
        """
        cache_key = "cartmaker:global:search"
        cached_data = cache.get(cache_key)

        if (
            cached_data
            and isinstance(cached_data.get("categories"), list)
            and (not cached_data["categories"] or "default_product_schema" in cached_data["categories"][0])
        ):
            return Response(cached_data, status=status.HTTP_200_OK)

        # Cache Miss
        categories = [category.get_json() for category in Category.objects.prefetch_related('subcategories').order_by('id')]
        search_stores_at_zone = {
            "atlas_message": "Detecto varias ofertas de hortalizas en el Kiosco de DonAmigo.",
            "image_background": storage_manager.get_url('static/img/tiendas_en_la_zona_background.jpg', True)
        }
        
        data = {
            "categories": categories,
            'search_stores_at_zone': search_stores_at_zone
        }
        
        cache.set(cache_key, data, timeout=86400) # 24h
        return Response(data, status=status.HTTP_200_OK)


class CategoriesListAPI(APIView):
    """
    Endpoint público (protegido por X-Api-Key en el Gatekeeper) para listar
    las categorías principales del catálogo durante el Onboarding, buscador o registro de productos.
    GET /api/v1/categories/?page_size=50
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "cartmaker:global:categories"
        categories = cache.get(cache_key)

        if (
            categories is None
            or not isinstance(categories, list)
            or (categories and "default_product_schema" not in categories[0])
        ):
            categories = [
                category.get_json()
                for category in Category.objects.prefetch_related('subcategories').order_by('id')
            ]
            cache.set(cache_key, categories, timeout=86400)

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = max(1, min(100, int(request.query_params.get('page_size', 50))))
        except (TypeError, ValueError):
            page_size = 50

        start = (page - 1) * page_size
        end = start + page_size
        sliced = categories[start:end]

        return Response(
            {
                "count": len(categories),
                "next": None,
                "previous": None,
                "results": sliced,
                "categories": sliced,
                "data": sliced,
            },
            status=status.HTTP_200_OK,
        )


class CategoryProductSchemaAPI(APIView):
    """
    Devuelve el esquema dinámico de creación/visualización de producto para una
    subcategoría o categoría específica (o el catálogo completo de unidades y esquemas).
    GET /api/v1/categories/product-schema/?subcategory_id=X
    GET /api/v1/categories/product-schema/?category_id=Y
    GET /api/v1/categories/product-schema/?subcategory_name=Frescos
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'
    permission_classes = [AllowAny]

    def get(self, request):
        from api.core.category_schemas import SELLING_UNITS_CATALOG, get_subcategory_schema

        subcategory_id = request.query_params.get('subcategory_id') or request.query_params.get('sub_category_id')
        category_id = request.query_params.get('category_id')
        subcategory_name = request.query_params.get('subcategory_name')
        category_name = request.query_params.get('category_name')

        if subcategory_id:
            try:
                sub = SubCategory.objects.select_related('parent_category').get(id=int(subcategory_id))
                return Response({
                    "subcategory_id": sub.id,
                    "subcategory_name": sub.name,
                    "category_id": sub.parent_category_id,
                    "category_name": sub.parent_category.name if sub.parent_category_id else "",
                    "product_schema": sub.get_product_schema(),
                }, status=status.HTTP_200_OK)
            except (SubCategory.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Subcategoría no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if category_id:
            try:
                cat = Category.objects.prefetch_related('subcategories').get(id=int(category_id))
                return Response({
                    "category_id": cat.id,
                    "category_name": cat.name,
                    "default_product_schema": cat.get_product_schema(),
                    "sub_categories": [
                        {
                            "id": s.id,
                            "name": s.name,
                            "product_schema": s.get_product_schema(),
                        }
                        for s in cat.subcategories.all()
                    ],
                }, status=status.HTTP_200_OK)
            except (Category.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Categoría no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if subcategory_name or category_name:
            schema = get_subcategory_schema(
                subcategory_name=subcategory_name,
                parent_category_name=category_name,
            )
            return Response({
                "subcategory_name": subcategory_name,
                "category_name": category_name,
                "product_schema": schema,
            }, status=status.HTTP_200_OK)

        categories = [
            category.get_json()
            for category in Category.objects.prefetch_related('subcategories').order_by('id')
        ]
        return Response({
            "selling_units_catalog": list(SELLING_UNITS_CATALOG.values()),
            "categories": categories,
        }, status=status.HTTP_200_OK)


class UserPreferencesAPI(APIView):
    """
    Endpoint para consultar y guardar las preferencias de categorías del usuario
    seleccionadas durante el Onboarding o desde Ajustes.
    Rutas: GET / POST /api/v1/users/preferences/ (y /api/v1/user/preferences/)
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'actions'
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preferred_ids = request.user.get_preferred_category_ids()
        return Response(
            {"preferred_category_ids": preferred_ids},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        is_valid, clean_ids, error_msg = _extract_and_validate_category_ids(request.data)
        if not is_valid:
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        valid_categories = list(Category.objects.filter(id__in=clean_ids).order_by('id'))
        valid_ids = [cat.id for cat in valid_categories]

        with transaction.atomic():
            request.user.preferred_categories.set(valid_categories)
            user_id = request.user.id
            transaction.on_commit(
                lambda: cache.delete(f"cartmaker:tenant:{user_id}:profile")
            )

        return Response(
            {"preferred_category_ids": valid_ids},
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        return self.post(request)

    def patch(self, request):
        return self.post(request)

