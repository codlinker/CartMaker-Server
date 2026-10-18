"""Hyper-Local PostGIS + Trigram Product Search Engine and Atlas 2.0 AI Conversational Assistant."""
from .base import *
from .base import _get_cached_bcv_rate, _extract_and_validate_category_ids

class ProductSearchEngineViewSet(viewsets.ViewSet):
    """
    API integral para la distribución algorítmica de productos hacia la App.
    Interactúa con el ProductSearchEngine para retornar Feeds dinámicos cacheados
    respetando exactamente las firmas de respuesta requeridas por Flutter.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'navigation'

    def get_permissions(self):
        public_reads = (
            'category', 'store', 'offers', 'text_search', 'home_feed', 'item_details',
        )
        if self.action in public_reads:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    # ------------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------------
    def _get_coordinates(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
            return lat, lng
        except (TypeError, ValueError):
            return None, None

    def _get_sorting_params(self, request):
        sort_by = request.query_params.get('sort_by', 'relevance')
        price_order = request.query_params.get('price_order')
        return sort_by, price_order

    def _get_pagination_params(self, request):
        """Extrae de forma segura los parámetros de paginación con límites defensivos contra DoS."""
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = max(1, min(50, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page, page_size = 1, 20
        return page, page_size

    def _paginate_and_respond(self, data_list: list, request) -> Response:
        """
        [OBSOLETO PARA FEEDS PRINCIPALES - Mantenido por retrocompatibilidad]
        Paginación O(1) en RAM que imita la estructura CursorPagination de DRF.
        """
        page, page_size = self._get_pagination_params(request)

        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_data = data_list[start:end]
        has_next = end < len(data_list)
        has_previous = page > 1

        url = request.build_absolute_uri()
        import urllib.parse as urlparse
        
        def replace_page_param(base_url, page_num):
            url_parts = list(urlparse.urlparse(base_url))
            query = dict(urlparse.parse_qsl(url_parts[4]))
            query['page'] = page_num
            url_parts[4] = urlparse.urlencode(query)
            return urlparse.urlunparse(url_parts)

        next_url = replace_page_param(url, page + 1) if has_next else None
        prev_url = replace_page_param(url, page - 1) if has_previous else None

        return Response({
            'next': next_url,
            'previous': prev_url,
            'results': paginated_data
        }, status=status.HTTP_200_OK)

    def _respond_pre_sliced_data(self, data_list: list, request, page: int, page_size: int) -> Response:
        """
        Paginador optimizado para feeds.
        Asume que la lista ya fue rebanada nativamente en SQL (Limit/Offset).
        """
        has_next = len(data_list) == page_size
        has_previous = page > 1

        url = request.build_absolute_uri()
        import urllib.parse as urlparse
        
        def replace_page_param(base_url, page_num):
            url_parts = list(urlparse.urlparse(base_url))
            query = dict(urlparse.parse_qsl(url_parts[4]))
            query['page'] = page_num
            url_parts[4] = urlparse.urlencode(query)
            return urlparse.urlunparse(url_parts)

        next_url = replace_page_param(url, page + 1) if has_next else None
        prev_url = replace_page_param(url, page - 1) if has_previous else None

        return Response({
            'next': next_url,
            'previous': prev_url,
            'results': data_list
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINTS
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def category(self, request):
        sub_category_id = request.query_params.get('sub_category_id')
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)

        if not sub_category_id or lat is None or lng is None:
            return Response({'error': 'Faltan parámetros'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_category_feed(
            sub_category_id=sub_category_id, page=page, page_size=page_size, 
            sort_by=sort_by, price_order=price_order
        )

        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def store(self, request):
        store_id = request.query_params.get('store_id')
        company_id = request.query_params.get('company_id')
        category_id = request.query_params.get('category_id')
        lat, lng = self._get_coordinates(request)
        _, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)

        if (not store_id and not company_id) or lat is None or lng is None:
            return Response(
                {'error': 'Faltan parámetros obligatorios: store_id o company_id, lat, lng'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_store_feed(
            page=page, page_size=page_size,
            store_id=store_id, 
            company_id=company_id,
            category_id=category_id,
            price_order=price_order
        )
        
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def offers(self, request):
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        effective_page_size = min(page_size, 10) if is_home_widget else page_size
        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_offers_feed(page=page, page_size=effective_page_size, sort_by=sort_by, price_order=price_order)

        if is_home_widget:
            top_10 = data_list[:10]
            return Response({'results': top_10}, status=status.HTTP_200_OK)
            
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def stores_with_tokens(self, request):
        lat, lng = self._get_coordinates(request)
        page, page_size = self._get_pagination_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        effective_page_size = min(page_size, 10) if is_home_widget else page_size
        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_stores_with_tokens_feed(page=page, page_size=effective_page_size)

        if is_home_widget:
            top_10 = data_list[:10]
            # Mantenemos consistencia con la respuesta de 'favorites'
            return Response({'data': {'results': top_10}}, status=status.HTTP_200_OK)
            
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def text_search(self, request):
        search_query = request.query_params.get('q', '')
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)
        
        try:
            max_distance = float(request.query_params.get('max_distance', 10000))
        except ValueError:
            max_distance = 10000

        if not search_query or lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: q, lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_text_search_feed(
            search_query=search_query, page=page, page_size=page_size,
            sort_by=sort_by, price_order=price_order,
            max_distance_meters=max_distance
        )

        if len(data_list) == 0 and search_query:
            payload = {
                'client_id': str(request.user.id) if request.user.is_authenticated else None,
                'search_term': search_query,
                'lat': lat,
                'lng': lng,
                'timestamp': timezone.now().isoformat()
            }
            try:
                redis_conn = cache.client.get_client()
                redis_conn.rpush("telemetry:unmet_demand", json.dumps(payload))
            except Exception as e:
                print(f"Error registrando demanda insatisfecha: {e}")

        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    @action(detail=False, methods=['get'])
    def home_feed(self, request):
        lat, lng = self._get_coordinates(request)
        # 💡 Capturamos la semilla enviada por Flutter
        seed = request.query_params.get('seed', 'default_seed')
        
        if lat is None or lng is None:
            return Response({'error': 'Faltan coordenadas'}, status=status.HTTP_400_BAD_REQUEST)

        page, page_size = self._get_pagination_params(request)

        # 🕵️ ESPÍA 1: ¿Flutter nos está mandando una semilla distinta cada vez?
        print(f"\n=======================================================")
        print(f"🚀 [ENDPOINT HOME] Request -> Page: {page} | Semilla recibida: {seed}")
        print(f"=======================================================")

        # 💡 Le pasamos la semilla al motor
        engine = ProductSearchEngine(lat, lng, user=request.user, seed=seed)
        data_list = engine.get_home_feed(page=page, page_size=page_size)
        
        return self._respond_pre_sliced_data(data_list, request, page, page_size)
        
    @action(detail=False, methods=['get'])
    def favorites(self, request):
        lat, lng = self._get_coordinates(request)
        sort_by, price_order = self._get_sorting_params(request)
        page, page_size = self._get_pagination_params(request)
        is_home_widget = request.query_params.get('home_widget', 'false').lower() == 'true'

        if lat is None or lng is None:
            return Response({'error': 'Faltan parámetros obligatorios: lat, lng'}, status=status.HTTP_400_BAD_REQUEST)

        effective_page_size = min(page_size, 10) if is_home_widget else page_size
        engine = ProductSearchEngine(lat, lng, user=request.user)
        data_list = engine.get_favorites_feed(page=page, page_size=effective_page_size, sort_by=sort_by, price_order=price_order)

        if is_home_widget:
            top_10 = data_list[:10]
            return Response({'data': {'results': top_10}}, status=status.HTTP_200_OK)
    
        return self._respond_pre_sliced_data(data_list, request, page, page_size)

    # ------------------------------------------------------------------------
    # MÉTODOS SIN PAGINACIÓN (Item Details y Toggle Like)
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def item_details(self, request):
        item_id = request.query_params.get('item_id')

        if not item_id:
            return Response({'error': 'Falta el parámetro obligatorio: item_id'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            item = InventoryItem.objects.select_related(
                'product',
                'product__category',
                'product__category__parent_category',
                'product__company',
                'offer',
                'store',
                'store__company',
            ).prefetch_related('product__califications').annotate(
                avg_rating=Round(Coalesce(Avg('product__califications__rating'), 0.0), 1),
                rating_count=Count('product__califications')
            ).get(id=item_id, paused=False)
            
            data = item.get_json()
            data['is_owner'] = item.product.company.id == request.user.company.id \
                if (request.user.is_authenticated and hasattr(request.user, 'company')) else False
            
            
            user_tokens = 0
            if request.user.is_authenticated:
                try:
                    from api.models import TokenWallet
                    wallet = TokenWallet.objects.only('balance').get(
                        user=request.user, 
                        company=item.store.company
                    )
                    user_tokens = wallet.balance
                except TokenWallet.DoesNotExist:
                    user_tokens = 0
            
            data['user_wallet_balance'] = user_tokens
            
            return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)
            
        except InventoryItem.DoesNotExist:
            return Response({'error': 'El producto no existe o fue retirado.'}, status=status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------------
    # MÉTODOS SIN PAGINACIÓN (Item Details y Toggle Universal Like)
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def toggle_like(self, request):
        target_type = request.data.get('target_type')
        target_id = request.data.get('target_id')

        if not target_type or not target_id:
            return Response({'error': 'Faltan parámetros: target_type, target_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if target_type == 'product':
                target_obj = InventoryItem.objects.get(id=target_id, paused=False)
            elif target_type == 'video':
                target_obj = CompanyVideoStory.objects.get(id=target_id)
            else:
                return Response({'error': 'Tipo no soportado.'}, status=status.HTTP_400_BAD_REQUEST)
        except (InventoryItem.DoesNotExist, CompanyVideoStory.DoesNotExist):
            return Response({'error': 'El contenido no existe.'}, status=status.HTTP_404_NOT_FOUND)

        content_type_obj = ContentType.objects.get_for_model(target_obj)

        like, created = UniversalLike.objects.get_or_create(
            user=request.user,
            content_type=content_type_obj,
            object_id=target_id
        )

        try:
            cache.delete(f"cartmaker:affinity_profile:v1:{request.user.id}")
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"cartmaker:struct:favs:{request.user.id}:*")
        except Exception:
            pass

        if not created:
            like.delete()
            # Contamos cuántos likes quedaron tras eliminar
            total_likes = UniversalLike.objects.filter(content_type=content_type_obj, object_id=target_id).count()
            return Response({'success': True, 'is_liked': False, 'total_likes': total_likes}, status=status.HTTP_200_OK)
        
        total_likes = UniversalLike.objects.filter(content_type=content_type_obj, object_id=target_id).count()
        return Response({'success': True, 'is_liked': True, 'total_likes': total_likes}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def mark_video_as_viewed(self, request, pk=None):
        try:
            video = CompanyVideoStory.objects.get(pk=pk)
            # 💡 get_or_create usando VideoEngagementLog
            # Esto registra que el usuario ha interactuado con el video
            VideoEngagementLog.objects.get_or_create(
                client=request.user, 
                video=video
            )
            return Response({'status': 'viewed'}, status=status.HTTP_200_OK)
        except CompanyVideoStory.DoesNotExist:
            return Response({'error': 'Historia no encontrada'}, status=status.HTTP_404_NOT_FOUND)

class AtlasViewSet(viewsets.ViewSet):
    """
    API integral para todas las interacciones con Atlas (IA de CartMaker).
    """
    permission_classes = [IsAuthenticated]
    GUEST_HEADER = 'HTTP_X_CARTMAKER_GUEST'

    def get_permissions(self):
        if self.action in ('guest_session', 'current_thread', 'message', 'stage_radar', 'stage_radar_dash'):
            return [AllowAny()]
        return [IsAuthenticated()]

    # 💡 LÍMITE DIARIO CONFIGURABLE
    DAILY_FREE_LIMIT = 7

    def _client_ip(self, request) -> str:
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip:
            return cf_ip.strip()
        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip:
            return real_ip.strip()
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR') or 'unknown'

    def _seconds_until_midnight(self) -> int:
        now_local = timezone.localtime(timezone.now())
        tomorrow = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((tomorrow - now_local).total_seconds()))

    def _anonymous_daily_limit(self) -> int:
        try:
            return SystemConfig.objects.latest('creation').atlas_anonymous_daily_limit
        except SystemConfig.DoesNotExist:
            return 3

    def _guest_token_from_request(self, request) -> str:
        return (request.META.get(self.GUEST_HEADER) or '').strip()

    def _known_guest(self, token: str) -> bool:
        if not token:
            return False
        return cache.get(f"cartmaker:atlas:guest-known:{token}") is not None

    def _remember_guest(self, token: str) -> None:
        cache.set(f"cartmaker:atlas:guest-known:{token}", 1, timeout=60 * 60 * 24 * 30)

    def _anon_used(self, token: str, ip: str) -> int:
        used_token = cache.get(f"cartmaker:atlas:anon:{token}") or 0
        used_ip = cache.get(f"cartmaker:atlas:anon-ip:{ip}") or 0
        return max(int(used_token), int(used_ip))

    def _anon_remaining(self, token: str, ip: str) -> int:
        return max(0, self._anonymous_daily_limit() - self._anon_used(token, ip))

    def _consume_anon(self, token: str, ip: str) -> bool:
        if self._anon_remaining(token, ip) <= 0:
            return False
        timeout = self._seconds_until_midnight()
        for key in (f"cartmaker:atlas:anon:{token}", f"cartmaker:atlas:anon-ip:{ip}"):
            if cache.get(key) is None:
                cache.set(key, 1, timeout=timeout)
            else:
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 1, timeout=timeout)
        return True

    def _refund_anon(self, token: str, ip: str) -> None:
        for key in (f"cartmaker:atlas:anon:{token}", f"cartmaker:atlas:anon-ip:{ip}"):
            try:
                current = cache.get(key)
                if current and int(current) > 0:
                    cache.decr(key)
            except Exception:
                pass

    def _login_required_payload(self, daily_limit: int) -> dict:
        return {
            'error': 'Inicia sesión para seguir hablando con Atlas.',
            'free_interactions_left': 0,
            'login_required': True,
            'daily_limit': daily_limit,
            'is_premium': False,
        }

    def _get_user_plan(self, user):
        plan, _ = AtlasPlusPlan.objects.get_or_create(user=user)
        return plan

    def _create_thread(self, plan):
        return AtlasThread.objects.create(plan=plan)

    # =========================================================================
    # LÓGICA DE PRESUPUESTO DIARIO UNIFICADO (Atlas Comprador + Atlas Negocios)
    # =========================================================================
    def _get_daily_limit(self, user) -> int:
        """
        Devuelve el límite diario unificado según el Tier del usuario en AtlasPlusPlan.
        Respeta derechos adquiridos (Grandfathered Subscription Quota) si el usuario
        contrató su suscripción cuando el límite diario era superior al actual.
        """
        try:
            config = SystemConfig.objects.latest('creation')
            free_limit = int(config.atlas_free_daily_limit or self.DAILY_FREE_LIMIT)
        except SystemConfig.DoesNotExist:
            config = None
            free_limit = self.DAILY_FREE_LIMIT
        plan = self._get_user_plan(user)
        if plan and plan.is_active_premium():
            return plan.get_effective_plus_daily_limit(config=config)
        return free_limit

    def _get_used_today(self, user) -> int:
        """
        Obtiene el consumo diario unificado (Comprador + Negocios) desde Redis,
        o lo reconstruye desde PostgreSQL (AtlasPlusPlan.daily_usage_count + AtlasMessage) si hubo cache miss.
        """
        cache_key = f"cartmaker:atlas:daily_usage:{user.id}"
        used = cache.get(cache_key)
        now_local = timezone.localtime(timezone.now())
        today_local = now_local.date()

        if used is None:
            try:
                plan = self._get_user_plan(user)
                db_used = plan.daily_usage_count if plan.daily_usage_date == today_local else 0
                msg_used = AtlasMessage.objects.filter(
                    conversation__plan=plan,
                    origin=1,
                    creation__date=today_local,
                ).count()
                used = max(int(db_used or 0), int(msg_used or 0))
                if plan.daily_usage_date != today_local or plan.daily_usage_count != used:
                    AtlasPlusPlan.objects.filter(pk=plan.pk).update(
                        daily_usage_date=today_local,
                        daily_usage_count=used,
                    )
            except Exception:
                used = 0

            tomorrow = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            timeout = max(1, int((tomorrow - now_local).total_seconds()))
            cache.set(cache_key, used, timeout=timeout)

        return max(0, int(used or 0))

    def _get_free_interactions_left(self, user) -> int:
        limit = self._get_daily_limit(user)
        used = self._get_used_today(user)
        return max(0, limit - used)

    def _consume_free_interaction(self, user) -> bool:
        limit = self._get_daily_limit(user)
        used = self._get_used_today(user)

        if used >= limit:
            return False

        now_local = timezone.localtime(timezone.now())
        today_local = now_local.date()
        tomorrow = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        timeout = max(1, int((tomorrow - now_local).total_seconds()))
        cache_key = f"cartmaker:atlas:daily_usage:{user.id}"

        new_used = used + 1
        if used == 0 or cache.get(cache_key) is None:
            cache.set(cache_key, new_used, timeout=timeout)
        else:
            try:
                new_used = int(cache.incr(cache_key))
            except Exception:
                cache.set(cache_key, new_used, timeout=timeout)

        try:
            plan = self._get_user_plan(user)
            AtlasPlusPlan.objects.filter(pk=plan.pk).update(
                daily_usage_date=today_local,
                daily_usage_count=new_used,
            )
        except Exception:
            pass

        return True

    def _refund_free_interaction(self, user) -> None:
        if not user or not getattr(user, 'is_authenticated', False):
            return
        cache_key = f"cartmaker:atlas:daily_usage:{user.id}"
        now_local = timezone.localtime(timezone.now())
        today_local = now_local.date()
        try:
            current = cache.get(cache_key)
            if current is not None and int(current) > 0:
                new_val = max(0, int(cache.decr(cache_key)))
            else:
                new_val = 0
        except Exception:
            new_val = 0

        try:
            plan = self._get_user_plan(user)
            if plan.daily_usage_date == today_local and plan.daily_usage_count > 0:
                AtlasPlusPlan.objects.filter(pk=plan.pk).update(
                    daily_usage_count=max(0, new_val)
                )
        except Exception:
            pass

    def _build_quota_exceeded_payload(self, user, company=None) -> dict:
        config = SystemConfig.objects.order_by('-creation').first()
        plan = self._get_user_plan(user)
        quota_status = plan.get_quota_status(config=config)
        is_premium = quota_status['is_premium']
        daily_limit = quota_status['daily_limit']
        plus_limit = int(quota_status.get('atlas_plus_daily_limit') or getattr(config, 'atlas_plus_daily_limit', 30) or 30)
        price_fmt = quota_status['atlas_plus_price_formatted']

        if is_premium:
            mensaje_error = (
                f"Has agotado tus {daily_limit} interacciones diarias de Atlas Plus por hoy. "
                f"Tu cupo se renovará automáticamente a la medianoche."
            )
        else:
            mensaje_error = (
                f"Has agotado tus {daily_limit} interacciones gratuitas de hoy. "
                f"Activa Atlas Plus por {price_fmt}/mes para disfrutar de {plus_limit} consultas diarias "
                f"compartidas entre Atlas Comprador y Atlas Negocios."
            )

        payload = {
            'error': mensaje_error,
            'code': 'ATLAS_DAILY_QUOTA_EXCEEDED',
            'free_interactions_left': 0,
            'used_today': quota_status['used_today'],
            'daily_limit': daily_limit,
            'atlas_plus_daily_limit': plus_limit,
            'is_premium': is_premium,
            'requires_atlas_plus': not is_premium,
            'atlas_plus_price_usd': quota_status['atlas_plus_price_usd'],
            'atlas_plus_price_formatted': price_fmt,
            'login_required': False,
            'quota_status': quota_status,
        }
        if company is not None:
            from ..core.atlas_merchant import AtlasMerchantCopilot
            payload['access_status'] = AtlasMerchantCopilot.check_merchant_access(company, user=user)
        return payload

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/atlas/scan_image/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def scan_image(self, request):
        company = self._resolve_merchant_company(request.user)
        if not company:
            return Response(
                {'error': 'Debes poseer un comercio registrado para utilizar el escáner de inventario.'},
                status=status.HTTP_403_FORBIDDEN
            )
        image_file = request.FILES.get('image')
        if not image_file:
            return Response(
                {'error': 'No se proporcionó ninguna imagen. Asegúrate de enviarla como multipart/form-data con la clave "image".'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if getattr(image_file, 'size', 0) > 15 * 1024 * 1024:
            return Response({'error': 'La imagen excede el tamaño máximo permitido (15 MB).'}, status=status.HTTP_400_BAD_REQUEST)

        if not self._consume_free_interaction(request.user):
            return Response(
                self._build_quota_exceeded_payload(request.user, company=company),
                status=status.HTTP_403_FORBIDDEN,
            )

        image_bytes = image_file.read()
        mime_type = image_file.content_type

        atlas_manager = atlas.AtlasManager()
        resultado = async_to_sync(atlas_manager.analyze_image_for_products_async)(image_bytes, mime_type)

        if "error" in resultado and not resultado.get("products"):
            self._refund_free_interaction(request.user)
            return Response(resultado, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        quota_status = self._get_user_plan(request.user).get_quota_status()
        resultado['free_interactions_left'] = quota_status['free_interactions_left']
        resultado['used_today'] = quota_status['used_today']
        resultado['daily_limit'] = quota_status['daily_limit']
        resultado['is_premium'] = quota_status['is_premium']
        resultado['quota_status'] = quota_status
        return Response(resultado, status=status.HTTP_200_OK)
    
    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/scan_image_multiple/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def scan_image_multiple(self, request):
        company = self._resolve_merchant_company(request.user)
        if not company:
            return Response(
                {'error': 'Debes poseer un comercio registrado para utilizar el escáner de inventario.'},
                status=status.HTTP_403_FORBIDDEN
            )
        image_file = request.FILES.get('image')
        if not image_file:
            return Response(
                {'error': 'No se proporcionó ninguna imagen para el escaneo masivo.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if getattr(image_file, 'size', 0) > 15 * 1024 * 1024:
            return Response({'error': 'La imagen excede el tamaño máximo permitido (15 MB).'}, status=status.HTTP_400_BAD_REQUEST)

        if not self._consume_free_interaction(request.user):
            return Response(
                self._build_quota_exceeded_payload(request.user, company=company),
                status=status.HTTP_403_FORBIDDEN,
            )

        image_bytes = image_file.read()
        mime_type = image_file.content_type

        atlas_manager = atlas.AtlasManager()
        resultado = async_to_sync(atlas_manager.analyze_image_for_multiple_products_async)(image_bytes, mime_type)

        if "error" in resultado and not resultado.get("products"):
            self._refund_free_interaction(request.user)
            return Response(resultado, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        quota_status = self._get_user_plan(request.user).get_quota_status()
        resultado['free_interactions_left'] = quota_status['free_interactions_left']
        resultado['used_today'] = quota_status['used_today']
        resultado['daily_limit'] = quota_status['daily_limit']
        resultado['is_premium'] = quota_status['is_premium']
        resultado['quota_status'] = quota_status
        return Response(resultado, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/scan_excel_multiple/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def scan_excel_multiple(self, request):
        company = self._resolve_merchant_company(request.user)
        if not company:
            return Response(
                {'error': 'Debes poseer un comercio registrado para utilizar el escáner de inventario.'},
                status=status.HTTP_403_FORBIDDEN
            )
        excel_file = request.FILES.get('file')
        if not excel_file:
            return Response({'error': 'No se proporcionó ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST)
        if getattr(excel_file, 'size', 0) > 10 * 1024 * 1024:
            return Response({'error': 'El archivo excede el tamaño máximo permitido (10 MB).'}, status=status.HTTP_400_BAD_REQUEST)
        
        filename = excel_file.name.lower()
        if not filename.endswith(('.xlsx', '.xls', '.csv')):
            return Response({'error': 'Formato no soportado. Usa archivos .xlsx, .xls o .csv.'}, status=status.HTTP_400_BAD_REQUEST)
        raw_rows = []

        try:
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                wb = openpyxl.load_workbook(io.BytesIO(excel_file.read()), data_only=True)
                sheet = wb.active
                headers = [str(cell.value) if cell.value is not None else f"Col_{idx}" for idx, cell in enumerate(sheet[1])]
                
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if any(cell is not None for cell in row):
                        row_dict = {headers[idx]: str(val) if val is not None else "" for idx, val in enumerate(row) if idx < len(headers)}
                        raw_rows.append(row_dict)
            else:
                decoded_file = excel_file.read().decode('utf-8-sig').splitlines()
                reader = csv.DictReader(decoded_file)
                for row in reader:
                    raw_rows.append(dict(row))

            raw_rows = raw_rows[:50] 

        except Exception as e:
            print(f"[PARSING ERROR]: {e}")
            return Response({'error': 'Error al procesar la estructura del archivo.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if not self._consume_free_interaction(request.user):
            return Response(
                self._build_quota_exceeded_payload(request.user, company=company),
                status=status.HTTP_403_FORBIDDEN,
            )

        atlas_manager = atlas.AtlasManager()
        resultado = async_to_sync(atlas_manager.analyze_processed_json_products_async)(raw_rows)
        
        if "error" in resultado and not resultado.get("products"):
            self._refund_free_interaction(request.user)
            return Response(resultado, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        quota_status = self._get_user_plan(request.user).get_quota_status()
        resultado['free_interactions_left'] = quota_status['free_interactions_left']
        resultado['used_today'] = quota_status['used_today']
        resultado['daily_limit'] = quota_status['daily_limit']
        resultado['is_premium'] = quota_status['is_premium']
        resultado['quota_status'] = quota_status
        return Response(resultado, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/guest-session/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='guest-session')
    def guest_session(self, request):
        if request.user.is_authenticated:
            free_left = self._get_free_interactions_left(request.user)
            plan = self._get_user_plan(request.user)
            is_premium = bool(
                plan and plan.tier == AtlasSubscriptionTier.PREMIUM
                and plan.valid_until and plan.valid_until >= timezone.now()
            )
            return Response({
                'guest_token': None,
                'free_interactions_left': free_left,
                'daily_limit': self._get_daily_limit(request.user),
                'is_premium': is_premium,
                'login_required': False,
            }, status=status.HTTP_200_OK)

        daily_limit = self._anonymous_daily_limit()
        ip = self._client_ip(request)
        token = self._guest_token_from_request(request)
        if not self._known_guest(token):
            if (cache.get(f"cartmaker:atlas:anon-ip:{ip}") or 0) >= daily_limit:
                return Response(self._login_required_payload(daily_limit), status=status.HTTP_403_FORBIDDEN)
            token = secrets.token_urlsafe(32)
            self._remember_guest(token)
        else:
            self._remember_guest(token)

        remaining = self._anon_remaining(token, ip)
        return Response({
            'guest_token': token,
            'free_interactions_left': remaining,
            'daily_limit': daily_limit,
            'is_premium': False,
            'login_required': remaining <= 0,
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: GET /api/v1/atlas/current_thread/
    # ------------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def current_thread(self, request):
        if request.user.is_authenticated:
            plan = self._get_user_plan(request.user)
            is_premium = plan.is_active_premium()
            free_left = self._get_free_interactions_left(request.user)
            latest_thread = AtlasThread.objects.filter(plan=plan).order_by('-id').first()
            nombre_usuario = request.user.first_name.strip() if request.user.first_name else ""
        else:
            token = self._guest_token_from_request(request)
            if not self._known_guest(token):
                return Response(
                    self._login_required_payload(self._anonymous_daily_limit()),
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            is_premium = False
            free_left = self._anon_remaining(token, self._client_ip(request))
            latest_thread = AtlasThread.objects.filter(guest_key=token).order_by('-id').first()
            nombre_usuario = ""

        starter_quick_actions = [
            {"id": "qa_open_now", "label": "🟢 Abiertos ahora", "prompt": "Muéstrame tiendas y productos abiertos ahorita cerca de mi ubicación", "action_type": "STAGE_RADAR", "radar_params": {"intent": "FEED", "enfoque": "OPEN_NOW"}},
            {"id": "qa_flash_offers", "label": "⚡ Ofertas Flash", "prompt": "¿Qué ofertas y descuentos hay cerca de mí hoy?", "action_type": "STAGE_RADAR", "radar_params": {"intent": "FEED", "enfoque": "FLASH_OFFERS"}},
            {"id": "qa_tokens", "label": "🪙 Canjear Tokens", "prompt": "¿En qué productos puedo canjear o ganar tokens hoy?", "action_type": "STAGE_RADAR", "radar_params": {"intent": "FEED", "enfoque": "TOKEN_REWARDS"}},
            {"id": "qa_smart_bundle", "label": "🛒 Armar compra inteligente", "prompt": "Ayúdame a armar una lista de mercado al mejor precio en mi zona", "action_type": "SEND_PROMPT"},
        ]

        if not latest_thread:
            if request.user.is_authenticated:
                latest_thread = AtlasThread.objects.create(plan=plan)
            else:
                latest_thread = AtlasThread.objects.create(guest_key=token, plan=None)
            
            saludo_nombre = f", {nombre_usuario}" if nombre_usuario else ""
            # 💡 2. BANCO DE SALUDOS INICIALES DINÁMICOS (Naturales, sin muletillas prohibidas)
            saludos_templates = [
                f"¡Epa{saludo_nombre}! Qué bueno tenerte por aquí. Soy Atlas. Dime qué andas buscando hoy y rastreo el inventario de tu zona al instante.",
                f"¡Hola{saludo_nombre}! Por aquí Atlas. Estoy listo para conseguirte el mejor precio, armar tu mercado o mostrarte qué tiendas están abiertas ahorita.",
                f"¡Qué más{saludo_nombre}! Te saluda Atlas. Dime qué producto necesitas o toca uno de los accesos rápidos para explorar el radar de tu zona.",
                f"¡Hola{saludo_nombre}! Aquí Atlas reportándose. Cuéntame qué tienes en mente comprar hoy y te ubico las mejores opciones cerca de ti.",
            ]
            
            mensaje_bienvenida = random.choice(saludos_templates)
            welcome_experience = {
                "version": "2.0",
                "ui_mode": "CONVERSATIONAL",
                "cinematic_directive": {
                    "animation_type": "IDLE_PULSE",
                    "mood_theme": "DEFAULT",
                    "auto_expand_map": False,
                    "show_radar_pulse": False,
                    "sound_haptic_cue": "SOFT_POP",
                    "camera_keyframes": [],
                    "target_bounding_box": None,
                    "route_polyline_points": [],
                },
                "stores_map": [],
                "comparison_highlights": None,
                "smart_bundle": None,
                "video_reels": [],
                "token_opportunities": {
                    "items_with_redeemable_discount": 0,
                    "max_immediate_savings_usd": 0.0,
                    "best_item_id": None,
                },
                "zone_transition": None,
                "quick_actions": starter_quick_actions,
            }
            
            AtlasMessage.objects.create(
                conversation=latest_thread,
                origin=2,
                text=mensaje_bienvenida,
                product_ids=[],
                action_command={"action": "NONE", "atlas_experience": welcome_experience}
            )
            
        # 💡 FEATURE: PAGINACIÓN (Por defecto carga 15 mensajes)
        try:
            offset = int(request.query_params.get('offset', 0))
        except ValueError:
            offset = 0
        limit = 15

        # Obtenemos de más nuevo a más viejo para aplicar el slice exacto
        messages_qs = AtlasMessage.objects.filter(conversation=latest_thread).order_by('-creation')[offset:offset+limit]
        
        # Invertimos la lista de nuevo para entregar en orden cronológico (Viejo -> Nuevo)
        messages_list = list(messages_qs)[::-1]

        # 💡 FEATURE: HIDRATACIÓN DE PRODUCTOS EN TIEMPO REAL
        all_product_ids = set()
        for m in messages_list:
            if getattr(m, 'product_ids', None):
                all_product_ids.update(m.product_ids)

        items_dict = {}
        if all_product_ids:
            # Traemos la info viva para respetar el stock actual y pausas
            fresh_items = InventoryItem.objects.filter(id__in=all_product_ids).select_related(
                'product',
                'product__category',
                'store__company',
                'store__location',
                'store__location__mall',
            )
            for item in fresh_items:
                items_dict[str(item.id)] = item.get_json()

        messages_data = []
        for m in messages_list:
            msg_type = 'text'
            msg_products = []
            
            p_ids = getattr(m, 'product_ids', [])
            if p_ids:
                msg_type = 'products'
                for pid in p_ids:
                    if str(pid) in items_dict:
                        msg_products.append(items_dict[str(pid)])
                    else:
                        msg_products.append({"id": pid, "paused": True, "stock": 0})

            cmd = getattr(m, 'action_command', None)
            if isinstance(cmd, str):
                try:
                    cmd = json.loads(cmd)
                except Exception:
                    cmd = None

            msg_experience = cmd.get("atlas_experience") if isinstance(cmd, dict) else None

            messages_data.append({
                "id": m.id,
                "origin": m.origin, 
                "text": m.text,
                "type": msg_type,
                "products": msg_products if msg_products else None,
                "creation": m.creation.isoformat(),
                "action_command": cmd,
                "atlas_experience": msg_experience,
            })

        if request.user.is_authenticated:
            daily_limit = self._get_daily_limit(request.user)
            used_today = self._get_used_today(request.user)
            quota_status = self._get_user_plan(request.user).get_quota_status()
            login_required = False
        else:
            daily_limit = self._anonymous_daily_limit()
            used_today = max(0, daily_limit - free_left)
            quota_status = None
            login_required = free_left <= 0

        return Response({
            'thread_id': latest_thread.id,
            'free_interactions_left': free_left,
            'used_today': used_today,
            'is_premium': is_premium,
            'daily_limit': daily_limit,
            'requires_atlas_plus': bool(quota_status.get('requires_atlas_plus')) if quota_status else False,
            'quota_status': quota_status,
            'login_required': login_required,
            'initial_quick_actions': starter_quick_actions,
            'messages': messages_data
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT: POST /api/v1/atlas/{id}/message/
    # ------------------------------------------------------------------------
    @action(detail=True, methods=['post'])
    def message(self, request, pk=None):
        text = request.data.get('text')
        image_base64 = request.data.get('image_base64')
        
        if not text:
            return Response({'error': 'El texto del mensaje es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        guest_token = None
        guest_ip = None
        if request.user.is_authenticated:
            plan = self._get_user_plan(request.user)
            try:
                thread = AtlasThread.objects.get(pk=pk, plan=plan)
            except AtlasThread.DoesNotExist:
                return Response({'error': 'El hilo no existe.'}, status=status.HTTP_404_NOT_FOUND)
            is_premium = plan.is_active_premium()
            if not self._consume_free_interaction(request.user):
                return Response(
                    self._build_quota_exceeded_payload(request.user),
                    status=status.HTTP_403_FORBIDDEN,
                )
            atlas_user = request.user
        else:
            guest_token = self._guest_token_from_request(request)
            if not self._known_guest(guest_token):
                return Response(
                    self._login_required_payload(self._anonymous_daily_limit()),
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            try:
                thread = AtlasThread.objects.get(pk=pk, guest_key=guest_token)
            except AtlasThread.DoesNotExist:
                return Response({'error': 'El hilo no existe.'}, status=status.HTTP_404_NOT_FOUND)
            guest_ip = self._client_ip(request)
            is_premium = False
            if not self._consume_anon(guest_token, guest_ip):
                return Response(
                    self._login_required_payload(self._anonymous_daily_limit()),
                    status=status.HTTP_403_FORBIDDEN,
                )
            atlas_user = None

        lat = float(request.data.get('lat', 0.0) or 0.0)
        lng = float(request.data.get('lng', 0.0) or 0.0)
        user_locations = request.data.get('locations', []) or []

        atlas_manager = atlas.AtlasManager(
            user_lat=lat,
            user_lng=lng,
            user_locations=user_locations,
            user=atlas_user,
            seed=str(thread.id)
        )

        resultado = async_to_sync(atlas_manager.send_chat_message_async)(thread_id=thread.id, user_text=text, image_base64=image_base64)
        
        if not resultado.get('success'):
            if guest_token:
                self._refund_anon(guest_token, guest_ip)
            else:
                self._refund_free_interaction(request.user)
            return Response({'error': resultado.get('error')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 💡 ZERO-RESULTS QUOTA SHIELD: Si el usuario buscó un producto y no había stock en ninguna zona,
        # no le penalizamos su cuota diaria.
        quota_refunded = False
        if resultado.get('zero_results_refund_eligible'):
            quota_refunded = True
            if guest_token:
                self._refund_anon(guest_token, guest_ip)
            else:
                self._refund_free_interaction(request.user)

        if guest_token:
            free_left = self._anon_remaining(guest_token, guest_ip)
            daily_limit = self._anonymous_daily_limit()
            used_today = max(0, daily_limit - free_left)
            quota_status = None
            login_required = free_left <= 0
        else:
            quota_status = self._get_user_plan(request.user).get_quota_status()
            free_left = quota_status['free_interactions_left']
            daily_limit = quota_status['daily_limit']
            used_today = quota_status['used_today']
            login_required = False
            
        print(f"📦 [VIEWS] Comando enviado al Frontend: {resultado.get('action_command')}")
            
        return Response({
            'response': resultado['response'],
            'message_id': resultado['message_id'],
            'free_interactions_left': free_left,
            'used_today': used_today,
            'daily_limit': daily_limit,
            'is_premium': is_premium,
            'requires_atlas_plus': bool(quota_status.get('requires_atlas_plus')) if quota_status else False,
            'quota_status': quota_status,
            'login_required': login_required,
            'quota_refunded': quota_refunded,
            'injected_products': resultado.get('injected_products'),
            'action_command': resultado.get('action_command'),
            'atlas_experience': resultado.get('atlas_experience'),
        }, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------
    # ENDPOINT 0-TOKENS (<50ms): GET/POST /api/v1/atlas/stage_radar/
    # Permite al Frontend disparar escaneos de radar, filtros rápidos, cambios
    # de cámara en el mapa o armar combos SIN gastar tokens de Gemini ni cuota.
    # ------------------------------------------------------------------------
    def _handle_stage_radar(self, request):
        data = request.data if request.method == 'POST' else request.query_params
        try:
            lat = float(data.get('lat', 0.0) or 0.0)
            lng = float(data.get('lng', 0.0) or 0.0)
        except (TypeError, ValueError):
            lat, lng = 0.0, 0.0

        user_locations = data.get('locations', []) if isinstance(data.get('locations'), list) else []
        atlas_user = request.user if request.user.is_authenticated else None
        seed = str(data.get('seed') or (atlas_user.id if atlas_user else 'stage-radar'))

        intent = str(data.get('intent', 'FEED') or 'FEED').upper()
        query = str(data.get('query', '') or '').strip()

        def _to_bool(val, default=False):
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ('1', 'true', 'yes', 'si', 'sí')

        def _to_float(val):
            try:
                return float(val) if val is not None and val != '' else None
            except (TypeError, ValueError):
                return None

        atlas_manager = atlas.AtlasManager(
            user_lat=lat,
            user_lng=lng,
            user_locations=user_locations,
            user=atlas_user,
            seed=seed,
        )

        injected_products = []
        smart_bundle = None
        zone_transition = None
        applied_filters = {}
        tools_used = []

        mode_raw = str(data.get('mode') or 'best').lower()
        mode_map = {
            'cheapest': 'cheap',
            'cheap': 'cheap',
            'nearest': 'nearby',
            'nearby': 'nearby',
            'fastest': 'nearby',
            'balanced': 'best',
            'best': 'best',
            'discounts': 'cheap',
        }
        mapped_mode = mode_map.get(mode_raw, 'best')

        if intent == 'SHOPPING_LIST':
            raw_items = data.get('items') or []
            if isinstance(raw_items, str):
                raw_items = [x.strip() for x in raw_items.split(',') if x.strip()]
            title = str(data.get('title') or 'Compra Inteligente Atlas')
            budget_max_usd = _to_float(data.get('budget_max_usd'))
            plan = atlas_manager._execute_shopping_list({
                'items': raw_items,
                'titulo_plan': title,
                'presupuesto_max_usd': budget_max_usd,
                'mode': mapped_mode,
            })
            smart_bundle = plan
            injected_products = list(plan.get('injected', []))
            tools_used.append('armar_lista_o_receta')
        elif intent == 'SEARCH' or query:
            search_args = {
                'query': query,
                'mode': mapped_mode,
                'categoria': data.get('category') or data.get('categoria'),
                'comercio_o_centro_comercial': data.get('company') or data.get('tienda_o_empresa'),
                'solo_abiertos_ahora': _to_bool(data.get('only_open_now') or data.get('solo_abiertos_ahora'), False),
                'solo_ofertas': _to_bool(data.get('only_offers') or data.get('solo_ofertas') or (mode_raw == 'discounts'), False),
                'solo_con_descuento_tokens': _to_bool(data.get('only_token_discounts') or data.get('solo_descuento_tokens'), False),
                'precio_min_usd': _to_float(data.get('min_price') or data.get('precio_min')),
                'precio_max_usd': _to_float(data.get('max_price') or data.get('precio_max')),
                'unidad_venta': data.get('selling_unit') or data.get('unidad_venta'),
                'atributo_o_variante': data.get('variant_or_attribute') or data.get('atributo_o_variante'),
                'solo_en_centro_comercial': _to_bool(data.get('mall_only') or data.get('solo_centro_comercial'), False),
            }
            db_res = atlas_manager._execute_search(search_args)
            if db_res.get('applied_filters'):
                applied_filters.update(db_res['applied_filters'])
            if query:
                applied_filters['query'] = query
            if db_res.get('type') == 'results':
                injected_products = list(db_res.get('data', []))
                zone_transition = db_res.get('zone_transition')
            tools_used.append('buscar_productos_inventario')
        else:
            enfoque = str(data.get('enfoque') or data.get('focus') or 'parati').lower()
            if enfoque in ('open_now', 'abiertos_cerca'):
                applied_filters['only_open_now'] = True
            elif enfoque in ('flash_offers', 'ofertas'):
                applied_filters['only_offers'] = True
            elif enfoque in ('token_rewards', 'mis_tokens'):
                applied_filters['only_token_discounts'] = True
            injected_products = atlas_manager._execute_personalized_feed({
                'enfoque': enfoque,
                'categoria': data.get('category') or data.get('categoria'),
            })
            tools_used.append('explorar_feed_personalizado')

        atlas_experience = atlas_manager._build_atlas_experience(
            user_text=query or intent,
            injected_products=injected_products,
            smart_bundle=smart_bundle,
            zone_transition=zone_transition,
            tools_used=tools_used,
            applied_filters=applied_filters,
        )
        action_command = {
            "action": atlas_experience["ui_mode"],
            "ui_mode": atlas_experience["ui_mode"],
            "cinematic_directive": atlas_experience["cinematic_directive"],
            "quick_actions": atlas_experience["quick_actions"],
            "atlas_experience": atlas_experience,
        }

        return Response({
            'success': True,
            'zero_token_engine': True,
            'injected_products': injected_products,
            'action_command': action_command,
            'atlas_experience': atlas_experience,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get', 'post'], url_path='stage_radar')
    def stage_radar(self, request):
        return self._handle_stage_radar(request)

    @action(detail=False, methods=['get', 'post'], url_path='stage-radar')
    def stage_radar_dash(self, request):
        return self._handle_stage_radar(request)

    # ========================================================================
    # 🧠 PILAR 2: ATLAS BUSINESS COPILOT (MODO COMERCIANTE)
    # ========================================================================
    def _resolve_merchant_company(self, user):
        company = Company.objects.select_related('category').filter(owner=user).first()
        if company:
            return company
        emp = Employee.objects.select_related('company', 'company__category').filter(user=user, is_active=True).first()
        return emp.company if emp else None

    def _handle_merchant_briefing(self, request):
        from ..core.atlas_merchant import AtlasMerchantCopilot

        company = self._resolve_merchant_company(request.user)
        if not company:
            return Response(
                {'error': 'No tienes una compañía registrada para usar Atlas Business Copilot.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        access_status = AtlasMerchantCopilot.check_merchant_access(company, user=request.user)
        if not access_status.get('allowed'):
            return Response(
                {'error': access_status.get('reason'), 'access_status': access_status},
                status=status.HTTP_403_FORBIDDEN,
            )

        quota_status = self._get_user_plan(request.user).get_quota_status()

        force_refresh = str(request.query_params.get('refresh', 'false')).lower() == 'true'
        store_id = request.query_params.get('store_id')
        scope = request.query_params.get('scope') or ('single_branch' if store_id else 'all_branches')

        copilot = AtlasMerchantCopilot(company=company, user=request.user)
        snapshot = copilot.build_company_intelligence_snapshot(
            force_refresh=force_refresh,
            store_id=store_id,
            scope=scope,
        )
        history = copilot.get_thread_history()

        resolved_scope = snapshot.get('scope', 'all_branches')
        selected_store_id = snapshot.get('selected_store_id')
        selected_store_name = snapshot.get('selected_store_name', 'Todas las sucursales')
        branches_summary = snapshot.get('branches_summary', [])
        action_cards = snapshot.get('recommended_actions', [])

        if resolved_scope == 'single_branch' and selected_store_id:
            starter_prompts = [
                {
                    "id": "mp_unmet_demand",
                    "label": f"📍 ¿Qué buscan cerca de {selected_store_name}?",
                    "prompt": f"¿Qué productos están buscando los clientes cerca de mi sucursal '{selected_store_name}' que nadie está vendiendo ahorita?",
                },
                {
                    "id": "mp_price_check",
                    "label": "⚖️ Analizar precios de esta sede",
                    "prompt": f"Compara los precios de mi sucursal '{selected_store_name}' contra los comercios de mi zona y dime dónde debo hacer ajustes u ofertas.",
                },
                {
                    "id": "mp_rescue_clients",
                    "label": "🎯 Rescatar carritos de esta sede",
                    "prompt": f"¿Cuántos clientes vieron mis productos o los dejaron en el carrito en '{selected_store_name}' esta semana y cómo los cierro?",
                },
                {
                    "id": "mp_grow_sales",
                    "label": "🚀 Plan para subir ventas aquí",
                    "prompt": f"Dame un plan de acción concreto para subir mi conversión y rotación de inventario en '{selected_store_name}' esta semana.",
                },
            ]
        else:
            starter_prompts = [
                {
                    "id": "mp_unmet_demand",
                    "label": "📍 ¿Qué buscan en mi zona?",
                    "prompt": "¿Qué productos están buscando los clientes cerca de mis sucursales que nadie está vendiendo ahorita?",
                },
                {
                    "id": "mp_branches_compare",
                    "label": "🏢 Comparar mis sucursales",
                    "prompt": "Compara el rendimiento, facturación, conversión e inventario entre todas mis sucursales y dime cuál requiere atención inmediata.",
                },
                {
                    "id": "mp_rescue_clients",
                    "label": "🎯 Rescatar carritos abandonados",
                    "prompt": "¿Cuántos clientes vieron mis productos o los dejaron en el carrito esta semana en mis sucursales y cómo los cierro?",
                },
                {
                    "id": "mp_price_check",
                    "label": "⚖️ Analizar mis precios",
                    "prompt": "Compara mis precios contra los comercios de mi zona y dime en qué sucursal debo hacer ajustes u ofertas.",
                },
            ]

        payload = {
            'success': True,
            'scope': resolved_scope,
            'selected_store_id': selected_store_id,
            'selected_store_name': selected_store_name,
            'access_status': access_status,
            'quota_status': quota_status,
            'free_interactions_left': quota_status['free_interactions_left'],
            'used_today': quota_status['used_today'],
            'daily_limit': quota_status['daily_limit'],
            'is_premium': quota_status['is_premium'],
            'requires_atlas_plus': quota_status['requires_atlas_plus'],
            'snapshot': snapshot,
            'branches_summary': branches_summary,
            'branches': branches_summary,
            'action_cards': action_cards,
            'recommended_actions': action_cards,
            'starter_prompts': starter_prompts,
            'thread_history': history,
        }
        payload['data'] = {
            'scope': resolved_scope,
            'selected_store_id': selected_store_id,
            'selected_store_name': selected_store_name,
            'access_status': access_status,
            'quota_status': quota_status,
            'free_interactions_left': quota_status['free_interactions_left'],
            'used_today': quota_status['used_today'],
            'daily_limit': quota_status['daily_limit'],
            'is_premium': quota_status['is_premium'],
            'requires_atlas_plus': quota_status['requires_atlas_plus'],
            'snapshot': snapshot,
            'branches_summary': branches_summary,
            'branches': branches_summary,
            'action_cards': action_cards,
            'recommended_actions': action_cards,
            'starter_prompts': starter_prompts,
            'thread_history': history,
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='merchant_briefing')
    def merchant_briefing(self, request):
        return self._handle_merchant_briefing(request)

    @action(detail=False, methods=['get'], url_path='merchant-briefing')
    def merchant_briefing_dash(self, request):
        return self._handle_merchant_briefing(request)

    def _handle_merchant_consult(self, request):
        from ..core.atlas_merchant import AtlasMerchantCopilot

        company = self._resolve_merchant_company(request.user)
        if not company:
            return Response(
                {'error': 'No tienes una compañía registrada para usar Atlas Business Copilot.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        prompt = (
            request.data.get('message')
            or request.data.get('prompt')
            or request.data.get('text')
            or ''
        ).strip()
        reset_thread = bool(request.data.get('reset_thread', False))
        store_id = request.data.get('store_id') or request.query_params.get('store_id')
        scope = (
            request.data.get('scope')
            or request.query_params.get('scope')
            or ('single_branch' if store_id else 'all_branches')
        )

        if not prompt:
            return Response(
                {'error': 'Debes enviar tu consulta en el campo "message", "prompt" o "text".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Consumir 1 uso del presupuesto diario unificado (Atlas Comprador + Atlas Negocios)
        if not self._consume_free_interaction(request.user):
            return Response(
                self._build_quota_exceeded_payload(request.user, company=company),
                status=status.HTTP_403_FORBIDDEN,
            )

        copilot = AtlasMerchantCopilot(company=company, user=request.user)
        try:
            result = async_to_sync(copilot.consult_async)(
                user_prompt=prompt,
                reset_thread=reset_thread,
                store_id=store_id,
                scope=scope,
            )
        except Exception as exc:
            self._refund_free_interaction(request.user)
            return Response(
                {'error': f'Error procesando consulta en Atlas Business: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        quota_status = self._get_user_plan(request.user).get_quota_status()
        access_status = AtlasMerchantCopilot.check_merchant_access(company, user=request.user)

        result['access_status'] = access_status
        result['quota_status'] = quota_status
        result['free_interactions_left'] = quota_status['free_interactions_left']
        result['used_today'] = quota_status['used_today']
        result['daily_limit'] = quota_status['daily_limit']
        result['is_premium'] = quota_status['is_premium']
        result['requires_atlas_plus'] = quota_status['requires_atlas_plus']

        result['data'] = {
            'scope': result.get('scope'),
            'selected_store_id': result.get('selected_store_id'),
            'selected_store_name': result.get('selected_store_name'),
            'response': result.get('response'),
            'health_score': result.get('health_score'),
            'kpis_highlighted': result.get('kpis_highlighted'),
            'branches_summary': result.get('branches_summary'),
            'action_cards': result.get('action_cards'),
            'snapshot': result.get('snapshot'),
            'access_status': access_status,
            'quota_status': quota_status,
            'free_interactions_left': quota_status['free_interactions_left'],
            'used_today': quota_status['used_today'],
            'daily_limit': quota_status['daily_limit'],
            'is_premium': quota_status['is_premium'],
            'requires_atlas_plus': quota_status['requires_atlas_plus'],
        }
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='merchant_consult')
    def merchant_consult(self, request):
        return self._handle_merchant_consult(request)

    @action(detail=False, methods=['post'], url_path='merchant-consult')
    def merchant_consult_dash(self, request):
        return self._handle_merchant_consult(request)

    def _handle_merchant_execute_action(self, request):
        from ..core.atlas_merchant import AtlasMerchantCopilot

        company = self._resolve_merchant_company(request.user)
        if not company:
            return Response(
                {'error': 'No tienes una compañía registrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        action_type = request.data.get('action_type')
        payload = request.data.get('payload') or {}
        if not action_type:
            return Response(
                {'error': 'El campo "action_type" es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        copilot = AtlasMerchantCopilot(company=company, user=request.user)
        result = copilot.execute_action(action_type=action_type, payload=payload)
        http_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=http_status)

    @action(detail=False, methods=['post'], url_path='merchant_execute_action')
    def merchant_execute_action(self, request):
        return self._handle_merchant_execute_action(request)

    @action(detail=False, methods=['post'], url_path='merchant-execute-action')
    def merchant_execute_action_dash(self, request):
        return self._handle_merchant_execute_action(request)

    # ========================================================================
    # 🧾 FACTURACIÓN DIGITAL VENEZOLANA (SENIAT / BCV) — PLAN ATLAS PLUS
    # ========================================================================
    @action(detail=False, methods=['get'], url_path='invoices')
    def invoices(self, request):
        """
        GET /api/v1/atlas/invoices/
        Lista todas las facturas digitales emitidas al usuario autenticado por sus pagos aprobados de Atlas Plus.
        """
        config = SystemConfig.objects.order_by('-creation').first()
        plan = self._get_user_plan(request.user)
        approved_payments = (
            AtlasPlusPlanPayment.objects.filter(plan=plan, status=PaymentStatus.APPROVED)
            .select_related('invoice')
            .order_by('-creation')
        )
        invoices_list = []
        for payment in approved_payments:
            try:
                inv = getattr(payment, 'invoice', None)
            except Exception:
                inv = None
            if inv is None:
                inv = AtlasPlusInvoice.issue_for_payment(payment=payment, config=config)
            invoices_list.append(inv.get_json())

        return Response({
            'success': True,
            'count': len(invoices_list),
            'billing_issuer': config.get_billing_issuer_json() if config else None,
            'invoices': invoices_list,
            'data': invoices_list,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path=r'invoices/(?P<lookup_id>[^/.]+)')
    def invoice_detail(self, request, lookup_id=None):
        """
        GET /api/v1/atlas/invoices/<payment_id_or_invoice_uuid>/
        Devuelve el detalle fiscal completo y el link PDF/imprimible de una factura de Atlas Plus.
        """
        config = SystemConfig.objects.order_by('-creation').first()
        invoice = None

        if str(lookup_id).isdigit():
            payment_qs = AtlasPlusPlanPayment.objects.select_related('plan__user', 'invoice').filter(pk=int(lookup_id))
            if not (request.user.is_staff or request.user.is_superuser):
                payment_qs = payment_qs.filter(plan__user=request.user)
            payment = payment_qs.first()
            if not payment:
                return Response({'error': 'No se encontró el pago especificado.'}, status=status.HTTP_404_NOT_FOUND)
            if payment.status != PaymentStatus.APPROVED:
                return Response(
                    {'error': 'La factura digital solo se emite para pagos verificados y aprobados.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                existing_inv = getattr(payment, 'invoice', None)
            except Exception:
                existing_inv = None
            invoice = existing_inv or AtlasPlusInvoice.issue_for_payment(payment=payment, config=config)
        else:
            inv_qs = AtlasPlusInvoice.objects.select_related('payment', 'user').filter(pk=lookup_id)
            if not (request.user.is_staff or request.user.is_superuser):
                inv_qs = inv_qs.filter(user=request.user)
            invoice = inv_qs.first()
            if not invoice:
                return Response({'error': 'No se encontró la factura especificada.'}, status=status.HTTP_404_NOT_FOUND)

        inv_json = invoice.get_json()
        return Response({
            'success': True,
            'invoice': inv_json,
            'invoice_url': invoice.invoice_url,
            'data': inv_json,
        }, status=status.HTTP_200_OK)



